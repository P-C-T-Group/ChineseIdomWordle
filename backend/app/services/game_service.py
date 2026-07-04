import json
import os
import uuid
import random
from datetime import date
from random import Random

from app.core.models import Difficulty, GameMode, Idiom, Game, CharFeedback
from app.core.feedback import evaluate_guess
from app.core.candidate import generate_candidates

# 难度对应的轮次配置
MAX_ROUNDS = {
    Difficulty.easy: 20,
    Difficulty.medium: 16,
    Difficulty.hard: 12,
}

# 难度对应的候选字池大小
POOL_SIZE = {
    Difficulty.easy: 10,
    Difficulty.medium: 14,
    Difficulty.hard: 20,
}

# 内存存储（数据库待定）
games: dict[str, Game] = {}
idiom_list: list[Idiom] = []


def load_idioms():
    #从 JSON 文件加载成语数据，过滤四字成语
    global idiom_list
    if idiom_list:
        return

    data_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "idiom.json")
    with open(data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    idiom_list = [Idiom(**item) for item in raw if len(item.get("word", "")) == 4]


def get_daily_idiom() -> Idiom:
    #根据日期生成每日挑战成语
    load_idioms()
    today = date.today()
    rng = Random(today.toordinal())
    return rng.choice(idiom_list)


def get_random_idiom() -> Idiom:
    #随机成语（无限模式）
    load_idioms()
    return random.choice(idiom_list)


def create_game(mode: GameMode, difficulty: Difficulty) -> Game:
    #创建新游戏
    load_idioms()

    if mode == GameMode.daily:
        target = get_daily_idiom()
    else:
        target = get_random_idiom()

    all_words = [item.word for item in idiom_list]
    candidates = generate_candidates(target.word, POOL_SIZE[difficulty], difficulty.value, all_words)

    game = Game(
        game_id=str(uuid.uuid4()),
        mode=mode,
        difficulty=difficulty,
        max_rounds=MAX_ROUNDS[difficulty],
        candidate_chars=candidates,
        target_idiom=target.word,
        target_pinyin=target.pinyin,
        guesses=[],
        status="playing",
        round=0,
    )
    games[game.game_id] = game
    return game


def submit_guess(game_id: str, guess: str) -> tuple[list[CharFeedback], str, int, str, str | None, str | None]:
    #提交猜测
    #返回: (feedback, status, round, answer, pinyin, error)
    if game_id not in games:
        return [], "", 0, "", None, "游戏不存在"

    game = games[game_id]
    if game.status != "playing":
        return [], game.status, game.round, game.target_idiom, None, "游戏已结束"

    if len(guess) != 4:
        return [], game.status, game.round, "", None, "必须输入4字成语"

    # 校验是否为合法成语
    valid_idioms = {item.word for item in idiom_list}
    if guess not in valid_idioms:
        return [], game.status, game.round, "", None, "不是有效成语"

    # 检查候选字是否足够
    guess_chars = list(guess)
    available = list(game.candidate_chars)
    for c in guess_chars:
        if c in available:
            available.remove(c)
        else:
            return [], game.status, game.round, "", None, f"字\"{c}\"不在候选字中"

    feedback = evaluate_guess(guess, game.target_idiom)
    game.guesses.append(feedback)
    game.round += 1

    answer = None
    pinyin = None

    if guess == game.target_idiom:
        game.status = "won"
        answer = game.target_idiom
    elif game.round >= game.max_rounds:
        game.status = "lost"
        answer = game.target_idiom

    if game.status != "playing":
        pinyin = game.target_pinyin

    return feedback, game.status, game.round, answer, pinyin, None


def use_hint(game_id: str) -> tuple[list[str], str | None]:
    #使用提示
    #返回: (revealed_pinyins, error)
    if game_id not in games:
        return [], "游戏不存在"
    game = games[game_id]
    if game.status != "playing":
        return [], "游戏已结束"
    if game.hints_used >= game.max_hints:
        return [], "提示次数已用完"
    
    # 随机选一个未提示过的字的拼音
    pinyins = game.target_pinyin.split()
    available_indices = [i for i, p in enumerate(pinyins) if p not in game.revealed_pinyins]
    if not available_indices:
        return [], "没有可提示的拼音了"
    
    idx = random.choice(available_indices)
    pinyin = pinyins[idx]
    game.revealed_pinyins.append(pinyin)
    game.hints_used += 1
    
    return game.revealed_pinyins, None


def get_game(game_id: str) -> Game | None:
    return games.get(game_id)