// ========== 主题初始化：页面加载时读取本地偏好 ==========
(function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
})();

var mode, difficulty, game_id, max_rounds, candidate_chars, gameStatus;
var mainGameDiv, startGameDiv, candidateDivLine1, candidateDivLine2, guessDiv;
var turn, candidate, reverseCandidate, word;
var isSubmitting = false;
var isStarting = false;
var isContinuing = false;
var isHinting = false;
var isRevealing = false;

const endMusic = new Audio('结束.wav');
const startMusic = new Audio('要开始了哟.wav')

const colorDict = {
    'correct': 'green',
    'present': 'yellow',
    'absent': 'gray'
}

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
        // 未手动设置时，取反系统主题
        newTheme = systemIsDark ? 'light' : 'dark';
    }

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

// ========== 滚动逻辑：仅溢出时生效，右对齐保证完整可见 ==========
function scrollToCurrentTurn() {
    requestAnimationFrame(() => {
        const container = document.getElementById('mainGame');
        const currentBox = document.getElementById(turn);
        if (!container || !currentBox) return;

        const containerRect = container.getBoundingClientRect();
        const boxRect = currentBox.getBoundingClientRect();

        // 水平方向判断：当前列是否完全在容器可视区域内
        const isFullyVisible = boxRect.left >= containerRect.left
            && boxRect.right <= containerRect.right;

        // 仅在溢出时执行滚动，对齐到可视区域右边缘
        if (!isFullyVisible) {
            currentBox.scrollIntoView({
                inline: 'end',
                block: 'nearest',
                behavior: 'smooth'
            });
        }
    });
}

// ========== 通用提交接口 ==========
async function submitGuess(guessStr) {
    if (isSubmitting) return null;
    isSubmitting = true;
    try {
        const response = await fetch(`//127.0.0.1:8000/api/games/${game_id}/guesses`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-token',
            },
            body: JSON.stringify({ guess: guessStr })
        });
        return await response.json();
    } catch (error) {
        console.error('Error:', error);
        return null;
    } finally {
        isSubmitting = false;
    }
}

// 创建游戏
function startGame() {
    if (isStarting) return;
    isStarting = true;
    startMusic.play();
    mode = document.querySelector('input[name="mode"]:checked').value;
    difficulty = document.querySelector('input[name="difficulty"]:checked').value;
    fetch('//127.0.0.1:8000/api/games', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-token',
        },
        body: JSON.stringify({ mode: mode, difficulty: difficulty })
    })
        .then(response => response.json())
        .then(data => {
            turn = 0;
            word = [true, true, true, true];
            candidate = {};
            reverseCandidate = {};
            game_id = data['game_id'];
            max_rounds = data['max_rounds'];
            candidate_chars = data['candidate_chars'];
            startGameDiv = document.getElementById('startPanel');
            mainGameDiv = document.getElementById('mainGame');
            guessDiv = document.getElementById('guess');
            startGameDiv.style.display = 'none';
            summonBox();
            summonCandidate();
            localStorage.setItem('game_id', game_id);
            guessDiv.style.display = 'flex';
            document.getElementById('hints').innerHTML = '获取提示';
            document.getElementById('msg').innerHTML = '';

            scrollToCurrentTurn();
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('msg').innerHTML = '开局失败喵，请重试';
        })
        .finally(() => {
            isStarting = false;
        });
}

