const API = {
    base: '/api/v1',

    async get(path) {
        const res = await fetch(this.base + path);
        return res.json();
    },

    async post(path, body = {}) {
        const res = await fetch(this.base + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        return res.json();
    },

    createSession(userId = 1, courseId = 1) {
        return this.post(`/sessions?user_id=${userId}&course_id=${courseId}`);
    },

    getSession(id) { return this.get(`/sessions/${id}`); },
    pauseSession(id) { return this.post(`/sessions/${id}/pause`); },
    resumeSession(id) { return this.post(`/sessions/${id}/resume`); },

    chat(sessionId, message, targetKpId) {
        return this.post(`/sessions/${sessionId}/chat`, {
            message, target_kp_id: targetKpId,
        });
    },

    getChatHistory(sessionId) {
        return this.get(`/sessions/${sessionId}/chat/history`);
    },

    getRoadmap(sessionId) {
        return this.get(`/sessions/${sessionId}/roadmap`);
    },

    getRoadmapHtml(sessionId) {
        return this.get(`/sessions/${sessionId}/roadmap/html`);
    },

    generateTest(sessionId, chapterId) {
        return this.post(`/sessions/${sessionId}/test/generate?chapter_id=${chapterId}`);
    },

    getTest(sessionId, testId) {
        return this.get(`/sessions/${sessionId}/test/${testId}`);
    },

    submitTest(sessionId, testId, answers) {
        return this.post(`/sessions/${sessionId}/test/${testId}/submit`, { answers });
    },

    getNextQuestion(sessionId, testId) {
        return this.get(`/sessions/${sessionId}/test/${testId}/next`);
    },

    submitAnswer(sessionId, testId, questionId, answer) {
        return this.post(`/sessions/${sessionId}/test/${testId}/answer`, {
            question_id: questionId,
            answer: answer,
        });
    },

    getProgress(userId = 1, courseId = 1) {
        return this.get(`/progress/${userId}?course_id=${courseId}`);
    },

    getBktStates(userId = 1) {
        return this.get(`/progress/${userId}/bkt`);
    },

    getKpContent(kpId) {
        return this.get(`/sessions/knowledge-points/${kpId}/content`);
    },

    getKpContentHtml(kpId) {
        return fetch(`/api/v1/sessions/knowledge-points/${kpId}/content/html`).then(r => r.text());
    },

    // Quiz API
    startQuiz(sessionId, kpId) {
        return fetch(`/api/v1/sessions/${sessionId}/quiz/start?kp_id=${kpId}`, {method: 'POST'}).then(r => r.json());
    },

    answerQuiz(sessionId, quizId, answer) {
        return fetch(`/api/v1/sessions/${sessionId}/quiz/${quizId}/answer?answer=${encodeURIComponent(answer)}`, {method: 'POST'}).then(r => r.json());
    },

    getQuizResult(sessionId, quizId) {
        return this.get(`/sessions/${sessionId}/quiz/${quizId}/result`);
    },

    getCurrentQuiz(sessionId, kpId) {
        return this.get(`/sessions/${sessionId}/quiz/current?kp_id=${kpId}`);
    },
};
