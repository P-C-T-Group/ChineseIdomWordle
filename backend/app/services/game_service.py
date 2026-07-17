import json
import os
import uuid
import random
from datetime import date
from random import Random

from app.core.models import Difficulty, GameMode, Idiom, Game, CharFeedback
from app.core.feedback import evaluate_guess
from app.core.candidate import generate_candidates
from app.database import db_manager

# 难度对应的轮次配置
MAX_ROUNDS = {
    Difficulty.easy: 12,
    Difficulty.medium: 10,
    Difficulty.hard: 8,
}

# 难度对应的候选字池大小
POOL_SIZE = {
    Difficulty.easy: 10,
    Difficulty.medium: 14,
    Difficulty.hard: 20,
}

# 成语库
# idiom_list: list[Idiom] = []
easy_idiom_list: list[Idiom] = []
medium_idiom_list: list[Idiom] = []
hard_idiom_list: list[Idiom] = []
difficulty_dict: dict[str, list[Idiom]]

# 空游戏
NONEGAME = Game(
    game_id='none',
    mode=GameMode("daily"),
    difficulty=Difficulty("medium"),
    max_rounds=0,
    candidate_chars=[],
    target_idiom='',
    target_pinyin='',
    guesses=[],
    game_status="playing",
    round=0,
)


