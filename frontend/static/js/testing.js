const Testing = {
    panel: document.getElementById('test-panel'),
    questions: document.getElementById('test-questions'),
    result: document.getElementById('test-result'),
    submitBtn: document.getElementById('test-submit-btn'),
    testId: null,
    chapterId: null,
    totalQuestions: 0,
    answeredCount: 0,
    currentQuestion: null,

    async start(sessionId) {
        const roadmap = App.state.roadmap;
        if (!roadmap || !roadmap.chapters || !roadmap.chapters.length) return;

        const currentChapter = roadmap.chapters[0];
        this.chapterId = currentChapter.id;

        this.panel.classList.remove('hidden');
        this.questions.innerHTML = '<p style="color:var(--text-secondary);">正在生成测试题...</p>';
        this.submitBtn.classList.add('hidden');
        this.result.classList.add('hidden');
        this.result.innerHTML = '';

        const data = await API.generateTest(sessionId, this.chapterId);
        if (data.status === 'failed') {
            this.questions.innerHTML = '<p style="color:var(--red);">测试生成失败，请重试。</p>';
            return;
        }

        this.testId = data.test_id;
        this.totalQuestions = data.total_questions || data.questions.length;
        this.answeredCount = 0;

        // Load the first question
        await this.loadNextQuestion(sessionId);
    },

    async loadNextQuestion(sessionId) {
        const data = await API.getNextQuestion(sessionId, this.testId);

        if (data.complete) {
            this.showResult({
                overall_score: data.overall_score,
                concept_results: null,
                chapter_passed: null,
            });
            return;
        }

        this.currentQuestion = data.question;
        this.answeredCount = data.answered;
        this.renderQuestion(data.question, data.remaining, data.total);
    },

    renderQuestion(question, remaining, total) {
        this.questions.innerHTML = '';

        const card = document.createElement('div');
        card.style.cssText = `
            margin-bottom: 16px; padding: 16px;
            background: var(--surface); border: 1px solid var(--border);
            border-radius: var(--radius);
        `;

        const progressPct = Math.round((total - remaining) / total * 100);
        const progressBar = `
            <div style="background:rgba(255,255,255,0.06);border-radius:4px;height:6px;margin-bottom:16px;">
                <div style="background:var(--accent);height:6px;border-radius:4px;width:${progressPct}%;transition:width 0.3s;"></div>
            </div>
            <div style="font-size:0.75rem;color:var(--text-tertiary);margin-bottom:12px;">
                第 ${total - remaining + 1} / ${total} 题
            </div>
        `;

        let optionsHtml = '';
        if (question.options && question.options.length) {
            optionsHtml = question.options.map(opt => `
                <label class="test-option-label" style="display:block;padding:10px 12px;margin:6px 0;
                    cursor:pointer;color:var(--text-secondary);border:1px solid var(--border);
                    border-radius:8px;transition:all 0.15s;">
                    <input type="radio" name="q_${question.id}" value="${opt.label}" style="margin-right:8px;">
                    ${opt.label}. ${opt.text}
                </label>
            `).join('');

            optionsHtml = `<div class="test-options" style="margin-top:12px;">${optionsHtml}</div>`;
        } else {
            optionsHtml = `<textarea id="test-textarea" rows="4"
                style="width:100%;background:rgba(255,255,255,0.04);border:1px solid var(--border);
                border-radius:8px;color:var(--text);padding:10px;font-family:var(--font-sans);
                resize:vertical;margin-top:8px;" placeholder="在此输入你的答案..."></textarea>`;
        }

        const typeLabels = {
            multiple_choice: '选择题', true_false: '判断题',
            fill_blank: '填空题', short_answer: '简答题',
        };

        card.innerHTML = `
            ${progressBar}
            <div style="font-size:0.75rem;color:var(--text-tertiary);margin-bottom:6px;">
                ${typeLabels[question.question_type] || question.question_type}
            </div>
            <div style="font-weight:600;font-size:1rem;line-height:1.6;">
                ${this.escapeHtml(question.question_text)}
            </div>
            ${optionsHtml}
            <button id="test-answer-btn" style="margin-top:14px;padding:10px 24px;background:var(--accent);
                color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;">
                提交答案
            </button>
            <div id="test-feedback" style="margin-top:10px;"></div>
        `;
        this.questions.appendChild(card);

        // Attach handlers
        this.attachOptionHover();
        document.getElementById('test-answer-btn').addEventListener('click', () => this.submitAnswer(App.state.sessionId));

        // Allow Enter key in textarea to not submit, Ctrl+Enter to submit
        const textarea = document.getElementById('test-textarea');
        if (textarea) {
            textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && e.ctrlKey) {
                    e.preventDefault();
                    this.submitAnswer(App.state.sessionId);
                }
            });
        }

        // Double-click option to submit immediately
        card.querySelectorAll('.test-option-label').forEach(label => {
            label.addEventListener('dblclick', () => {
                label.querySelector('input').checked = true;
                this.submitAnswer(App.state.sessionId);
            });
        });
    },

    attachOptionHover() {
        document.querySelectorAll('.test-option-label').forEach(label => {
            label.addEventListener('mouseenter', () => {
                label.style.background = 'rgba(255,255,255,0.04)';
            });
            label.addEventListener('mouseleave', () => {
                if (!label.querySelector('input').checked) {
                    label.style.background = '';
                }
            });
        });
        document.querySelectorAll('.test-option-label input').forEach(input => {
            input.addEventListener('change', () => {
                const allLabels = input.closest('.test-options').querySelectorAll('.test-option-label');
                allLabels.forEach(l => { l.style.background = ''; l.style.borderColor = 'var(--border)'; });
                if (input.checked) {
                    input.closest('.test-option-label').style.background = 'rgba(99,102,241,0.12)';
                    input.closest('.test-option-label').style.borderColor = 'var(--accent)';
                }
            });
        });
    },

    async submitAnswer(sessionId) {
        if (!this.currentQuestion) return;

        let answer = '';
        const selected = document.querySelector(`input[name="q_${this.currentQuestion.id}"]:checked`);
        if (selected) {
            answer = selected.value;
        } else {
            const textarea = document.getElementById('test-textarea');
            if (textarea) {
                answer = textarea.value.trim();
            }
        }

        if (!answer) {
            alert('请先回答问题。');
            return;
        }

        // Disable submit button and show loading
        const btn = document.getElementById('test-answer-btn');
        btn.disabled = true;
        btn.textContent = '提交中...';

        const data = await API.submitAnswer(sessionId, this.testId, this.currentQuestion.id, answer);
        this.showFeedback(data);

        if (data.has_next) {
            // Wait a moment, then load next question
            await new Promise(r => setTimeout(r, 1500));
            await this.loadNextQuestion(sessionId);
        } else {
            // All done
            if (data.overall_result) {
                this.showResult(data.overall_result);
            }
        }
    },

    showFeedback(data) {
        const feedback = document.getElementById('test-feedback');
        if (!feedback) return;

        const correct = data.is_correct;
        const color = correct ? 'var(--green)' : 'var(--red)';
        const icon = correct ? '✓' : '✗';
        const label = correct ? '回答正确' : '回答错误';

        feedback.innerHTML = `
            <div style="padding:10px 14px;border-radius:8px;background:${correct ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)'};
                border:1px solid ${color};color:${color};font-weight:600;">
                ${icon} ${label}
                <span style="font-weight:400;margin-left:8px;">正确答案：${this.escapeHtml(data.correct_answer)}</span>
            </div>
        `;

        // Disable further interaction
        const btn = document.getElementById('test-answer-btn');
        if (btn) btn.disabled = true;
        const inputs = document.querySelectorAll('.test-options input, #test-textarea');
        inputs.forEach(i => i.disabled = true);
    },

    showResult(data) {
        this.result.classList.remove('hidden');
        this.questions.innerHTML = '';

        const passed = data.chapter_passed;
        const color = passed ? 'var(--green)' : 'var(--red)';
        const text = passed ? '通过' : '未通过';
        const score = data.overall_score || 0;

        let detailsHtml = '';
        if (data.concept_results) {
            for (const [kpId, info] of Object.entries(data.concept_results)) {
                const c = info.needs_relearn ? 'var(--red)' : 'var(--green)';
                const s = info.needs_relearn ? '需重学' : '已掌握';
                detailsHtml += `
                    <div style="margin:6px 0;padding:6px 10px;border-radius:6px;
                        background:rgba(255,255,255,0.03);font-size:0.8rem;">
                        <span style="color:${c};font-weight:600;">${info.needs_relearn ? '⚠' : '✓'} ${s}</span>
                        <span style="color:var(--text-tertiary);"> · 掌握度 ${Math.round(info.p_know_after * 100)}%</span>
                        <span style="color:var(--text-tertiary);"> · ${info.correct_answers} 正确</span>
                    </div>`;
            }
        }

        this.result.innerHTML = `
            <div style="font-size:1.2rem;font-weight:700;color:${color};margin-bottom:8px;">
                ${text} · 得分 ${score}%
            </div>
            ${detailsHtml}
            ${passed !== null && !passed ? `<p style="margin-top:12px;color:var(--amber);font-size:0.85rem;">
                ⚠ 标有"需重学"的知识点需要重新学习，之后才能进入下一章。</p>` : ''}
        `;

        document.getElementById('test-submit-btn').classList.add('hidden');
        App.loadRoadmap();
        App.hideTestButton();
    },

    escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },
};

// Close test panel
document.getElementById('test-close-btn').addEventListener('click', () => {
    document.getElementById('test-panel').classList.add('hidden');
});
