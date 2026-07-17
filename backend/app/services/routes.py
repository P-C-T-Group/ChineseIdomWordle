from fastapi import APIRouter, HTTPException, Response, Request
from app.schemas.game import (
    CreateGameRequest,
    CreateGameResponse,
    GuessRequest,
    GuessResponse,
    GameStateResponse,
    HintResponse
)
from app.services.game_service import (
    create_game,
    submit_guess,
    get_game,
    use_hint,
    load_idioms,
    ensure_game,
    reveal_game
)


router = APIRouter(prefix="/api")


def _get_client_ip(request: Request) -> str:
    """从请求中提取客户端真实 IP，支持反向代理场景"""
    # 优先使用 X-Forwarded-For（多级代理时取第一个）
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    # 其次使用 X-Real-IP
    xri = request.headers.get("X-Real-IP")
    if xri:
        return xri.strip()
    # 回退到直连 IP
    if request.client:
        return request.client.host
    return "0.0.0.0"


@router.post("/games", response_model=CreateGameResponse)
# 创建新游戏
def api_create_game(req: CreateGameRequest, request: Request, response: Response):
    client_ip = _get_client_ip(request)
    game = create_game(req.mode, req.difficulty, client_ip)
    return CreateGameResponse(
        game_id=game.game_id,
        mode=game.mode,
        difficulty=game.difficulty,
        max_rounds=game.max_rounds,
        candidate_chars=game.candidate_chars,
        game_status=game.game_status,
        guesses=game.guesses
    )


@router.post("/games/{game_id}/guesses", response_model=GuessResponse)
# 提交猜测
def api_submit_guess(game_id: str, req: GuessRequest, response: Response):
    load_idioms()
    feedback, status, round_num, answer, pinyin, explanation, error = submit_guess(
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
        game_status=status,
        answer=answer,
        pinyin=pinyin,
        explanation=explanation
    )


@router.get("/games/{game_id}/hints", response_model=HintResponse)
# 使用提示
def api_use_hint(game_id: str, response: Response):
    load_idioms()
    pinyins, explanation, error = use_hint(game_id)
    if error:
        raise HTTPException(status_code=400, detail=error)
    game = get_game(game_id)
    return HintResponse(
        game_id=game_id,
        revealed_pinyins=pinyins,
        explanation=explanation,
        hints_used=game.hints_used,
        max_hints=game.max_hints
    )


@router.get("/games/{game_id}", response_model=GameStateResponse)
# 获取游戏状态
def api_get_game(game_id: str, response: Response):
    load_idioms()

    if not ensure_game(game_id):
        raise HTTPException(status_code=400, detail="游戏不存在")

    game = get_game(game_id)

    answer = None
    pinyin = None
    explanation = None

    if game.game_status != "playing":
        answer = game.target_idiom
        pinyin = game.target_pinyin
        explanation = game.target_explanation
    if game.hints_used >= 2:
        explanation = game.target_explanation

    return GameStateResponse(
        game_id=game.game_id,
        mode=game.mode,
        difficulty=game.difficulty,
        max_rounds=game.max_rounds,
        candidate_chars=game.candidate_chars,
        game_status=game.game_status,
        guesses=game.guesses,
        round=game.round,
        answer=answer,
        pinyin=pinyin,
        explanation=explanation,
        hints_used=game.hints_used,
        max_hints=game.max_hints,
        revealed_pinyins=game.revealed_pinyins
    )


@router.get("/games/{game_id}/reveal", response_model=GameStateResponse)
# 强制揭示答案
def api_game_reveal(game_id: str, response: Response):
    load_idioms()

    if not ensure_game(game_id):
        raise HTTPException(status_code=400, detail="游戏不存在")

    game = reveal_game(game_id)

    if game.game_status != "lost":
        raise HTTPException(status_code=400, detail="本局游戏已结束,状态不为playing")

    return GameStateResponse(
        game_id=game.game_id,
        mode=game.mode,
        difficulty=game.difficulty,
        max_rounds=game.max_rounds,
        candidate_chars=game.candidate_chars,
        game_status=game.game_status,
        guesses=game.guesses,
        round=game.round,
        answer=game.target_idiom,
        pinyin=game.target_pinyin,
        hints_used=game.hints_used,
        max_hints=game.max_hints,
        revealed_pinyins=game.revealed_pinyins,
        explanation=game.target_explanation
    )
