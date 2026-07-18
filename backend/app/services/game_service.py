import json
import uuid
import random
from datetime import date
from random import Random

from app.core.models import Difficulty, GameMode, Idiom, Game, CharFeedback
from app.core.feedback import evaluate_guess
from app.core.candidate import generate_candidates
from app.core.config import get_settings
from app.database import db_manager

# 成语库
# idiom_list: list[Idiom] = []
easy_idiom_list: list[Idiom] = []
medium_idiom_list: list[Idiom] = []
hard_idiom_list: list[Idiom] = []
difficulty_dict: dict[str, list[Idiom]]

# 空游戏
NONEGAME = Game(
    game_id='none',
    create_ip='0.0.0.0',
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


def _difficulty_settings(difficulty: Difficulty):
    """从统一配置获取指定难度的游戏参数"""
    game_cfg = get_settings().game
    return {
        Difficulty.easy: game_cfg.easy,
        Difficulty.medium: game_cfg.medium,
        Difficulty.hard: game_cfg.hard,
    }[difficulty]


def get_max_rounds(difficulty: Difficulty) -> int:
    return _difficulty_settings(difficulty).max_rounds


def get_pool_size(difficulty: Difficulty) -> int:
    return _difficulty_settings(difficulty).candidate_count


def get_max_hints(difficulty: Difficulty) -> int:
    return _difficulty_settings(difficulty).max_hints


def load_idioms():
    # 从 JSON 文件加载成语数据，过滤四字成语；路径已由 Settings 统一解析为绝对路径
    global easy_idiom_list, medium_idiom_list, hard_idiom_list, difficulty_dict
    if easy_idiom_list and medium_idiom_list and hard_idiom_list:
        return

    lib_cfg = get_settings().idiom_library

    def _load(path) -> list[Idiom]:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Idiom(**item) for item in raw if len(item.get("word", "")) == 4]

    easy_idiom_list = _load(lib_cfg.easy_resolved)
    medium_idiom_list = _load(lib_cfg.medium_resolved)
    hard_idiom_list = _load(lib_cfg.hard_resolved)

    difficulty_dict = {
        'easy': easy_idiom_list,
        'medium': medium_idiom_list,
        'hard': hard_idiom_list
    }


def reload_idioms() -> int:
    """强制清空缓存并重新加载成语库；返回加载后的成语总数（三个难度之和）。

    在配置文件（idiom_library 路径）或字库内容变更后调用，使新成语库立即生效。
    """
    global easy_idiom_list, medium_idiom_list, hard_idiom_list, difficulty_dict
    easy_idiom_list = []
    medium_idiom_list = []
    hard_idiom_list = []
    difficulty_dict = {}
    load_idioms()
    return len(easy_idiom_list) + len(medium_idiom_list) + len(hard_idiom_list)


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


def create_game(mode: GameMode, difficulty: Difficulty, create_ip: str = "0.0.0.0") -> Game:
    # 创建新游戏
    load_idioms()

    if mode == GameMode.daily:
        target = get_daily_idiom(difficulty)
    else:
        target = get_random_idiom(difficulty)
    all_words = [item.word for item in difficulty_dict[difficulty.value]]
    candidates = generate_candidates(
        target.word, get_pool_size(difficulty), difficulty.value, all_words)

    game = Game(
        game_id=str(uuid.uuid4()),
        create_ip=create_ip,
        mode=mode,
        difficulty=difficulty,
        max_rounds=get_max_rounds(difficulty),
        candidate_chars=candidates,
        target_idiom=target.word,
        target_pinyin=target.pinyin,
        target_explanation=target.explanation,
        guesses=[],
        game_status="playing",
        round=0,
        max_hints=get_max_hints(difficulty)
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

    game.hints_used += 1

    if game.hints_used == 1 and game.max_hints == 1:
        # max_hints=1：唯一一次提示只给释义，不揭示拼音
        db_manager.save_game(game)
        return game.revealed_pinyins, game.target_explanation, None

    if game.hints_used == 1:
        # 第1次提示：揭示1个拼音，无释义
        if not available_indices:
            game.hints_used -= 1
            db_manager.save_game(game)
            return [], None, "没有可提示的拼音了"
        idx = random.choice(available_indices)
        game.revealed_pinyins.append(pinyins[idx])
        db_manager.save_game(game)
        return game.revealed_pinyins, None, None

    if game.hints_used == 2:
        # 第2次提示：只给释义，不揭示新拼音
        db_manager.save_game(game)
        return game.revealed_pinyins, game.target_explanation, None

    # 第3次及以后：每次揭示1个拼音（若还有），附带释义
    if available_indices:
        idx = random.choice(available_indices)
        game.revealed_pinyins.append(pinyins[idx])
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
