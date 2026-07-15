from pydantic import BaseModel, field_validator
from typing import Optional
from app.core.models import Difficulty, GameMode, CharFeedback


class CreateGameRequest(BaseModel):
    code: int = 200
    status: str = "success"
    mode: GameMode = GameMode.unlimited
    difficulty: Difficulty = Difficulty.medium


class CreateGameResponse(BaseModel):
    code: int = 200
    status: str = "success"
    game_id: str
    mode: GameMode
    difficulty: Difficulty
    max_rounds: int
    candidate_chars: list[str]
    game_status: str
    guesses: list[list[CharFeedback]] = []


class GuessRequest(BaseModel):
    guess: str

    @field_validator("guess")
    @classmethod
    def validate_guess(cls, v):
        v = v.strip()
        if len(v) != 4:
            raise ValueError("必须输入4字成语")
        if not all('\u4e00' <= c <= '\u9fff' for c in v):
            raise ValueError("只能包含汉字")
        return v


class GuessResponse(BaseModel):
    code: int = 200
    status: str = "success"
    game_id: str
    game_status: str
    guess: str
    result: list[CharFeedback]
    round: int
    max_rounds: int
    answer: Optional[str] = None
    pinyin: Optional[str] = None
    definition: Optional[str] = None


class HintResponse(BaseModel):
    code: int = 200
    status: str = "success"
    game_id: str
    revealed_pinyins: list[str]
    hints_used: int
    max_hints: int


class GameStateResponse(BaseModel):
    code: int = 200
    status: str = "success"
    game_id: str
    mode: GameMode
    difficulty: Difficulty
    max_rounds: int
    candidate_chars: list[str]
    game_status: str
    guesses: list[list[CharFeedback]] = []
    round: int = 0
    answer: Optional[str] = None
    pinyin: Optional[str] = None
    definition: Optional[str] = None
    hints_used: int = 0
    max_hints: int = 2
    revealed_pinyins: list[str] = []


class ErrorResponse(BaseModel):
    code: int
    status: str = "fail"
    message: str
