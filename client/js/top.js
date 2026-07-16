// ========== 主题初始化：页面加载时读取本地偏好 ==========
(function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
})();

// ========== 切换深浅色模式 ==========
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const systemIsDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    let newTheme;
    if (currentTheme === 'dark') {
        newTheme = 'light';
    } else if (currentTheme === 'light') {
        newTheme = 'dark';
    } else {
        newTheme = systemIsDark ? 'light' : 'dark';
    }

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

// ========== 菜单栏导航 ==========
function start() {
    window.location.href = '../';
}

function help() {
    window.location.href = '../help/';
}

function rank() {
    window.location.reload();
}

// ========== 历史记录功能 ==========
const HISTORY_KEY = 'idiom_wordle_history';

function getHistoryList() {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
}

function clearHistory() {
    if (confirm('确定要清空所有历史记录吗？')) {
        localStorage.removeItem(HISTORY_KEY);
        renderHistory();
    }
}

function formatDate(timestamp) {
    const d = new Date(timestamp);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function modeName(mode) {
    return { daily: '日常挑战', unlimited: '无限模式' }[mode] || mode;
}

function difficultyName(diff) {
    return { easy: '简单', medium: '中等', hard: '困难' }[diff] || diff;
}

function renderHistory() {
    const listEl = document.getElementById('historyList');
    const statsEl = document.getElementById('historyStats');
    const history = getHistoryList();

    if (history.length === 0) {
        listEl.innerHTML = '<div class="history-empty">暂无历史记录喵~<br>快来开始一局吧！</div>';
        statsEl.style.display = 'none';
        return;
    }

    statsEl.style.display = 'flex';

    const wonCount = history.filter(h => h.status === 'won').length;
    const totalRounds = history.filter(h => h.status === 'won').reduce((sum, h) => sum + h.rounds, 0);
    const avgRounds = wonCount > 0 ? (totalRounds / wonCount).toFixed(1) : '-';

    listEl.innerHTML = `
        <div style="margin-bottom:1rem;padding:0.8rem;background:var(--bg-secondary);border-radius:var(--radius-sm);display:flex;justify-content:space-around;flex-wrap:wrap;gap:0.5rem;text-align:center;">
            <div><div style="font-size:1.3em;font-weight:bold;color:var(--primary);">${history.length}</div><div style="font-size:0.85em;color:var(--text-secondary);">总局数</div></div>
            <div><div style="font-size:1.3em;font-weight:bold;color:var(--correct);">${wonCount}</div><div style="font-size:0.85em;color:var(--text-secondary);">胜利</div></div>
            <div><div style="font-size:1.3em;font-weight:bold;color:var(--absent);">${history.length - wonCount}</div><div style="font-size:0.85em;color:var(--text-secondary);">失败</div></div>
            <div><div style="font-size:1.3em;font-weight:bold;color:var(--present);">${avgRounds}</div><div style="font-size:0.85em;color:var(--text-secondary);">平均回合</div></div>
        </div>
    ` + history.map(h => `
        <div class="history-item">
            <div class="history-header">
                <span class="history-answer">${h.answer}</span>
                <span class="history-meta">
                    <span class="history-result ${h.status}">${h.status === 'won' ? '猜对了' : '未猜出'}</span>
                </span>
            </div>
            ${h.pinyin ? `<div class="history-pinyin">${h.pinyin}</div>` : ''}
            ${h.explanation ? `<div class="history-explanation">${h.explanation}</div>` : ''}
            <div class="history-rounds">
                ${h.status === 'won' ? `用时 ${h.rounds} 回合猜出` : `未能猜出（${h.rounds}/${h.max_rounds} 回合）`}
                ｜ ${modeName(h.mode)} · ${difficultyName(h.difficulty)}
                ｜ ${formatDate(h.timestamp)}
            </div>
        </div>
    `).join('');
}

function getHistory() {
    renderHistory();
    document.getElementById('historyModal').classList.add('active');
}

function closeHistory(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('historyModal').classList.remove('active');
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('historyModal');
        if (modal && modal.classList.contains('active')) {
            closeHistory();
        }
    }
});