// 继续游戏
function continueGame() {
    if (isContinuing) return;
    var msgDiv = document.getElementById('msg');
    if (localStorage.getItem('game_id') == null) {
        msgDiv.innerHTML = '尚未找到上一局喵';
    } else {
        isContinuing = true;
        fetch(`//127.0.0.1:8000/api/games/${localStorage.getItem('game_id')}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-token',
            }
        })
            .then(response => response.json())
            .then(data => {
                game_id = data['game_id'];
                max_rounds = data['max_rounds'];
                candidate_chars = data['candidate_chars'];
                startGameDiv = document.getElementById('startPanel');
                mainGameDiv = document.getElementById('mainGame');
                guessDiv = document.getElementById('guess');
                startGameDiv.style.display = 'none';
                summonBox();
                summonCandidate();
                localStorage.setItem('game_id', game_id);
                guessDiv.style.display = 'flex';
                var hintLabel = document.getElementById('hints');
                if (data['hints_used'] == 1) {
                    hintLabel.innerHTML = data['revealed_pinyins'][0];
                    msgDiv.innerHTML = '还有一次提示机会喵';
                } else if (data['hints_used'] == 2) {
                    hintLabel.innerHTML = data['revealed_pinyins'][0] + '   ' + data['explanation'];
                    msgDiv.innerHTML = '提示机会没有了喵';
                } else {
                    hintLabel.innerHTML = '获取提示';
                }
                for (var _turn = 0; _turn < data['round']; _turn++) {
                    for (var i = 0; i <= 3; i++) {
                        document.getElementById(_turn + '/' + i).innerHTML = data['guesses'][_turn][i]['char'];
                        document.getElementById(_turn + '/' + i).style.backgroundColor = colorDict[data['guesses'][_turn][i]['status']];
                    }
                }
                word = [true, true, true, true];
                candidate = {};
                reverseCandidate = {};
                turn = data['round'];

                scrollToCurrentTurn();
            })
            .catch(error => {
                console.error('Error:', error);
                msgDiv.innerHTML = '恢复游戏失败喵，请重试';
            })
            .finally(() => {
                isContinuing = false;
            });
    }

}

// 生成待输入区
function summonBox() {
    for (var i = 0; i < max_rounds; i++) {
        mainGameDiv.innerHTML = `
            <div class="box" id=${i}>
                <div class="round-number">${i + 1}</div>
                <div class="boxes" id="${i}/0" onclick="delWord(this)"></div>
                <div class="boxes" id="${i}/1" onclick="delWord(this)"></div>
                <div class="boxes" id="${i}/2" onclick="delWord(this)"></div>
                <div class="boxes" id="${i}/3" onclick="delWord(this)"></div>
            </div>` + mainGameDiv.innerHTML
    }
}

// 生成候选字
function summonCandidate() {
    candidateDivLine1 = document.getElementById("line1");
    candidateDivLine2 = document.getElementById("line2");
    for (var i = 0; i < candidate_chars.length; i++) {
        if (i < candidate_chars.length / 2) {
            candidateDivLine1.innerHTML += `
            <div class="word" id="c${i}" onclick="addWord(this)">${candidate_chars[i]}</div>`
        } else {
            candidateDivLine2.innerHTML += `
            <div class="word" id="c${i}" onclick="addWord(this)">${candidate_chars[i]}</div>`
        }
    }
}

// 菜单栏
async function start() {
    var re = await CWDialog.confirm('是否回到首页？', {
        title: '确认返回',
        confirmText: '返回',
        cancelText: '取消'
    });
    if (re == true) {
        document.getElementById('msg').innerHTML = '';
        document.getElementById("line1").innerHTML = '';
        document.getElementById("line2").innerHTML = '';
        document.getElementById('mainGame').innerHTML = '';
        document.getElementById('guess').style.display = 'none';
        document.getElementById('startPanel').style.display = 'grid';
    }
}

// 跳转帮助页面
function help() {
    window.location.href = 'help';
}

// 跳转排行榜/日志页面
function rank() {
    window.location.href = 'top';
}

// 加词
function addWord(element) {
    var msgDiv = document.getElementById('msg');
    msgDiv.innerHTML = '';

    if (isSubmitting) return;

    if (Object.keys(candidate).includes(element.id)) {
        delWord(document.getElementById(`${turn}/${candidate[element.id]}`))
    } else {
        var full = true
        var isFirstChar = word.every(v => v);

        for (var i = 0; i <= 3; i++) {
            if (word[i]) {
                full = false;
                var wordDiv = document.getElementById(turn + '/' + i)
                wordDiv.innerHTML = element.innerHTML;
                word[i] = false;
                candidate[element.id] = i;
                reverseCandidate[i] = element.id;

                if (isFirstChar) {
                    scrollToCurrentTurn();
                }
                break;
            }
        }

        // 第5字自动提交并带入下一轮
        if (full) {
            var guessStr = '';
            for (var i = 0; i <= 3; i++) {
                guessStr += document.getElementById(`${turn}/${i}`).innerHTML;
            }

            submitGuess(guessStr).then(data => {
                if (!data) return;
                gameStatus = data['game_status'];
                if (gameStatus == 'won') {
                    won(data['answer'], data['pinyin'], data['explanation']);
                } else {
                    playing(data['result'], data);
                    if (turn < max_rounds && word[0]) {
                        var wordDiv = document.getElementById(turn + '/0');
                        wordDiv.innerHTML = element.innerHTML;
                        word[0] = false;
                        candidate[element.id] = 0;
                        reverseCandidate[0] = element.id;
                        scrollToCurrentTurn();
                    }
                }
            });
        }
    }
}

// 删除字
function delWord(element) {
    if (isSubmitting) return;
    if (element.id.split('/')[0] == turn) {
        document.getElementById('msg').innerHTML = '';
        var candidateID = reverseCandidate[element.id.slice(-1)];
        delete reverseCandidate[candidate[candidateID]];
        delete candidate[candidateID];
        element.innerHTML = '';
        word[element.id.slice(-1)] = true;
    }
}

// 手动提交
function guess() {
    var msgDiv = document.getElementById('msg');
    if (isSubmitting) return;

    var guessStr = '';
    for (var i = 0; i <= 3; i++) {
        if (word[i]) {
            msgDiv.innerHTML = '我们只猜四字成语喵';
            return;
        } else {
            guessStr += document.getElementById(`${turn}/${i}`).innerHTML;
        }
    }

    submitGuess(guessStr).then(data => {
        if (!data) return;
        gameStatus = data['game_status'];
        if (gameStatus == 'won') {
            won(data['answer'], data['pinyin'], data['explanation']);
        } else {
            playing(data['result'], data);
        }
    });
}

async function won(ans, py, explanation) {
    endMusic.play()
    for (var i = 0; i <= 3; i++) {
        document.getElementById(turn + '/' + i).style.backgroundColor = colorDict['correct']
    }
    turn += 1;
    document.getElementById('msg').innerHTML = turn + '回合猜出: ' + ans + '(' + py + ')';

    // 保存到历史记录
    saveHistory({
        game_id: game_id,
        answer: ans,
        pinyin: py,
        explanation: explanation || null,
        status: 'won',
        rounds: turn,
        max_rounds: max_rounds,
        mode: mode,
        difficulty: difficulty,
        timestamp: Date.now()
    });

    var winMsg = turn + '回合猜出: ' + ans + '(' + py + ')' + "了喵";
    if (explanation) {
        winMsg += "\n释义: " + explanation;
    }
    winMsg += "\n\n是否重启游戏喵";
    var re = await CWDialog.confirm(winMsg, {
        title: '恭喜通关',
        confirmText: '重启新游戏',
        cancelText: '关闭'
    });
    if (re == true) {
        document.getElementById('msg').innerHTML = '';
        document.getElementById("line1").innerHTML = '';
        document.getElementById("line2").innerHTML = '';
        document.getElementById('mainGame').innerHTML = '';
        document.getElementById('guess').style.display = 'none';
        document.getElementById('startPanel').style.display = 'grid';
    }
    localStorage.removeItem("game_id");
}

async function playing(result, gameData) {
    for (var i = 0; i <= 3; i++) {
        document.getElementById(reverseCandidate[i]).style.backgroundColor = colorDict[result[i]['status']]
        document.getElementById(turn + '/' + i).style.backgroundColor = colorDict[result[i]['status']]
    }
    if (turn < max_rounds - 1) {
        word = [true, true, true, true];
        candidate = {};
        reverseCandidate = {};
        turn += 1;
    } else {
        // 直接使用submitGuess返回的答案数据，不需要额外调用/reveal接口
        // 后端在最后一回合提交猜词后已经返回了答案
        saveHistory({
            game_id: game_id,
            answer: gameData['answer'],
            pinyin: gameData['pinyin'],
            explanation: gameData['explanation'] || null,
            status: 'lost',
            rounds: turn + 1,
            max_rounds: max_rounds,
            mode: mode,
            difficulty: difficulty,
            timestamp: Date.now()
        });

        document.getElementById('msg').innerHTML = '答案是: ' + gameData['answer'] + '(' + gameData['pinyin'] + ')';
        var loseMsg = "没有猜出来喵! \n答案是: " + gameData['answer'] + '(' + gameData['pinyin'] + ')';
        if (gameData['explanation']) {
            loseMsg += "\n释义: " + gameData['explanation'];
        }
        loseMsg += "\n\n是否重启游戏喵";
        var re = await CWDialog.confirm(loseMsg, {
            title: '游戏结束',
            confirmText: '重启',
            cancelText: '关闭'
        });
        if (re == true) {
            document.getElementById('msg').innerHTML = '';
            document.getElementById("line1").innerHTML = '';
            document.getElementById("line2").innerHTML = '';
            document.getElementById('mainGame').innerHTML = '';
            document.getElementById('guess').style.display = 'none';
            document.getElementById('startPanel').style.display = 'grid';
        }
        localStorage.removeItem("game_id");
    }
}

function hint() {
    if (isHinting) return;
    var msgDiv = document.getElementById('msg');
    var hintLabel = document.getElementById('hints')
    isHinting = true;
    fetch(`//127.0.0.1:8000/api/games/${game_id}/hints`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-token',
        },
    })
        .then(response => response.json())
        .then(data => {
            if (data['message'] == '提示次数已用完') {
                msgDiv.innerHTML = '提示次数用完了喵'
            } else {
                if (data['hints_used'] == 1) {
                    hintLabel.innerHTML = data['revealed_pinyins'][0]
                    msgDiv.innerHTML = '还有一次提示机会喵'
                } else {
                    hintLabel.innerHTML = data['revealed_pinyins'][0] + '   ' + data['explanation']
                    msgDiv.innerHTML = '提示机会没有了喵'
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            msgDiv.innerHTML = '获取提示失败喵，请重试';
        })
        .finally(() => {
            isHinting = false;
        });
}

// 揭晓答案
async function revealAnswer() {
    if (isSubmitting || isRevealing) return;
    isRevealing = true;
    try {
        var re = await CWDialog.confirm('确定要揭晓答案吗？这将直接判定本局为负喵！', {
            title: '确认揭晓',
            confirmText: '揭晓答案',
            cancelText: '取消',
            danger: true
        });
        if (!re) return;

        isSubmitting = true;
        var response = await fetch(`//127.0.0.1:8000/api/games/${game_id}/reveal`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-token',
            },
        });
        var data = await response.json();

        if (data['status'] === 'fail') {
            document.getElementById('msg').innerHTML = data['message'] || '揭晓失败喵';
            return;
        }

        // 标记已输入的格子为absent状态
        for (var i = 0; i <= 3; i++) {
            if (!word[i]) {
                var charDiv = document.getElementById(turn + '/' + i);
                charDiv.style.backgroundColor = colorDict['absent'];
                var candidateId = reverseCandidate[i];
                if (candidateId) {
                    document.getElementById(candidateId).style.backgroundColor = colorDict['absent'];
                }
            }
        }

        // 保存到历史记录
        saveHistory({
            game_id: game_id,
            answer: data['answer'],
            pinyin: data['pinyin'],
            explanation: data['explanation'] || null,
            status: 'lost',
            rounds: data['round'],
            max_rounds: data['max_rounds'],
            mode: mode,
            difficulty: difficulty,
            timestamp: Date.now()
        });

        document.getElementById('msg').innerHTML = '答案是: ' + data['answer'] + '(' + data['pinyin'] + ')';
        var revealMsg = "揭晓答案了喵! \n答案是: " + data['answer'] + '(' + data['pinyin'] + ')';
        if (data['explanation']) {
            revealMsg += "\n释义: " + data['explanation'];
        }
        revealMsg += "\n\n是否重启游戏喵";
        var re2 = await CWDialog.confirm(revealMsg, {
            title: '答案揭晓',
            confirmText: '重启',
            cancelText: '关闭'
        });
        if (re2 == true) {
            document.getElementById('msg').innerHTML = '';
            document.getElementById("line1").innerHTML = '';
            document.getElementById("line2").innerHTML = '';
            document.getElementById('mainGame').innerHTML = '';
            document.getElementById('guess').style.display = 'none';
            document.getElementById('startPanel').style.display = 'grid';
        }
        localStorage.removeItem("game_id");
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('msg').innerHTML = '揭晓失败喵，请重试';
    } finally {
        isSubmitting = false;
        isRevealing = false;
    }
}

