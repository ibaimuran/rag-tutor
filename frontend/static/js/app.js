const App = {
    state: {
        sessionId: null,
        courseId: 1,
        userId: 1,
        currentKpId: null,
        currentMode: 'reading',  // 'reading' | 'chat' | 'quiz'
        phase: 'idle',
        roadmap: null,
    },

    async init() {
        const params = new URLSearchParams(window.location.search);
        this.state.sessionId = parseInt(params.get('session_id')) || null;
        this.state.courseId = parseInt(params.get('course_id')) || 1;

        if (!this.state.sessionId) {
            const session = await API.createSession(this.state.userId, this.state.courseId);
            this.state.sessionId = session.id;
            window.history.replaceState({}, '', `?session_id=${session.id}`);
        }

        await this.loadCourses();
        await this.loadRoadmap();
        await this.loadChatHistory();

        document.getElementById('mode-read-btn').addEventListener('click', () => this.switchMode('reading'));
        document.getElementById('mode-chat-btn').addEventListener('click', () => this.switchMode('chat'));
        document.getElementById('mode-quiz-btn').addEventListener('click', () => this.switchMode('quiz'));

        document.getElementById('send-btn').addEventListener('click', () => this.sendMessage());
        document.getElementById('chat-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); }
        });
    },

    switchMode(mode) {
        this.state.currentMode = mode;

        document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
        const btnMap = { reading: 'mode-read-btn', chat: 'mode-chat-btn', quiz: 'mode-quiz-btn' };
        document.getElementById(btnMap[mode]).classList.add('active');

        // Show/hide panels
        document.getElementById('reading-panel').classList.toggle('hidden', mode !== 'reading');

        const qaPanel = document.getElementById('qa-panel');
        qaPanel.classList.toggle('hidden', mode === 'reading');

        const chatMessages = document.getElementById('chat-messages');
        const chatInputArea = document.getElementById('chat-input-area');
        const quizContainer = document.getElementById('quiz-container');

        if (mode === 'reading') {
            chatMessages.classList.add('hidden');
            chatInputArea.classList.add('hidden');
            if (quizContainer) quizContainer.classList.add('hidden');
            if (this.state.currentKpId) this.loadKpContent(this.state.currentKpId);
        } else if (mode === 'chat') {
            chatMessages.classList.remove('hidden');
            chatInputArea.classList.remove('hidden');
            if (quizContainer) quizContainer.classList.add('hidden');
            if (this.state.currentKpId) this.startChatForConcept(this.state.currentKpId);
        } else if (mode === 'quiz') {
            chatMessages.classList.add('hidden');
            chatInputArea.classList.add('hidden');
            if (quizContainer) quizContainer.classList.remove('hidden');
            if (this.state.currentKpId) this.startQuizForConcept(this.state.currentKpId);
        }
    },

    // === Course Switcher ===
    async loadCourses() {
        try {
            const resp = await fetch('/api/v1/admin/courses');
            const courses = await resp.json();
            if (!courses || courses.length <= 1) return;

            const switcher = document.getElementById('course-switcher');
            const list = document.getElementById('course-switcher-list');
            switcher.classList.remove('hidden');

            list.innerHTML = courses.map(c => `
                <div class="cs-item${c.id === this.state.courseId ? ' active' : ''}" data-course-id="${c.id}">
                    <span>${this.escapeHtml(c.title)}</span>
                    <span class="cs-item-badge">${c.subject || ''}</span>
                </div>
            `).join('');

            list.querySelectorAll('.cs-item').forEach(item => {
                item.addEventListener('click', async () => {
                    const courseId = parseInt(item.dataset.courseId);
                    if (courseId === this.state.courseId) return;
                    const session = await API.createSession(this.state.userId, courseId);
                    window.location.href = `/app?session_id=${session.id}&course_id=${courseId}`;
                });
            });

            document.getElementById('course-switcher-toggle').addEventListener('click', () => {
                list.classList.toggle('hidden');
                document.getElementById('course-switcher-toggle').classList.toggle('collapsed');
            });
        } catch (e) { /* optional */ }
    },

    escapeHtml(text) {
        if (!text) return '';
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    },

    // === Roadmap ===
    async loadRoadmap() {
        const data = await API.getRoadmap(this.state.sessionId);
        if (data.error) { console.error(data.error); return; }
        this.state.roadmap = data;
        document.getElementById('course-title').textContent = data.course_title;
        Roadmap.render(data);
        this.updateProgress(data.overall_progress);
    },

    updateProgress(pct) {
        document.getElementById('progress-text').textContent = Math.round(pct) + '%';
        document.getElementById('progress-circle').style.strokeDashoffset = 163.4 * (1 - pct / 100);
    },

    async loadChatHistory() {
        const data = await API.getChatHistory(this.state.sessionId);
        if (data.messages) {
            data.messages.forEach(m => Chat.appendBubble(m.role, m.content, m));
        }
    },

    // === Reading Mode ===
    async loadKpContent(kpId) {
        const panel = document.getElementById('kp-content');
        panel.innerHTML = '<p class="placeholder-text">正在加载...</p>';
        try {
            const resp = await fetch(`/api/v1/sessions/knowledge-points/${kpId}/content/html`);
            panel.innerHTML = await resp.text();
        } catch (e) {
            panel.innerHTML = '<p class="placeholder-text">无法加载教材内容，请重试。</p>';
        }
    },

    // === Chat/Dialogue Mode (Socratic AI tutor + BKT) ===
    async startChatForConcept(kpId) {
        document.getElementById('chat-messages').innerHTML = '';
        Chat.showTyping();
        try {
            const resp = await API.chat(this.state.sessionId, '', kpId);
            Chat.hideTyping();
            this.handleChatResponse(resp);
        } catch (e) {
            Chat.hideTyping();
            Chat.appendBubble('assistant', '抱歉，出现了一些问题。请重试。');
        }
    },

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const text = input.value.trim();
        if (!text) return;
        input.value = '';
        input.disabled = true;
        document.getElementById('send-btn').disabled = true;

        Chat.appendBubble('user', text);
        Chat.showTyping();

        try {
            const resp = await API.chat(this.state.sessionId, text, this.state.currentKpId);
            Chat.hideTyping();
            this.handleChatResponse(resp);
        } catch (e) {
            Chat.hideTyping();
            Chat.appendBubble('assistant', '抱歉，出现了一些问题。请重试。');
        }

        input.disabled = false;
        document.getElementById('send-btn').disabled = false;
        input.focus();
    },

    handleChatResponse(resp) {
        if (resp.answer_feedback) {
            Chat.appendFeedback(resp.answer_feedback);
        }

        Chat.appendBubble('assistant', resp.reply, resp);
        this.updatePhaseBadge(resp.phase);

        if (resp.current_kp) {
            document.getElementById('current-concept').textContent =
                `当前知识点：${resp.current_kp.title}`;
        }

        if (resp.bkt_update) {
            Roadmap.updateNode(resp.bkt_update);
        }

        if (resp.roadmap_update) {
            Roadmap.render(resp.roadmap_update);
            this.updateProgress(resp.roadmap_update.overall_progress);
        }

        this.handleMasteryAction(resp);

        if (resp.test_ready) {
            this.showTestButton();
        }
    },

    handleMasteryAction(resp) {
        const indicator = document.getElementById('mastery-indicator');
        if (!resp.next_action || resp.next_action.action === 'continue') {
            indicator.classList.add('hidden');
            return;
        }

        indicator.classList.remove('hidden', 'success', 'warning');

        if (resp.next_action.action === 'advance') {
            indicator.classList.add('success');
            const pct = resp.bkt_update ? Math.round(resp.bkt_update.p_know_after * 100) : 0;
            indicator.innerHTML = `
                <span>已掌握！掌握度 ${pct}%</span>
                <button class="mastery-action-btn advance" id="advance-btn">进入下一个知识点</button>
            `;
            document.getElementById('advance-btn').addEventListener('click', () => this.advanceToNext());
        } else if (resp.next_action.action === 'relearn') {
            indicator.classList.add('warning');
            const pct = resp.bkt_update ? Math.round(resp.bkt_update.p_know_after * 100) : 0;
            indicator.innerHTML = `
                <span>掌握度不足 ${pct}%，需要重新学习此知识点</span>
                <button class="mastery-action-btn relearn" id="relearn-btn">重新学习</button>
            `;
            document.getElementById('relearn-btn').addEventListener('click', () => this.relearnCurrent());
        }
    },

    advanceToNext() {
        const chapters = this.state.roadmap?.chapters || [];
        let found = false;
        for (const ch of chapters) {
            for (const kp of ch.knowledge_points) {
                if (found) {
                    this.navigateToConcept(kp.id);
                    document.getElementById('mastery-indicator').classList.add('hidden');
                    return;
                }
                if (kp.id === this.state.currentKpId) found = true;
            }
        }
    },

    relearnCurrent() {
        this.switchMode('reading');
        document.getElementById('mastery-indicator').classList.add('hidden');
        if (this.state.currentKpId) this.loadKpContent(this.state.currentKpId);
    },

    // === Quiz Mode ===
    async startQuizForConcept(kpId) {
        document.getElementById('quiz-container').classList.remove('hidden');
        Quiz.start(this.state.sessionId, kpId);
    },

    // === Shared ===
    async navigateToConcept(kpId) {
        this.state.currentKpId = kpId;
        Roadmap.setActive(kpId);
        document.getElementById('current-concept').textContent = '选择左侧知识点开始学习';

        // Always load reading content
        await this.loadKpContent(kpId);

        // Act according to current mode
        if (this.state.currentMode === 'chat') {
            await this.startChatForConcept(kpId);
        } else if (this.state.currentMode === 'quiz') {
            await this.startQuizForConcept(kpId);
        }
    },

    async updateRoadmapFromQuiz() {
        try {
            const data = await API.getRoadmap(this.state.sessionId);
            if (!data.error) {
                this.state.roadmap = data;
                Roadmap.render(data);
                this.updateProgress(data.overall_progress);
            }
        } catch (e) { /* silent */ }
    },

    updatePhaseBadge(phase) {
        const badge = document.getElementById('phase-badge');
        badge.className = 'badge ' + phase;
        badge.textContent = {
            idle: '待命中', diagnosing: '诊断中', teaching: '教学中',
            mastery_check: '掌握度检验', testing: '测试中', remediating: '补救学习',
        }[phase] || phase;
    },

    showTestButton() {
        document.getElementById('test-start-btn').classList.remove('hidden');
        document.getElementById('test-start-btn').onclick = () => Testing.start(this.state.sessionId);
    },

    hideTestButton() {
        document.getElementById('test-start-btn').classList.add('hidden');
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
