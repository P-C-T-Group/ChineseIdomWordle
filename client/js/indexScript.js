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
                'Authorization': 'Bearer 7sK9pR2tG5',
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
        .catch(error => console.error('Error:', error));
}

// 继续游戏
function continueGame() {
    var msgDiv = document.getElementById('msg');
    if (localStorage.getItem('game_id') == null) {
        msgDiv.innerHTML = '尚未找到上一局喵';
    } else {
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
                        document.getElementById(_turn + '/' + i).innerHTML = data['guesses'][_turn][i]['char']
                        document.getElementById(_turn + '/' + i).style.backgroundColor = colorDict[data['guesses'][_turn][i]['status']];
                    }
                }
                word = [true, true, true, true];
                candidate = {};
                reverseCandidate = {};
                turn = data['round'];

                scrollToCurrentTurn();
            })
            .catch(error => console.error('Error:', error));
    }

}

// 生成待输入区
function summonBox() {
    for (var i = 0; i < max_rounds; i++) {
        mainGameDiv.innerHTML += `
            <div class="box" id=${i}>
                <div class="boxes" id="${i}/0" onclick="delWord(this)"></div>
                <div class="boxes" id="${i}/1" onclick="delWord(this)"></div>
                <div class="boxes" id="${i}/2" onclick="delWord(this)"></div>
                <div class="boxes" id="${i}/3" onclick="delWord(this)"></div>
            </div>`
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
function start() {
    var re = confirm("是否回到首页");
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
    window.location.href = 'logs';
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
                    won(data['answer'], data['pinyin']);
                } else {
                    playing(data['result']);
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
            msgDiv.innerHTML = '我们只支持四字成语喵';
            return;
        } else {
            guessStr += document.getElementById(`${turn}/${i}`).innerHTML;
        }
    }

    submitGuess(guessStr).then(data => {
        if (!data) return;
        gameStatus = data['game_status'];
        if (gameStatus == 'won') {
            won(data['answer'], data['pinyin']);
        } else {
            playing(data['result']);
        }
    });
}

function won(ans, py) {
    endMusic.play()
    for (var i = 0; i <= 3; i++) {
        document.getElementById(turn + '/' + i).style.backgroundColor = colorDict['correct']
    }
    turn += 1;
    document.getElementById('msg').innerHTML = turn + '回合猜出: ' + ans + '(' + py + ')';
    var re = confirm(turn + '回合猜出: ' + ans + '(' + py + ')' + "了喵, 是否重启游戏喵");
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

function playing(result) {
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
        var re = confirm("没有猜出来喵, 是否重启游戏喵");
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
    var msgDiv = document.getElementById('msg');
    var hintLabel = document.getElementById('hints')
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
        .catch(error => console.error('Error:', error));
}