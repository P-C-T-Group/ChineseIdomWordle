from fastapi import APIRouter, HTTPException, Response
from app.schemas.game import (
    CreateGameRequest, CreateGameResponse,
    GuessRequest, GuessResponse,
    GameStateResponse, HintResponse
)
from app.services.game_service import (
    create_game, submit_guess, get_game, use_hint, idiom_list, load_idioms
)

router = APIRouter(prefix="/api")


@router.post("/games", response_model=CreateGameResponse)
def api_create_game(req: CreateGameRequest, response: Response):
    game = create_game(req.mode, req.difficulty)
    return CreateGameResponse(
        game_id=game.game_id,
        mode=game.mode,
        difficulty=game.difficulty,
        max_rounds=game.max_rounds,
        candidate_chars=game.candidate_chars,
        status=game.status,
        guesses=game.guesses
    )


@router.post("/games/{game_id}/guesses", response_model=GuessResponse)
def api_submit_guess(game_id: str, req: GuessRequest, response: Response):
    load_idioms()
    feedback, status, round_num, answer, pinyin, error = submit_guess(
        game_id, req.guess)
    if error:
        raise HTTPException(status_code=400, detail=error)

    game = get_game(game_id)

    return GuessResponse(
        game_id=game_id,
        guess=req.guess,
        result=feedback,
        round=round_num,
        max_rounds=game.max_rounds,
        status=status,
        answer=answer,
        pinyin=pinyin
    )


@router.post("/games/{game_id}/hints", response_model=HintResponse)
def api_use_hint(game_id: str, response: Response):
    load_idioms()
    pinyins, error = use_hint(game_id)
    if error:
        raise HTTPException(status_code=400, detail=error)
    game = get_game(game_id)
    return HintResponse(
        game_id=game_id,
        revealed_pinyins=pinyins,
        hints_used=game.hints_used,
        max_hints=game.max_hints
    )


@router.get("/games/{game_id}", response_model=GameStateResponse)
def api_get_game(game_id: str, response: Response):
    load_idioms()
    game = get_game(game_id)

    answer = None
    pinyin = None

    if game.status != "playing":
        answer = game.target_idiom
        pinyin = game.target_pinyin

    return GameStateResponse(
        game_id=game.game_id,
        mode=game.mode,
        difficulty=game.difficulty,
        max_rounds=game.max_rounds,
        candidate_chars=game.candidate_chars,
        status=game.status,
        guesses=game.guesses,
        round=game.round,
        answer=answer,
        pinyin=pinyin,
        hints_used=game.hints_used,
        max_hints=game.max_hints,
        revealed_pinyins=game.revealed_pinyins
    )
