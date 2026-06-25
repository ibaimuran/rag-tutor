const Chat = {
    container: document.getElementById('chat-messages'),

    appendBubble(role, content, meta = {}) {
        const div = document.createElement('div');
        div.className = `message ${role}`;

        const formatted = this.formatContent(content);

        if (role === 'assistant') {
            div.innerHTML = `<div class="avatar">AI</div><div class="bubble">${formatted}</div>`;
        } else {
            div.innerHTML = `<div class="bubble">${formatted}</div>`;
        }

        // Add MCQ click handlers after DOM insertion
        if (role === 'assistant') {
            this.attachMcqHandlers(div);
        }

        // BKT indicator
        if (meta.p_know_before !== undefined && meta.p_know_after !== undefined) {
            const diff = meta.p_know_after - meta.p_know_before;
            let cls = 'neutral', arrow = '→';
            if (diff > 0.05) { cls = 'up'; arrow = '↑'; }
            else if (diff < -0.05) { cls = 'down'; arrow = '↓'; }
            const pct = Math.round(meta.p_know_after * 100);
            const indicator = document.createElement('div');
            indicator.className = `bkt-indicator ${cls}`;
            indicator.textContent = `${arrow} 掌握度 ${pct}%`;
            div.querySelector('.bubble')?.appendChild(indicator);
        }

        // Guessed indicator — removed, no longer penalize MCQ-only answers
        if (meta.guessed) {
            // Silent: the backend may flag as guessed but frontend doesn't prompt
        }

        this.container.appendChild(div);
        this.container.scrollTop = this.container.scrollHeight;
    },

    formatContent(text) {
        if (!text) return '';
        // Escape HTML
        let html = text
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

        // Convert newlines to markup FIRST so MCQ regex can use <br> as anchors
        html = html
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');

        // Wrap MCQ options in clickable containers (after newline→<br> conversion)
        // Supports A. A) A、 A． etc.
        const optionSeparator = /[\.\)、．]\s*/;
        if (/\bA[\.\)、．]\s/.test(html) && /\bB[\.\)、．]\s/.test(html)) {
            html = html.replace(
                /([A-D])[\.\)、．]\s*([\s\S]+?)(?=\s*(?:[A-D][\.\)、．]\s*|$|<br|<\/p))/g,
                function(match, letter, text) {
                    const cleanText = text.trim().replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    return '<div class="mcq-option" data-option="' + letter + '" data-text="' + cleanText + '">' + letter + '. ' + text + '</div>';
                }
            );
            html = '<div class="mcq-options">' + html + '</div>';
        }

        // Mark fill-in-blank hints
        if (/_{2,}|____|空白处|填空/.test(html)) {
            html += '<div class="fill-blank-hint">请在下方输入框中填写你的答案</div>';
        }

        return html;
    },

    attachMcqHandlers(container) {
        container.querySelectorAll('.mcq-option').forEach(opt => {
            opt.addEventListener('click', () => {
                const input = document.getElementById('chat-input');
                const letter = opt.dataset.option;
                const text = opt.dataset.text || '';

                // Deselect all
                container.querySelectorAll('.mcq-option').forEach(o => o.classList.remove('selected'));
                // Select this one
                opt.classList.add('selected');

                // Remove previous auto-answer hint
                const prevHint = container.querySelector('.mcq-options + .fill-blank-hint');
                if (prevHint) prevHint.remove();

                // Auto-submit: send letter + option text so AI sees full answer
                input.value = letter + '. ' + text;
                App.sendMessage();
            });
        });
    },

    appendFeedback(feedback) {
        const div = document.createElement('div');
        div.className = 'message assistant feedback-message';

        const correct = feedback.is_correct;
        const icon = correct ? '✓' : '✗';
        const color = correct ? 'var(--green)' : 'var(--red)';
        const label = correct ? '回答正确' : '回答错误';
        const pctBefore = Math.round(feedback.p_know_before * 100);
        const pctAfter = Math.round(feedback.p_know_after * 100);
        const diff = pctAfter - pctBefore;
        const arrow = diff > 0 ? '↑' : diff < 0 ? '↓' : '→';
        const diffColor = diff > 0 ? 'var(--green)' : diff < 0 ? 'var(--red)' : 'var(--text-tertiary)';

        div.innerHTML = `
            <div class="avatar">AI</div>
            <div class="bubble feedback-bubble" style="border-left: 3px solid ${color};">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                    <span style="color:${color};font-weight:700;font-size:1rem;">${icon} ${label}</span>
                    <span style="color:var(--text-tertiary);font-size:0.8rem;">
                        正确答案：<strong style="color:var(--text);">${this.escapeOpt(feedback.correct_answer)}</strong>
                    </span>
                </div>
                <div style="color:var(--text-secondary);font-size:0.85rem;line-height:1.5;margin-bottom:8px;">
                    ${this.escapeOpt(feedback.explanation)}
                </div>
                <div style="display:flex;align-items:center;gap:6px;font-size:0.75rem;
                    background:rgba(255,255,255,0.03);padding:6px 10px;border-radius:6px;">
                    <span style="color:var(--text-tertiary);">BKT掌握度：</span>
                    <span style="color:var(--text-secondary);">${pctBefore}%</span>
                    <span style="color:${diffColor};font-weight:600;">${arrow} ${pctAfter}%</span>
                    ${diff !== 0 ? `<span style="color:var(--text-tertiary);">(${diff > 0 ? '+' : ''}${diff}%)</span>` : ''}
                </div>
            </div>
        `;
        this.container.appendChild(div);
        this.container.scrollTop = this.container.scrollHeight;
    },

    escapeOpt(text) {
        if (!text) return '';
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },

    showTyping() {
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.id = 'typing-indicator';
        div.innerHTML = `
            <div class="avatar">AI</div>
            <div class="bubble">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>`;
        this.container.appendChild(div);
        this.container.scrollTop = this.container.scrollHeight;
    },

    hideTyping() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    },
};
