var mode, difficulty, game_id, max_rounds, candidate_chars;
var mainGameDiv, startGameDiv, candidateDivLine1, candidateDivLine2, guessDiv;

var turn = 0;
var word = [true, true, true, true];
var candidate = [];

function startGame()
{
    mode = document.querySelector('input[name="mode"]:checked').value;
    difficulty = document.querySelector('input[name="difficulty"]:checked').value;
    fetch('https://wordle.whj.zdeweb.cn/api/games', {
        method: 'POST', 
        headers: {
            'Content-Type': 'application/json', 
            'Authorization': 'Bearer 7sK9pR2tG5', 
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
    window.alert("你是第一")
}


// client

function addWord(element) {
    var msgDiv = document.getElementById('msg');
    msgDiv.innerHTML = '';
    if (candidate.includes(element.innerHTML)) {
        msgDiv.innerHTML = '这个字被玩坏了喵';
    } else {
        var full = true
        for (var i = 0; i <= 3; i++) {
            if (word[i]) {
                full = false;
                var wordDiv = document.getElementById(turn + '/' + i)
                wordDiv.innerHTML = element.innerHTML;
                word[i] = false;
                candidate.push(element.innerHTML);
                element.style.backgroundColor = "orange";
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

function delWord(element) {
    var msgDiv = document.getElementById('msg');
    msgDiv.innerHTML = '';
    console.info(candidate_chars.indexOf(element.innerHTML))
    var candidateDiv = document.getElementById('c' + candidate_chars.indexOf(element.innerHTML));
    candidateDiv.style.backgroundColor = "lightgray";
    candidate.pop(element.innerHTML);
    element.innerHTML = '';
    word[element.id[2]] = true;
}

function guess() {
    var msgDiv = document.getElementById('msg');
    for (var i = 0; i <= 3; i++) {
        if (word[i]) {
            msgDiv.innerHTML = '我们只支持四字成语喵';
            break;
        } else {
            continue;
        }
    }
    fetch(`https://wordle.whj.zdeweb.cn/api/games/${game_id}/guesses`, {
        method: 'POST', 
        headers: {
            'Content-Type': 'application/json', 
            'Authorization': 'Bearer 7sK9pR2tG5', 
        },
        body: JSON.stringify({
            'guess': candidate[0] + candidate[1] + candidate[2] + candidate[3]
        })
    })
    .then(response => response.json())
    .then(data => {
        var status = data['game_status'];
        if (status == 'won') {
            won(data['answer'], data['pinyin']);
        } else {
            playing(data['result']);
        }
    })
    .catch(error => console.error('Error:', error));
}

function won(ans, py) {

}

function playing(result) {
    console.info(result)
}