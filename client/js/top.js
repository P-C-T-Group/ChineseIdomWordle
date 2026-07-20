// ========== 全局状态 ==========
const API_BASE = '/api';
const HISTORY_KEY = 'idiom_wordle_history';
const UPLOAD_TIMESTAMP_KEY = 'idiom_wordle_last_upload_ts';

let currentBoard = 'total';
let currentDifficulty = 'easy';
let currentBoardType = 'wins';
let myProfile = null;

// ========== 主题初始化 ==========
(function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
})();

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

// ========== 导航 ==========
function start() {
    window.location.href = '../';
}

function help() {
    window.location.href = '../help/';
}

function rank() {
    window.location.reload();
}

// ========== 工具函数 ==========
function modeName(mode) {
    return { daily: '日常挑战', unlimited: '无限模式' }[mode] || mode;
}

function difficultyName(diff) {
    return { easy: '简单', medium: '中等', hard: '困难' }[diff] || diff;
}

function formatDate(timestamp) {
    const d = new Date(timestamp);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function getHistoryList() {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
}

function getLastUploadTimestamp() {
    return parseInt(localStorage.getItem(UPLOAD_TIMESTAMP_KEY) || '0');
}

function setLastUploadTimestamp() {
    localStorage.setItem(UPLOAD_TIMESTAMP_KEY, String(Date.now()));
}

// API请求封装
async function apiFetch(url, options = {}) {
    const defaultOptions = {
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-token'
        }
    };
    
    const merged = { ...defaultOptions, ...options };
    if (merged.body && typeof merged.body === 'object') {
        merged.body = JSON.stringify(merged.body);
    }
    
    const resp = await fetch(API_BASE + url, merged);
    
    // 处理空响应（如204 No Content）
    let data = {};
    const text = await resp.text();
    if (text) {
        try {
            data = JSON.parse(text);
        } catch (e) {
            data = { message: text };
        }
    }
    
    if (!resp.ok || (data.code && data.code >= 400)) {
        throw new Error(data.detail || data.message || `请求失败 (${resp.status})`);
    }
    return data;
}

// ========== 页面初始化 ==========
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await loadMyProfile();
    } catch (e) {
        console.log('加载存档失败:', e);
        myProfile = null;
        renderProfile();
    }
    try {
        await loadLeaderboard();
    } catch (e) {
        console.log('加载排行榜失败:', e);
        const listEl = document.getElementById('lbList');
        if (listEl) listEl.innerHTML = `<div class="empty">加载失败: ${e.message}</div>`;
    }
});

// ========== 切换功能 ==========
function switchBoard(board) {
    currentBoard = board;
    document.querySelectorAll('.lbTab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.board === board);
    });
    
    document.getElementById('totalBoardTabs').style.display = board === 'total' ? 'flex' : 'none';
    document.getElementById('dailyDate').style.display = board === 'daily' ? 'block' : 'none';
    
    loadLeaderboard();
}

function switchDifficulty(diff) {
    currentDifficulty = diff;
    document.querySelectorAll('.lbDiffBtn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.diff === diff);
    });
    loadLeaderboard();
}

function switchBoardType(type) {
    currentBoardType = type;
    document.querySelectorAll('.boardTypeBtn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.type === type);
    });
    loadLeaderboard();
}

// ========== 加载用户存档 ==========
async function loadMyProfile() {
    try {
        const data = await apiFetch('/leaderboard/profile/me');
        myProfile = data.profile;
    } catch (e) {
        myProfile = null;
    }
    renderProfile();
}

