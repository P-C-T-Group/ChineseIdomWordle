var mode, difficulty, game_id, max_rounds, candidate_chars, gameStatus;
var mainGameDiv, startGameDiv, candidateDivLine1, candidateDivLine2, guessDiv;

var turn = 0;
var word = [true, true, true, true];
var candidate = {};
var reverseCandidate = {};

const endMusic = new Audio('结束.wav');
const startMusic = new Audio('要开始了哟.wav')

const colorDict = {
    'correct': 'green', 
    'present': 'yellow',
    'absent': 'gray'
}

window.addEventListener('beforeunload', function (event) {
    event.preventDefault();
    event.returnValue = '';
});


// 创建游戏
function startGame()
{
    startMusic.play();
    mode = document.querySelector('input[name="mode"]:checked').value;
    difficulty = document.querySelector('input[name="difficulty"]:checked').value;
    fetch('http://192.168.10.16:8000/api/games', {
        method: 'POST', 
        headers: {
            'Content-Type': 'application/json', 
            'Authorization': 'Bearer test-token', 
        },
        body: JSON.stringify({
            'mode': mode, 
            'difficulty': difficulty
        })
    })
    .then(response => response.json())
    .then(data => {
        game_id = data['game_id'];
        max_rounds = data['max_rounds']
        candidate_chars = data['candidate_chars']
        startGameDiv = document.getElementById('startGame')
        mainGameDiv = document.getElementById('mainGame')
        guessDiv = document.getElementById('guess')
        startGameDiv.style.display='none'
        summonBox()
        summonCandidate()
        guessDiv.style.display='flex'
    })
    .catch(error => console.error('Error:', error));
}

//生成待输入区
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

//生成候选字
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

//菜单栏
function start() {
    var re = confirm("是否回到首页")
    if (re == true) {
        location.reload()
    }
}

function help() {
    window.alert("help")
}

function rank() {
    window.alert("SQL不会写, 排行榜功能暂不可用喵")
}


// 游戏逻辑
// 加词
function addWord(element) {
    var msgDiv = document.getElementById('msg');
    msgDiv.innerHTML = ''; // 清空输出栏
    if (Object.keys(candidate).includes(element.id)) {
        delWord(document.getElementById(`${turn}/${candidate[element.id]}`)) // 点击候选字删除
    } else {
        var full = true
        for (var i = 0; i <= 3; i++) {
            if (word[i]) {
                full = false;
                var wordDiv = document.getElementById(turn + '/' + i)
                wordDiv.innerHTML = element.innerHTML;
                // word是个list 用于存储每一位字符是否输入 为true代表尚未输入
                // candidate的key是候选字的id, value是输入区的位置
                word[i] = false;
                candidate[element.id] = i;
                reverseCandidate[i] = element.id;
                break;
            } else {
                continue;
            }
        }
        if (full) {
            msgDiv.innerHTML = '该提交猜测了喵';
        }
    }
}

// 点击输入区删除
function delWord(element) {
    if (element.id.split('/')[0] == turn) {
        var msgDiv = document.getElementById('msg');
        msgDiv.innerHTML = '';
        var candidateDiv = document.getElementById('c' + candidate_chars.indexOf(element.innerHTML));
        var candidateID = reverseCandidate[element.id.slice(-1)];
        delete reverseCandidate[candidate[candidateID]];
        delete candidate[candidateID];
        element.innerHTML = '';
        word[element.id[2]] = true;
    } else {
        return ;
    }
}

function guess() {
    var msgDiv = document.getElementById('msg');
    var guess = '';
    for (var i = 0; i <= 3; i++) {
        if (word[i]) {
            msgDiv.innerHTML = '我们只支持四字成语喵';
            return;
        } else {
            guess += document.getElementById(`${turn}/${i}`).innerHTML;
        }
    }
    fetch(`http://192.168.10.16:8000/api/games/${game_id}/guesses`, {
        method: 'POST', 
        headers: {
            'Content-Type': 'application/json', 
            'Authorization': 'Bearer 7sK9pR2tG5', 
        },
        body: JSON.stringify({
            'guess': guess
        })
    })
    .then(response => response.json())
    .then(data => {
        gameStatus = data['game_status'];
        if (gameStatus == 'won') {
            won(data['answer'], data['pinyin']);
        } else {
            playing(data['result']);
        }
    })
    .catch(error => console.error('Error:', error));
}

function won(ans, py) {
    endMusic.play()
    for (var i = 0; i <= 3; i ++) {
        document.getElementById(turn + '/' + i).style.backgroundColor = colorDict['correct']
    }
    turn += 1;
    document.getElementById('msg').innerHTML = turn + '回合猜出: ' + ans + '(' + py + ')';
    var re = confirm(turn + '回合猜出: ' + ans + '(' + py + ')' + "了喵, 是否重启游戏喵");
    if (re == true) {
        location.reload()
    }
}

function playing(result) {
    console.info(result)
    for (var i = 0; i <= 3; i ++) {
        document.getElementById(reverseCandidate[i]).style.backgroundColor = colorDict[result[i]['status']]
        document.getElementById(turn + '/' + i).style.backgroundColor = colorDict[result[i]['status']]
    }
    word = [true, true, true, true];
    candidate = {};
    reverseCandidate = {};
    turn += 1;
}

function hint() {
    var msgDiv = document.getElementById('msg');
    var hintLabel = document.getElementById('hints')
    fetch(`http://192.168.10.16:8000/api/games/${game_id}/hints`, {
        method: 'POST', 
        headers: {
            'Content-Type': 'application/json', 
            'Authorization': 'Bearer 7sK9pR2tG5', 
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
                hintLabel.innerHTML = data['revealed_pinyins'][0] + '   ' + data['revealed_pinyins'][1]
                msgDiv.innerHTML = '提示机会没有了喵'
            }
        }
    })
    .catch(error => console.error('Error:', error));
}