/**
 * Quiz module - per-knowledge-point quiz with BKT evaluation.
 *
 * Flow:
 *   1. User clicks Q&A tab → starts quiz for current KP
 *   2. Shows greeting + question 1
 *   3. User clicks option → immediate feedback → auto-advance to next
 *   4. After Q10 → BKT evaluation result
 */

const Quiz = {
    quizId: null,
    totalQuestions: 0,
    answeredCount: 0,
    container: null,
    inputArea: null,

    async start(sessionId, kpId) {
        this.container = document.getElementById('quiz-container');
        this.inputArea = document.getElementById('chat-input-area');
        // 清空旧内容，避免切换知识点时显示上一个知识点的测验
        this.container.innerHTML = '';
        this.container.classList.remove('hidden');
        if (this.inputArea) this.inputArea.classList.add('hidden');

        // 检查已有测验记录
        let existingQuiz = null;
        try {
            const check = await fetch(`/api/v1/sessions/${sessionId}/quiz/current?kp_id=${kpId}`);
            existingQuiz = await check.json();
        } catch (e) { /* ignore */ }

        // 如果有已完成的测验，直接显示结果
        if (existingQuiz && existingQuiz.has_quiz && existingQuiz.status === 'completed') {
            try {
                const resp = await fetch(`/api/v1/sessions/${sessionId}/quiz/${existingQuiz.quiz_id}/result`);
                const data = await resp.json();
                if (!data.error) {
                    this.quizId = existingQuiz.quiz_id;
                    this.totalQuestions = existingQuiz.total;
                    this.showResult(data);
                    return;
                }
            } catch (e) { /* fall through to start new */ }
        }

        // 显示加载中
        if (!existingQuiz || !existingQuiz.has_quiz) {
            this.container.innerHTML = '<div class="quiz-loading"><div class="spinner"></div><p>正在生成测验题目...</p></div>';
        }

        try {
            const resp = await fetch(`/api/v1/sessions/${sessionId}/quiz/start?kp_id=${kpId}`, {
                method: 'POST',
            });
            const data = await resp.json();
            if (data.error) {
                this.container.innerHTML = `<p class="quiz-error">${data.error}</p>`;
                return;
            }
            this.quizId = data.quiz_id;
            this.totalQuestions = data.total_questions;
            this.answeredCount = 0;

            // 如果是恢复进行中的测验
            if (data.question) {
                this.renderQuestion(data.question);
            } else {
                // 新测验
                this.showGreeting(data.greeting, data.knowledge_point);
                setTimeout(() => {
                    this.renderQuestion(data.first_question);
                }, 1000);
            }
        } catch (e) {
            this.container.innerHTML = '<p class="quiz-error">无法启动测验，请重试。</p>';
        }
    },

    showGreeting(greeting, kp) {
        const div = document.createElement('div');
        div.className = 'quiz-greeting';
        div.innerHTML = `
            <div class="quiz-greeting-icon">&#x1F4DD;</div>
            <p>${greeting}</p>
        `;
        this.container.appendChild(div);
    },

    renderQuestion(question) {
        if (!question) return;

        // Remove old question card
        const oldCard = document.getElementById('quiz-current-question');
        if (oldCard) oldCard.remove();

        const card = document.createElement('div');
        card.className = 'quiz-question-card';
        card.id = 'quiz-current-question';

        const answered = question.index || 0;
        const total = question.total || 0;
        const pct = total > 0 ? Math.round(answered / total * 100) : 0;
        const qText = question.question_text || '';
        const options = question.options || [];
        const diffLabels = {1: '基础', 2: '中等', 3: '综合'};
        const diffLabel = diffLabels[question.difficulty] || '';

        card.innerHTML = `
            <div class="quiz-progress-bar">
                <div class="quiz-progress-fill" style="width:${pct}%"></div>
            </div>
            <div class="quiz-progress-text">
                <span>第 ${answered + 1} / ${total} 题</span>
                <span class="quiz-diff-badge">${diffLabel}</span>
            </div>
            <div class="quiz-question-text">${this.escapeHtml(qText)}</div>
            <div class="quiz-options">
                ${options.map(opt => `
                    <div class="quiz-option" data-option="${this.escapeHtml(opt.label || '')}">
                        <span class="quiz-option-letter">${this.escapeHtml(opt.label || '')}</span>
                        <span class="quiz-option-text">${this.escapeHtml(opt.text || '')}</span>
                    </div>
                `).join('')}
            </div>
            <div class="quiz-feedback" id="quiz-feedback"></div>
        `;
        this.container.appendChild(card);
        card.scrollIntoView({behavior: 'smooth', block: 'center'});

        card.querySelectorAll('.quiz-option').forEach(opt => {
            opt.addEventListener('click', () => {
                if (opt.classList.contains('disabled')) return;
                this.submitAnswer(opt.dataset.option, card);
            });
        });
    },

    async submitAnswer(answer, card) {
        card.querySelectorAll('.quiz-option').forEach(o => o.classList.add('disabled'));
        const selected = card.querySelector(`.quiz-option[data-option="${answer}"]`);
        if (selected) selected.classList.add('selected');

        const url = `/api/v1/sessions/${App.state.sessionId}/quiz/${this.quizId}/answer?answer=${encodeURIComponent(answer)}`;
        try {
            const resp = await fetch(url, {method: 'POST'});
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            if (data.error) {
                const fb = card.querySelector('#quiz-feedback');
                if (fb) fb.innerHTML = `<span style="color:var(--red);">${data.error}</span>`;
                card.querySelectorAll('.quiz-option').forEach(o => o.classList.remove('disabled', 'selected'));
                return;
            }

            if (data.feedback) this.showFeedback(card, data.feedback);
            if (data.p_know_end !== undefined || data.completed) App.updateRoadmapFromQuiz();

            if (data.completed) {
                setTimeout(() => this.showResult(data), 1800);
            } else if (data.next_question) {
                setTimeout(() => this.renderQuestion(data.next_question), 1500);
            }
        } catch (e) {
            console.error('Quiz submit error:', e);
            const fb = card.querySelector('#quiz-feedback');
            if (fb) fb.innerHTML = '<span style="color:var(--red);">提交失败，请重试。</span>';
            card.querySelectorAll('.quiz-option').forEach(o => o.classList.remove('disabled', 'selected'));
        }
    },

    showFeedback(card, feedback) {
        const fb = card.querySelector('#quiz-feedback');
        if (!fb) return;

        const correct = feedback.is_correct;
        const icon = correct ? '✓' : '✗';
        const label = correct ? '回答正确' : '回答错误';
        const color = correct ? 'var(--green)' : 'var(--red)';

        fb.innerHTML = `
            <div class="quiz-feedback-content" style="border-color:${color};">
                <span class="quiz-feedback-icon" style="color:${color};">${icon}</span>
                <span class="quiz-feedback-label" style="color:${color};">${label}</span>
                ${!correct ? `<span class="quiz-feedback-correct">正确答案：<strong>${this.escapeHtml(feedback.correct_answer)}</strong></span>` : ''}
            </div>
        `;

        // Highlight correct option in green
        const correctOpt = card.querySelector(`.quiz-option[data-option="${feedback.correct_answer}"]`);
        if (correctOpt && !correct) {
            correctOpt.classList.add('correct');
        }
        if (correct) {
            const selected = card.querySelector(`.quiz-option.selected`);
            if (selected) selected.classList.add('correct');
        }
    },

    showResult(data) {
        const resultDiv = document.createElement('div');
        resultDiv.className = 'quiz-result-card';

        const pct = data.p_know_end || 0;
        const correctCount = data.correct_count || 0;
        const totalQuestions = data.total_questions || 0;
        const masteryStatus = data.mastery_status || 'learning';
        const assessment = data.assessment || '暂无评估';

        const statusLabels = {
            mastered: '已掌握 ✓',
            learning: '学习中 ▶',
            needs_relearn: '需重学 ⚠',
        };
        const statusColors = {
            mastered: 'var(--green)',
            learning: 'var(--accent-2)',
            needs_relearn: 'var(--red)',
        };
        const statusLabel = statusLabels[masteryStatus] || masteryStatus;
        const statusColor = statusColors[masteryStatus] || 'var(--text)';

        const detailsHtml = (data.details || []).map(d => {
            const cls = d.is_correct ? 'correct' : 'incorrect';
            const icon = d.is_correct ? '✓' : '✗';
            const idx = (d.question_index || 0) + 1;
            return `<span class="quiz-dot ${cls}" title="第${idx}题：${d.is_correct ? '正确' : '错误'}">${icon}</span>`;
        }).join('');

        resultDiv.innerHTML = `
            <div class="quiz-result-header">
                <div class="quiz-result-icon">${masteryStatus === 'mastered' ? '🎉' : '📊'}</div>
                <h3>测验完成！</h3>
            </div>
            <div class="quiz-result-stats">
                <div class="quiz-stat">
                    <span class="quiz-stat-value" style="color:${statusColor};">${pct}%</span>
                    <span class="quiz-stat-label">掌握概率</span>
                </div>
                <div class="quiz-stat">
                    <span class="quiz-stat-value">${correctCount}/${totalQuestions}</span>
                    <span class="quiz-stat-label">答对题数</span>
                </div>
                <div class="quiz-stat">
                    <span class="quiz-stat-value" style="color:${statusColor};">${statusLabel}</span>
                    <span class="quiz-stat-label">掌握状态</span>
                </div>
            </div>
            <div class="quiz-result-dots">${detailsHtml}</div>
            <div class="quiz-result-assessment">
                <strong>BKT分析：</strong>${assessment}
            </div>
            <div class="quiz-result-actions">
                <button class="quiz-btn retry" onclick="Quiz.retry()">重新测验</button>
            </div>
        `;
        this.container.appendChild(resultDiv);
        resultDiv.scrollIntoView({behavior: 'smooth', block: 'center'});

        App.loadRoadmap();
    },

    retry() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        const kpId = App.state.currentKpId;
        if (kpId) {
            this.start(App.state.sessionId, kpId);
        }
    },

    escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },
};