function renderProfile() {
    const profileCard = document.getElementById('profileCard');
    const noProfileCard = document.getElementById('noProfileCard');
    
    if (!myProfile) {
        profileCard.style.display = 'none';
        noProfileCard.style.display = 'block';
        return;
    }
    
    profileCard.style.display = 'block';
    noProfileCard.style.display = 'none';
    
    document.getElementById('profileName').textContent = myProfile.username;
    document.getElementById('profileId').textContent = `ID: ${myProfile.user_id}`;
    document.getElementById('profileLocation').textContent = `📍 ${myProfile.ip_location}`;
    
    const statsEl = document.getElementById('profileStats');
    const diffs = [
        { key: 'easy', name: '简单' },
        { key: 'medium', name: '中等' },
        { key: 'hard', name: '困难' }
    ];
    
    statsEl.innerHTML = diffs.map(d => {
        const total = myProfile[`${d.key}_total`] || 0;
        const won = myProfile[`${d.key}_won`] || 0;
        const avgRounds = myProfile[`${d.key}_avg_rounds`] || 0;
        const winRate = myProfile[`${d.key}_win_rate`] || 0;
        
        return `
            <div class="statBlock">
                <div class="diffLabel">${d.name}</div>
                <div class="statNumbers">
                    <div class="statItem">
                        <div class="statValue">${total}</div>
                        <div class="statLabel">总局</div>
                    </div>
                    <div class="statItem">
                        <div class="statValue">${won}</div>
                        <div class="statLabel">胜利</div>
                    </div>
                    <div class="statItem">
                        <div class="statValue">${(winRate * 100).toFixed(1)}%</div>
                        <div class="statLabel">胜率</div>
                    </div>
                    <div class="statItem">
                        <div class="statValue">${avgRounds ? avgRounds.toFixed(1) : '-'}</div>
                        <div class="statLabel">均回合</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// ========== 加载排行榜 ==========
async function loadLeaderboard() {
    const listEl = document.getElementById('lbList');
    const myRankEl = document.getElementById('myRank');
    
    listEl.innerHTML = '<div class="loading">加载中...</div>';
    myRankEl.style.display = 'none';
    
    try {
        let data;
        if (currentBoard === 'daily') {
            data = await apiFetch(`/leaderboard/${currentDifficulty}/daily`);
            renderDailyBoard(data, myRankEl);
        } else {
            data = await apiFetch(`/leaderboard/${currentDifficulty}`);
            renderTotalBoard(data, myRankEl);
        }
    } catch (e) {
        listEl.innerHTML = `<div class="empty">加载失败: ${e.message}</div>`;
    }
}

function renderTotalBoard(data, myRankEl) {
    const listEl = document.getElementById('lbList');
    let boardData, valueLabel, valueFormatter;
    
    switch (currentBoardType) {
        case 'wins':
            boardData = data.wins;
            valueLabel = '胜利';
            valueFormatter = v => v;
            break;
        case 'win_rate':
            boardData = data.win_rate;
            valueLabel = '胜率';
            valueFormatter = v => v + '%';
            break;
        case 'avg_rounds':
            boardData = data.avg_rounds;
            valueLabel = '回合';
            valueFormatter = v => v.toFixed(2);
            break;
    }
    
    if (!boardData || boardData.length === 0) {
        listEl.innerHTML = '<div class="empty">暂无排行数据</div>';
        return;
    }
    
    const myUserId = myProfile?.user_id;
    
    listEl.innerHTML = boardData.map((entry, idx) => {
        const isMe = entry.user_id === myUserId;
        const rankClass = entry.rank <= 3 ? `rank-${entry.rank}` : '';
        
        return `
            <div class="lbItem ${isMe ? 'me' : ''}">
                <div class="lbRank ${rankClass}">${entry.rank}</div>
                <div class="lbUserInfo">
                    <div class="lbUsername">${escapeHtml(entry.username)}</div>
                    <div class="lbMeta">
                        <span class="lbUserId">${entry.user_id}</span>
                        <span>📍 ${escapeHtml(entry.ip_location)}</span>
                        <span>${entry.won_games}/${entry.total_games}局</span>
                    </div>
                </div>
                <div class="lbValue">
                    ${valueFormatter(entry.value)}
                    <span class="unit">${valueLabel}</span>
                </div>
            </div>
        `;
    }).join('');
    
    const myRank = data.my_rank?.[currentBoardType];
    if (myProfile && myRank && myRank > 100) {
        const myStats = myProfile;
        let myValue;
        switch (currentBoardType) {
            case 'wins':
                myValue = myStats[`${currentDifficulty}_won`] || 0;
                break;
            case 'win_rate':
                const total = myStats[`${currentDifficulty}_total`] || 0;
                const won = myStats[`${currentDifficulty}_won`] || 0;
                myValue = total > 0 ? ((won / total) * 100).toFixed(1) + '%' : '0%';
                break;
            case 'avg_rounds':
                const w = myStats[`${currentDifficulty}_won`] || 0;
                const r = myStats[`${currentDifficulty}_win_rounds`] || 0;
                myValue = w > 0 ? (r / w).toFixed(2) : '-';
                break;
        }
        
        myRankEl.style.display = 'block';
        myRankEl.innerHTML = `
            <div class="lbItem me">
                <div class="lbRank">${myRank}</div>
                <div class="lbUserInfo">
                    <div class="lbUsername">${escapeHtml(myProfile.username)}（您）</div>
                    <div class="lbMeta">
                        <span class="lbUserId">${myProfile.user_id}</span>
                        <span>📍 ${escapeHtml(myProfile.ip_location)}</span>
                    </div>
                </div>
                <div class="lbValue">
                    ${myValue}
                    <span class="unit">${valueLabel}</span>
                </div>
            </div>
        `;
    }
}

function renderDailyBoard(data, myRankEl) {
    const listEl = document.getElementById('lbList');
    const boardData = data.daily;
    
    if (!boardData || boardData.length === 0) {
        listEl.innerHTML = '<div class="empty">今日暂无日榜数据，快来完成每日挑战吧！</div>';
        return;
    }
    
    const myUserId = myProfile?.user_id;
    
    listEl.innerHTML = boardData.map(entry => {
        const isMe = entry.user_id === myUserId;
        const rankClass = entry.rank <= 3 ? `rank-${entry.rank}` : '';
        
        return `
            <div class="lbItem ${isMe ? 'me' : ''}">
                <div class="lbRank ${rankClass}">${entry.rank}</div>
                <div class="lbUserInfo">
                    <div class="lbUsername">${escapeHtml(entry.username)}</div>
                    <div class="lbMeta">
                        <span class="lbUserId">${entry.user_id}</span>
                        <span>📍 ${escapeHtml(entry.ip_location)}</span>
                    </div>
                </div>
                <div class="lbValue">
                    ${entry.rounds}
                    <span class="unit">回合</span>
                </div>
            </div>
        `;
    }).join('');
    
    const myRank = data.my_rank;
    if (myProfile && myRank && myRank > 100) {
        myRankEl.style.display = 'block';
        myRankEl.innerHTML = `
            <div class="lbItem me">
                <div class="lbRank">${myRank}</div>
                <div class="lbUserInfo">
                    <div class="lbUsername">${escapeHtml(myProfile.username)}（您）</div>
                    <div class="lbMeta">
                        <span class="lbUserId">${myProfile.user_id}</span>
                        <span>📍 ${escapeHtml(myProfile.ip_location)}</span>
                    </div>
                </div>
                <div class="lbValue">
                    -
                    <span class="unit">回合</span>
                </div>
            </div>
        `;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== 上传战绩 ==========
function showUploadDialog() {
    const history = getHistoryList();
    const modal = document.getElementById('uploadModal');
    const titleEl = document.getElementById('uploadModalTitle');
    const usernameInput = document.getElementById('usernameInput');
    
    if (myProfile) {
        titleEl.textContent = '追加新战绩';
        usernameInput.value = '';
        usernameInput.placeholder = '留空则不修改用户名';
    } else {
        titleEl.textContent = '上传战绩创建存档';
        usernameInput.value = '';
        usernameInput.placeholder = '输入您的用户名';
    }
    
    const statsEl = document.getElementById('uploadStats');
    if (history.length === 0) {
        statsEl.innerHTML = '<p style="color: var(--absent);">本地没有历史记录</p>';
    } else {
        const wonCount = history.filter(h => h.status === 'won').length;
        if (myProfile) {
            const lastTs = getLastUploadTimestamp();
            const newRecords = history.filter(h => h.timestamp > lastTs);
            const newWon = newRecords.filter(h => h.status === 'won').length;
            statsEl.innerHTML = `
                <p><strong>新战绩统计：</strong></p>
                <p>自上次上传以来新增 ${newRecords.length} 局，胜利 ${newWon} 局</p>
                <p style="font-size:0.85em;color:var(--text-secondary);">系统将自动只上传新记录，避免重复统计</p>
            `;
        } else {
            statsEl.innerHTML = `
                <p><strong>本地记录统计：</strong></p>
                <p>共 ${history.length} 局，胜利 ${wonCount} 局，失败 ${history.length - wonCount} 局</p>
            `;
        }
    }
    
    modal.classList.add('active');
    usernameInput.focus();
}

function closeUploadModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('uploadModal').classList.remove('active');
}

async function doUpload() {
    const username = document.getElementById('usernameInput').value.trim();
    const history = getHistoryList();
    
    if (history.length === 0) {
        await CWDialog.alert('本地没有历史记录，无法上传');
        return;
    }
    
    if (!myProfile && !username) {
        await CWDialog.alert('请输入用户名');
        return;
    }
    
    // 筛选记录：追加模式只传新记录，首次上传传全部
    let recordsToUpload = history;
    if (myProfile) {
        const lastTs = getLastUploadTimestamp();
        recordsToUpload = history.filter(h => h.timestamp > lastTs);
        if (recordsToUpload.length === 0) {
            await CWDialog.alert('没有新的战绩记录需要追加');
            return;
        }
    }
    
    const records = recordsToUpload.map(h => ({
        game_id: h.gameId || `local_${h.timestamp}`,
        mode: h.mode,
        difficulty: h.difficulty,
        status: h.status,
        rounds: h.rounds,
        timestamp: h.timestamp
    }));
    
    try {
        let result;
        if (myProfile) {
            result = await apiFetch('/leaderboard/append', {
                method: 'POST',
                body: { username, records }
            });
        } else {
            result = await apiFetch('/leaderboard/upload', {
                method: 'POST',
                body: { username, records }
            });
        }
        
        await CWDialog.alert(result.message || '上传成功！', { title: '成功' });
        setLastUploadTimestamp();
        closeUploadModal();
        await loadMyProfile();
        await loadLeaderboard();
    } catch (e) {
        await CWDialog.alert('上传失败: ' + e.message);
    }
}

async function confirmDeleteProfile() {
    const ok = await CWDialog.confirm('确定要删除您的存档吗？此操作不可撤销！', {
        title: '删除存档',
        confirmText: '删除',
        danger: true
    });
    
    if (ok) {
        try {
            await apiFetch('/leaderboard/profile/delete', { method: 'POST' });
            await CWDialog.alert('存档已删除', { title: '成功' });
            await loadMyProfile();
            await loadLeaderboard();
        } catch (e) {
            await CWDialog.alert('删除失败: ' + e.message);
        }
    }
}

// ========== 历史记录 ==========
function renderHistory() {
    const listEl = document.getElementById('historyList');
    const footerEl = document.getElementById('historyFooter');
    const history = getHistoryList();

    if (history.length === 0) {
        listEl.innerHTML = '<div class="history-empty">暂无历史记录喵~<br>快来开始一局吧！</div>';
        footerEl.style.display = 'none';
        return;
    }

    footerEl.style.display = 'flex';

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
                <span class="history-answer">${h.answer || '(本局答案)'}</span>
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

async function clearHistory() {
    const ok = await CWDialog.confirm('确定要清空所有本地历史记录吗？（云端存档不受影响）', {
        title: '确认清空',
        confirmText: '清空',
        danger: true
    });
    if (ok) {
        localStorage.removeItem(HISTORY_KEY);
        renderHistory();
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        ['historyModal', 'uploadModal'].forEach(id => {
            const modal = document.getElementById(id);
            if (modal && modal.classList.contains('active')) {
                modal.classList.remove('active');
            }
        });
    }
});
