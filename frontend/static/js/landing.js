(function () {
    const input = document.getElementById('topic-input');
    const startBtn = document.getElementById('start-btn');
    const progress = document.getElementById('generation-progress');
    const progressDetail = document.getElementById('progress-detail');
    const coursesNav = document.getElementById('courses-nav');
    const coursesEmpty = document.getElementById('courses-empty');
    const coursesCount = document.getElementById('courses-count');

    function resetState() {
        progress.classList.add('hidden');
        input.disabled = false;
        startBtn.disabled = false;
    }
    resetState();
    window.addEventListener('pageshow', resetState);

    function showProgress(msg) {
        progress.classList.remove('hidden');
        progressDetail.textContent = msg;
    }

    function setLoading(loading) {
        input.disabled = loading;
        startBtn.disabled = loading;
    }

    async function loadCourses() {
        try {
            const resp = await fetch('/api/v1/admin/courses');
            const courses = await resp.json();
            if (!courses || courses.length === 0) {
                coursesNav.innerHTML = '';
                coursesEmpty.classList.remove('hidden');
                coursesCount.textContent = '';
                return;
            }
            coursesEmpty.classList.add('hidden');
            coursesCount.textContent = `${courses.length} 门`;
            coursesNav.innerHTML = courses.map(c => `
                <div class="course-nav-item" data-course-id="${c.id}" data-course-title="${esc(c.title)}">
                    <div class="course-nav-icon">📚</div>
                    <div class="course-nav-info">
                        <div class="course-nav-title">${esc(c.title)}</div>
                        <div class="course-nav-meta">${esc(c.subject || '通用')} · ${esc(c.grade_level || '')}</div>
                    </div>
                    <button class="course-nav-delete" data-course-id="${c.id}" data-course-title="${esc(c.title)}" title="删除">✕</button>
                </div>
            `).join('');
            coursesNav.querySelectorAll('.course-nav-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    if (e.target.closest('.course-nav-delete')) return;
                    enterCourse(parseInt(item.dataset.courseId));
                });
            });
            coursesNav.querySelectorAll('.course-nav-delete').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteCourse(parseInt(btn.dataset.courseId), btn.dataset.courseTitle);
                });
            });
        } catch (e) {
            coursesNav.innerHTML = '<p class="courses-loading">加载失败</p>';
        }
    }

    async function enterCourse(courseId) {
        try {
            showProgress('正在创建学习会话...');
            setLoading(true);
            const sessionResp = await fetch(`/api/v1/sessions?user_id=1&course_id=${courseId}`, {method: 'POST'});
            const session = await sessionResp.json();
            if (session.error) { alert('创建学习会话失败：' + session.error); resetState(); return; }
            window.location.href = `/app?session_id=${session.id}&course_id=${courseId}`;
        } catch (e) { alert('网络错误，请重试。'); resetState(); }
    }

    async function deleteCourse(courseId, title) {
        if (!confirm(`确定删除「${title}」？所有章节、知识点和学习记录将被永久删除。`)) return;
        try {
            const resp = await fetch(`/api/v1/admin/courses/${courseId}`, {method: 'DELETE'});
            const result = await resp.json();
            if (result.status === 'deleted') loadCourses();
            else alert('删除失败');
        } catch (e) { alert('网络错误'); }
    }

    async function startLearning(topic) {
        topic = topic.trim();
        if (!topic) return;
        setLoading(true);
        showProgress('正在分析主题...');
        try {
            const resp = await fetch(`/api/v1/admin/generate-course-from-topic?topic=${encodeURIComponent(topic)}`, {method: 'POST'});
            const result = await resp.json();
            if (result.error) { alert('课程生成失败：' + result.error); resetState(); return; }
            progressDetail.textContent = `已生成 ${result.chapters_count || 0} 个章节、${result.knowledge_points_count || 0} 个知识点，正在进入...`;
            setTimeout(async () => {
                const sessionResp = await fetch(`/api/v1/sessions?user_id=1&course_id=${result.course_id}`, {method: 'POST'});
                const session = await sessionResp.json();
                window.location.href = `/app?session_id=${session.id}&course_id=${result.course_id}`;
            }, 800);
        } catch (e) { alert('网络错误，请重试。'); resetState(); }
    }

    function esc(s) {
        if (!s) return '';
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    startBtn.addEventListener('click', () => startLearning(input.value));
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') startLearning(input.value); });
    document.querySelectorAll('.example-chip').forEach(chip => {
        chip.addEventListener('click', () => { input.value = chip.dataset.topic; input.focus(); });
    });

    loadCourses();
})();
