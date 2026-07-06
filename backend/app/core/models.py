from pydantic import BaseModel
from enum import Enum


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class GameMode(str, Enum):
    daily = "daily"
    unlimited = "unlimited"


class Idiom(BaseModel):
    word: str
    pinyin: str          # 带声调拼音，如 "ā bí dì yù"
    pinyin_r: str        # 不带声调拼音，如 "a bi di yu"
    explanation: str = ""


class CharFeedback(BaseModel):
    char: str
    status: str  # correct | present | absent


class Game(BaseModel):
    game_id: str
    mode: GameMode
    difficulty: Difficulty
    max_rounds: int
    candidate_chars: list[str]
    target_idiom: str
    target_pinyin: str
    guesses: list[list[CharFeedback]] = []
    game_status: str = "playing"  # playing | won | lost
    round: int = 0
    hints_used: int = 0
    max_hints: int = 2
    revealed_pinyins: list[str] = []
