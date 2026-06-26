const Chat = {
    container: document.getElementById('chat-messages'),

    appendBubble(role, content) {
        const div = document.createElement('div');
        div.className = `message ${role}`;

        const formatted = this.formatContent(content);

        if (role === 'assistant') {
            div.innerHTML = `<div class="avatar">AI</div><div class="bubble">${formatted}</div>`;
            this.renderKatex(div.querySelector('.bubble'));
        } else {
            div.innerHTML = `<div class="bubble">${formatted}</div>`;
        }

        this.container.appendChild(div);
        this.container.scrollTop = this.container.scrollHeight;
    },

    formatContent(text) {
        if (!text) return '';
        let html = text
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

        html = html
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        if (html.trim().length > 0) {
            html = '<p>' + html + '</p>';
        }

        // Don't let katex auto-render mess with HTML in <pre> blocks
        return html;
    },

    renderKatex(container) {
        if (!container) return;
        try {
            renderMathInElement(container, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                ],
                throwOnError: false,
            });
        } catch (e) {
            // silently ignore katex errors
        }
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
