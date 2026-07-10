var mode, difficulty, game_id, max_rounds, candidate_chars;

function startGame()
{
    mode = document.getElementById('mode').value;
    difficulty = document.getElementById('difficulty').value;

    fetch('https://wordle.whj.zdeweb.cn/api/games', {
        method: 'POST', 
        headers: {
            'Content-Type': 'application/json', 
            'Authorization': 'Bearer exchangeable', 
            //'Access-Control-Allow-Origin': '*', 
            //'Access-Control-Allow-Headers': 'Content-Type, api_key, Authorization'
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
    })
    .catch(error => console.error('Error:', error));
}

function start()
{
window.alert("さ，はじまるよ！")
}

function help()
{
    window.alert("help")
}

function rank()
{
    window.alert("你是第一")
}