def load_idioms():
    # 从 JSON 文件加载成语数据，过滤四字成语
    # global idiom_list
    global easy_idiom_list, medium_idiom_list, hard_idiom_list, difficulty_dict
    if easy_idiom_list and medium_idiom_list and hard_idiom_list:
        return

    easy_data_path = os.path.join(os.path.dirname(
        __file__), "..", "..", "..", "data", "easy.json")
    with open(easy_data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    easy_idiom_list = [Idiom(**item)
                       for item in raw if len(item.get("word", "")) == 4]

    medium_data_path = os.path.join(os.path.dirname(
        __file__), "..", "..", "..", "data", "medium.json")
    with open(medium_data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    medium_idiom_list = [Idiom(**item)
                         for item in raw if len(item.get("word", "")) == 4]

    hard_data_path = os.path.join(os.path.dirname(
        __file__), "..", "..", "..", "data", "hard.json")
    with open(hard_data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    hard_idiom_list = [Idiom(**item)
                       for item in raw if len(item.get("word", "")) == 4]

    difficulty_dict = {
        'easy': easy_idiom_list,
        'medium': medium_idiom_list,
        'hard': hard_idiom_list
    }


def get_daily_idiom(difficulty: Difficulty) -> Idiom:
    global difficulty_dict
    # 根据日期生成每日挑战成语
    load_idioms()
    # 判断是否4月1日
    is_april_fool = (date.today().month == 4 and date.today().day == 1)
    if is_april_fool:
        return Idiom(
            word="啊舞萌痴",
            pinyin="ā wǔ méng chī",
            pinyin_r="a wu meng chi",
            explanation="愚人节快乐，恭喜触发限定啦！")
    else:
        today = date.today()
        rng = Random(today.toordinal())
        return rng.choice(difficulty_dict[difficulty.value])


def get_random_idiom(difficulty) -> Idiom:
    global difficulty_dict
    # 随机成语（无限模式）
    load_idioms()
    return random.choice(difficulty_dict[difficulty.value])


def create_game(mode: GameMode, difficulty: Difficulty) -> Game:
    # 创建新游戏
    load_idioms()

    if mode == GameMode.daily:
        target = get_daily_idiom(difficulty)
    else:
        target = get_random_idiom(difficulty)
    all_words = [item.word for item in difficulty_dict[difficulty.value]]
    candidates = generate_candidates(
        target.word, POOL_SIZE[difficulty], difficulty.value, all_words)

    game = Game(
        game_id=str(uuid.uuid4()),
        mode=mode,
        difficulty=difficulty,
        max_rounds=MAX_ROUNDS[difficulty],
        candidate_chars=candidates,
        target_idiom=target.word,
        target_pinyin=target.pinyin,
        target_explanation=target.explanation,
        guesses=[],
        game_status="playing",
        round=0
    )
    db_manager.save_game(game)
    return game


def submit_guess(game_id: str, guess: str) -> tuple[list[CharFeedback], str, int, str | None, str | None, str | None, str | None]:
    # 提交猜测
    # 返回: (feedback, status, round, answer, pinyin, explanation, error)
    game = db_manager.load_game(game_id)
    if game is None:
        return [], "", 0, "", None, None, "游戏不存在"

    if game.game_status != "playing":
        return [], game.game_status, game.round, game.target_idiom, game.target_pinyin, game.target_explanation, "游戏已结束"

    if len(guess) != 4:
        return [], game.game_status, game.round, "", None, None, "必须输入4字成语"

    # 校验是否为合法成语-为降低游戏难度而关闭，提供给玩家“暴力猜词“的可能性
    # valid_idioms = {item.word for item in idiom_list}
    # if guess not in valid_idioms:
    #     return [], game.game_status, game.round, "", None, "不是有效成语"

    # 检查候选字是否足够
    guess_chars = list(guess)
    available = list(game.candidate_chars)
    for c in guess_chars:
        if c in available:
            available.remove(c)
        else:
            return [], game.game_status, game.round, "", None, None, f"字\"{c}\"不在候选字中"

    feedback = evaluate_guess(guess, game.target_idiom)
    game.guesses.append(feedback)
    game.round += 1

    answer = None
    pinyin = None
    explanation = None

    if guess == game.target_idiom:
        game.game_status = "won"
        answer = game.target_idiom
    elif game.round >= game.max_rounds:
        game.game_status = "lost"
        answer = game.target_idiom

    if game.game_status != "playing":
        pinyin = game.target_pinyin
        explanation = game.target_explanation

    db_manager.save_game(game)
    return feedback, game.game_status, game.round, answer, pinyin, explanation, None


def use_hint(game_id: str) -> tuple[list[str], str | None, str | None]:
    # 使用提示
    # 返回: (revealed_pinyins, explanation, error)
    game = db_manager.load_game(game_id)
    if game is None:
        return [], None, "游戏不存在"
    if game.game_status != "playing":
        return [], None, "游戏已结束"
    if game.hints_used >= game.max_hints:
        return [], None, "提示次数已用完"

    # 随机选一个未提示过的字的拼音
    pinyins = game.target_pinyin.split()
    available_indices = [i for i, p in enumerate(
        pinyins) if p not in game.revealed_pinyins]
    if not available_indices:
        return [], None, "没有可提示的拼音了"

    game.hints_used += 1
    if game.hints_used == 1:
        idx = random.choice(available_indices)
        pinyin = pinyins[idx]
        game.revealed_pinyins.append(pinyin)
        db_manager.save_game(game)
        return game.revealed_pinyins, None, None
    elif game.hints_used == 2:
        db_manager.save_game(game)
        return game.revealed_pinyins, game.target_explanation, None
    else:
        idx = random.choice(available_indices)
        pinyin = pinyins[idx]
        game.revealed_pinyins.append(pinyin)
        db_manager.save_game(game)
        return game.revealed_pinyins, game.target_explanation, None


def get_game(game_id: str) -> Game:
    # 获取游戏状态
    game = db_manager.load_game(game_id)
    if game is None:
        game = NONEGAME
    return game


def ensure_game(game_id: str) -> bool:
    # 确保游戏存在的小工具
    return db_manager.game_exists(game_id)


def reveal_game(game_id: str) -> Game | None:
    # 强制揭晓答案（判负），返回更新后的 Game 或 None（不存在/已结束）
    game = db_manager.load_game(game_id)
    if game is None:
        return None
    if game.game_status != "playing":
        return game
    game.game_status = "lost"
    db_manager.save_game(game)
    return game
