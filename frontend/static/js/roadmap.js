const Roadmap = {
    container: document.getElementById('roadmap-nav'),

    render(data) {
        if (!data || !data.chapters) return;
        this.container.innerHTML = '';

        for (const ch of data.chapters) {
            const group = document.createElement('div');
            group.className = 'chapter-group';

            const label = document.createElement('div');
            label.className = 'chapter-label';
            label.textContent = ch.title;
            group.appendChild(label);

            for (const kp of ch.knowledge_points) {
                const node = this.createNode(kp);
                group.appendChild(node);
            }

            this.container.appendChild(group);
        }
    },

    createNode(kp) {
        const node = document.createElement('div');
        node.className = `roadmap-node ${kp.status}`;
        node.dataset.kpId = kp.id;
        node.dataset.status = kp.status;
        node.dataset.pKnow = kp.p_know;

        let icon = '○';
        if (kp.status === 'mastered') icon = '✓';
        else if (kp.status === 'needs_relearn') icon = '⚠';
        else if (kp.status === 'learning') icon = '▶';

        let badge = '未开始';
        if (kp.status === 'mastered') badge = '已掌握';
        else if (kp.status === 'needs_relearn') badge = '需重学';
        else if (kp.status === 'learning') badge = '学习中';

        if (kp.status === 'learning') {
            node.classList.add('pulse');
        }

        node.innerHTML = `
            <span class="node-icon">${icon}</span>
            <span class="node-title">${kp.title}</span>
            <span class="node-badge-mini">${badge}</span>
            <span class="node-pct">${kp.p_know}%</span>`;

        node.addEventListener('click', () => {
            App.navigateToConcept(kp.id);
        });

        return node;
    },

    updateNode(bktData) {
        const node = document.querySelector(`.roadmap-node[data-kp-id="${bktData.kp_id}"]`);
        if (!node) return;

        const pct = Math.round(bktData.p_know_after * 100);
        node.dataset.status = bktData.mastery_status;
        node.dataset.pKnow = pct;
        node.querySelector('.node-pct').textContent = pct + '%';

        let icon = '○', badge = '未开始';
        if (bktData.mastery_status === 'mastered') { icon = '✓'; badge = '已掌握'; }
        else if (bktData.mastery_status === 'needs_relearn') { icon = '⚠'; badge = '需重学'; }
        else if (bktData.mastery_status === 'learning') { icon = '▶'; badge = '学习中'; }
        node.querySelector('.node-icon').textContent = icon;
        node.querySelector('.node-badge-mini').textContent = badge;

        // Update CSS classes
        node.className = `roadmap-node ${bktData.mastery_status}`;
        if (bktData.mastery_status === 'learning') node.classList.add('pulse');
    },

    setActive(kpId) {
        document.querySelectorAll('.roadmap-node').forEach(n => n.classList.remove('active'));
        const node = document.querySelector(`.roadmap-node[data-kp-id="${kpId}"]`);
        if (node) {
            node.classList.add('active');
            // Expand parent chapter group if collapsed
            const group = node.closest('.chapter-group');
            if (group) {
                group.style.display = 'block';
            }
            node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            // Brief pulse animation
            node.style.transition = 'none';
            node.style.boxShadow = '0 0 20px rgba(6,182,212,0.3)';
            setTimeout(() => {
                node.style.transition = 'all 0.3s ease';
                node.style.boxShadow = '';
            }, 300);
        }
    },
};
