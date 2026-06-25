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

        // Only show loading if we're actually generating new questions
        // Check for existing quiz first
        let existingQuiz = null;
        try {
            const check = await fetch(`/api/v1/sessions/${sessionId}/quiz/current?kp_id=${kpId}`);
            existingQuiz = await check.json();
        } catch (e) { /* ignore */ }

        if (!existingQuiz || !existingQuiz.has_quiz) {
            this.container.innerHTML = '<div class="quiz-loading"><div class="spinner"></div><p>正在生成测验题目...</p></div>';
        }
        this.container.classList.remove('hidden');
        if (this.inputArea) this.inputArea.classList.add('hidden');

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

            // Show greeting
            this.showGreeting(data.greeting, data.knowledge_point);

            // Show first question after brief delay
            setTimeout(() => {
                this.renderQuestion(data.first_question);
            }, 1000);
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

        const card = document.createElement('div');
        card.className = 'quiz-question-card';
        card.id = 'quiz-current-question';

        // Progress bar
        const answered = question.index;
        const total = question.total;
        const pct = Math.round(answered / total * 100);

        // Difficulty label
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
            <div class="quiz-question-text">${this.escapeHtml(question.question_text)}</div>
            <div class="quiz-options">
                ${(question.options || []).map(opt => `
                    <div class="quiz-option" data-option="${opt.label}">
                        <span class="quiz-option-letter">${opt.label}</span>
                        <span class="quiz-option-text">${this.escapeHtml(opt.text)}</span>
                    </div>
                `).join('')}
            </div>
            <div class="quiz-feedback" id="quiz-feedback"></div>
        `;
        this.container.appendChild(card);

        // Scroll to card
        card.scrollIntoView({behavior: 'smooth', block: 'center'});

        // Attach option click handlers
        card.querySelectorAll('.quiz-option').forEach(opt => {
            opt.addEventListener('click', () => {
                if (opt.classList.contains('disabled')) return;
                this.submitAnswer(opt.dataset.option, card);
            });
        });
    },

    async submitAnswer(answer, card) {
        // Disable all options
        card.querySelectorAll('.quiz-option').forEach(o => o.classList.add('disabled'));

        // Highlight selected
        const selected = card.querySelector(`.quiz-option[data-option="${answer}"]`);
        if (selected) selected.classList.add('selected');

        try {
            const resp = await fetch(
                `/api/v1/sessions/${App.state.sessionId}/quiz/${this.quizId}/answer?answer=${encodeURIComponent(answer)}`,
                {method: 'POST'}
            );
            const data = await resp.json();

            // Show feedback if available
            if (data.feedback) {
                this.showFeedback(card, data.feedback);
            }

            // Update roadmap
            if (data.p_know_end !== undefined || data.completed) {
                App.updateRoadmapFromQuiz();
            }

            if (data.completed) {
                // Show final result after delay
                setTimeout(() => {
                    this.showResult(data);
                }, 1800);
            } else if (data.next_question) {
                // Show next question after delay
                setTimeout(() => {
                    this.renderQuestion(data.next_question);
                }, 1500);
            }
        } catch (e) {
            console.error('Quiz answer submission failed:', e);
            const fb = card.querySelector('#quiz-feedback');
            if (fb) {
                fb.innerHTML = '<span style="color:var(--red);">提交失败，请重试。</span>';
            }
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

        const pct = data.p_know_end;
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
        const statusLabel = statusLabels[data.mastery_status] || data.mastery_status;
        const statusColor = statusColors[data.mastery_status] || 'var(--text)';

        // Build answer details
        const detailsHtml = (data.details || []).map(d => {
            const cls = d.is_correct ? 'correct' : 'incorrect';
            const icon = d.is_correct ? '✓' : '✗';
            return `<span class="quiz-dot ${cls}" title="第${d.question_index + 1}题：${d.is_correct ? '正确' : '错误'}">${icon}</span>`;
        }).join('');

        resultDiv.innerHTML = `
            <div class="quiz-result-header">
                <div class="quiz-result-icon">${data.mastery_status === 'mastered' ? '🎉' : '📊'}</div>
                <h3>测验完成！</h3>
            </div>
            <div class="quiz-result-stats">
                <div class="quiz-stat">
                    <span class="quiz-stat-value" style="color:${statusColor};">${pct}%</span>
                    <span class="quiz-stat-label">掌握概率</span>
                </div>
                <div class="quiz-stat">
                    <span class="quiz-stat-value">${data.correct_count}/${data.total_questions}</span>
                    <span class="quiz-stat-label">答对题数</span>
                </div>
                <div class="quiz-stat">
                    <span class="quiz-stat-value" style="color:${statusColor};">${statusLabel}</span>
                    <span class="quiz-stat-label">掌握状态</span>
                </div>
            </div>
            <div class="quiz-result-dots">${detailsHtml}</div>
            <div class="quiz-result-assessment">
                <strong>BKT分析：</strong>${data.assessment}
            </div>
            <div class="quiz-result-actions">
                <button class="quiz-btn retry" onclick="Quiz.retry()">重新测验</button>
                <button class="quiz-btn continue" onclick="App.advanceToNext()">下一个知识点</button>
            </div>
        `;
        this.container.appendChild(resultDiv);
        resultDiv.scrollIntoView({behavior: 'smooth', block: 'center'});

        // Update roadmap
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