// ========== 历史记录功能 ==========
const HISTORY_KEY = 'idiom_wordle_history';
const MAX_HISTORY = 50;

// 保存一局游戏到历史
function saveHistory(gameData) {
    let history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    history.unshift(gameData);
    if (history.length > MAX_HISTORY) {
        history = history.slice(0, MAX_HISTORY);
    }
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

// 获取历史记录列表
function getHistoryList() {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
}

// 清空历史记录
async function clearHistory() {
    var re = await CWDialog.confirm('确定要清空所有历史记录吗？', {
        title: '确认清空',
        confirmText: '清空',
        cancelText: '取消',
        danger: true
    });
    if (re) {
        localStorage.removeItem(HISTORY_KEY);
        renderHistory();
    }
}

// 格式化日期
function formatDate(timestamp) {
    const d = new Date(timestamp);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// 获取模式中文名
function modeName(mode) {
    return { daily: '日常挑战', unlimited: '无限模式' }[mode] || mode;
}

// 获取难度中文名
function difficultyName(diff) {
    return { easy: '简单', medium: '中等', hard: '困难' }[diff] || diff;
}

// 渲染历史列表
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

    // 统计
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

// 打开历史记录
function getHistory() {
    renderHistory();
    document.getElementById('historyModal').classList.add('active');
}

// 关闭历史记录
function closeHistory(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('historyModal').classList.remove('active');
}

// ESC 键关闭弹窗
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('historyModal');
        if (modal && modal.classList.contains('active')) {
            closeHistory();
        }
    }
});