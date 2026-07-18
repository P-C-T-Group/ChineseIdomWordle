from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from app.schemas.game import (
    CreateGameRequest,
    CreateGameResponse,
    GuessRequest,
    GuessResponse,
    GameStateResponse,
    HintResponse,
    ErrorResponse,
)
from app.schemas.config import CleanupMode
from app.services.game_service import (
    create_game,
    submit_guess,
    get_game,
    use_hint,
    load_idioms,
    reload_idioms,
    ensure_game,
    reveal_game
)
from app.database import db_manager
from app.core.security import get_client_ip, is_admin_allowed
from app.core.config import get_settings, reload_settings
from app.core.logging_setup import setup_logging
import hashlib


def _admin_error(status_code: int, message: str) -> JSONResponse:
    """统一的管理员接口错误响应格式。"""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=status_code, status="fail",
                              message=message).model_dump(),
    )


def _verify_admin(request: Request):
    """管理员鉴权统一校验：IP 白名单 + Bearer Token 比对。
    返回 (admin_hash, None) 表示鉴权通过；返回 (None, JSONResponse) 表示鉴权失败。
    """
    if not is_admin_allowed(request):
        return None, _admin_error(403, '来源IP无权访问管理员接口')
    admin_hash = get_settings().auth.admin_token_hash
    if not admin_hash:
        return None, _admin_error(403, '未配置管理员Token')
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None, _admin_error(403, '缺少管理员Authorization')
    admin_token = auth_header.split(' ', 1)[1].strip()
    if hashlib.sha256(admin_token.encode('utf-8')).hexdigest() != admin_hash:
        return None, _admin_error(403, '管理员验证失败')
    return admin_hash, None


class AdminCleanRequest(BaseModel):
    """管理员立即清理接口请求体

    - retention_days: 清理多少天前创建的对局；留空则使用配置中的值
    - mode: 清理模式，all（清理所有过期对局）或 non_playing（仅清理非 playing 的过期对局）；留空则使用配置中的值
    """
    retention_days: Optional[int] = Field(
        None, ge=1, le=3650, description="清理天数前创建的对局")
    mode: Optional[CleanupMode] = Field(
        None, description="清理模式：all / non_playing")


router = APIRouter(prefix="/api")


@router.post("/games", response_model=CreateGameResponse)
# 创建新游戏
def api_create_game(req: CreateGameRequest, request: Request, response: Response):
    client_ip = get_client_ip(request)
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
    # 第二次提示后返回释义；max_hints=1 时第一次提示即返回释义
    if game.hints_used >= 2 or (game.max_hints == 1 and game.hints_used >= 1):
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
    if game is None:
        raise HTTPException(status_code=400, detail="游戏不存在")

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


# ----------------- 管理员 Token 管理接口（仅限管理员） -----------------
@router.post('/admin/tokens/add')
async def admin_add_tokens(request: Request):
    """增加接口：传入多条 token 原文及其属性，返回每条 token 的 id。"""
    # 管理员白名单 IP 校验
    admin_hash, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    payload = await request.json()
    items = payload.get('tokens') or []
    created = []
    creator_ip = request.client.host if request.client else ''
    for it in items:
        raw = it.get('raw')
        if not raw:
            continue
        valid_until = it.get('valid_until')  # 可以为 None 或 ISO 字符串
        whitelist_ips = it.get('whitelist_ips') or []
        sha = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        # 管理员 Token 不允许写入数据库
        if admin_hash and sha == admin_hash:
            created.append({'raw': raw, 'error': '为管理员Token，禁止写入数据库'})
            continue
        try:
            tid = db_manager.add_token(
                sha, creator_ip=creator_ip, valid_until=valid_until, whitelist_ips=whitelist_ips)
            created.append({'raw': raw, 'id': tid, 'sha256': sha})
        except Exception as e:
            created.append({'raw': raw, 'error': str(e)})
    return {'code': 200, 'status': 'success', 'created': created}


@router.get('/admin/tokens')
async def admin_list_tokens(request: Request):
    """查询接口：列出有效 token 数及其 id 与属性（不含管理员 token）。"""
    _, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    try:
        rows = db_manager.list_tokens()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'code': 200, 'status': 'success', 'total': len(rows), 'tokens': rows}


@router.post('/admin/tokens/delete')
async def admin_delete_tokens(request: Request):
    """删除接口：批量删除 token。

    接收 JSON 体：
      - {"identifiers": ["id:1", "sha:<64hex>", "<raw_token>", ...]}
      - 或 {"identifier": "..."}  （单个）

    每个 identifier 支持三种显式前缀以避免歧义：
      - "id:<数字>"     按数据库自增 id 删除
      - "sha:<64hex>"   按 sha256 摘要删除
      - "raw:<原文>"    按 token 原文（内部会计算 sha256）删除
    无前缀时：纯数字按 id；64 位十六进制按 sha；其余按原文。

    返回 results 数组，每项包含：
      - identifier: 原样传入的标识
      - deleted:    实际删除的行数（0 表示未找到）
      - error:      若出错则为错误信息
    """
    _, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    try:
        payload = await request.json()
    except Exception:
        return _admin_error(400, '请求体不是合法的 JSON')

    ids = []
    if isinstance(payload, dict):
        if 'identifiers' in payload and isinstance(payload['identifiers'], list):
            ids = payload['identifiers']
        elif 'identifier' in payload:
            ids = [payload['identifier']]
        else:
            return _admin_error(400, '缺少 identifiers 或 identifier 字段')
    else:
        return _admin_error(400, '请求体必须是 JSON 对象')

    results = []
    for ident in ids:
        if ident is None:
            results.append({'identifier': ident, 'deleted': 0, 'error': '空标识'})
            continue
        if not isinstance(ident, (str, int)):
            results.append(
                {'identifier': ident, 'deleted': 0, 'error': '标识必须是字符串或数字'})
            continue
        try:
            cnt = db_manager.delete_token(str(ident))
            results.append({'identifier': ident, 'deleted': cnt})
        except Exception as e:
            results.append(
                {'identifier': ident, 'deleted': 0, 'error': str(e)})

    total_deleted = sum(r.get('deleted', 0) for r in results)
    return {'code': 200, 'status': 'success', 'total': total_deleted, 'results': results}


# ----------------- 配置热重载 -----------------
@router.get('/admin/config/reload')
async def admin_reload_config(request: Request):
    """热重载配置（GET 方法，便于运维直接通过 URL/curl 触发，接口幂等）：
    重新读取 config.toml 与环境变量，并把变更应用到运行时组件。

    热重载后立即生效的配置项：
      - auth.enabled / auth.admin_token_hash（鉴权中间件每次请求实时读取）
      - security.admin_allowlist / security.trusted_proxies
      - game.*（难度参数，每局新游戏创建时读取）
      - idiom_library.*（成语库路径；本接口会强制重新加载字库文件）
      - logging.*（日志级别 / 目录；本接口会重新配置 logging）
      - database.*（每次新建连接时读取；切换 SQLite 路径会立即生效；
        MySQL 参数变更也会在下次新连接使用）

    不会被热更新、需重启服务才能生效的项：
      - security.cors_origins（CORS 中间件在启动时实例化）
      - 服务端口 / workers 等进程级参数

    返回体里包含：
      - applied: 已热应用的子系统列表
      - requires_restart: 需要重启才能生效的配置项提示
      - idioms_reloaded: 成语库重新加载后的条目总数
    """
    _, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    # 1) 重新加载配置（会重新读取 TOML + 环境变量并做校验）
    try:
        new_settings = reload_settings()
    except Exception as e:
        # 重载失败：保留旧配置，返回错误
        return _admin_error(500, f'配置重载失败（已保留旧配置）：{e}')

    applied: list[str] = []
    errors: list[str] = []

    # 2) 重新配置日志
    try:
        setup_logging(new_settings)
        applied.append('logging')
    except Exception as e:
        errors.append(f'logging: {e}')

    # 3) 重新加载成语库（使 idiom_library 路径 / 字库内容变更生效）
    idiom_count = 0
    try:
        idiom_count = reload_idioms()
        applied.append('idiom_library')
    except Exception as e:
        errors.append(f'idiom_library: {e}')

    # auth / security / game / database / cleanup 等模块每次调用都实时 get_settings()，
    # Settings 单例已被 reload_settings() 更新，自动生效，无需额外操作。
    applied.extend(['auth', 'security', 'game', 'database', 'cleanup'])

    result = {
        'code': 200,
        'status': 'success',
        'applied': applied,
        'idioms_reloaded': idiom_count,
        'requires_restart': [
            'security.cors_origins（CORS 中间件在启动时实例化，无法热更新）'
        ],
    }
    if errors:
        result['warnings'] = errors
    return result


# ----------------- 管理员垃圾清理 -----------------
@router.post('/admin/config/clean')
async def admin_clean_games(req: AdminCleanRequest, request: Request):
    """管理员：立即清理过期对局。

    请求体字段均为可选，未提供时使用当前配置文件中的 cleanup.* 值：
      - retention_days: 清理多少天前创建的对局
      - mode: all（清理所有过期对局，不论状态）/ non_playing（仅清理非 playing 的过期对局）

    请求体字段均为可选，未提供时使用当前配置文件中的 cleanup.* 值；
    传入的参数仅本次调用生效，不会修改配置文件，也不影响后台自动清理任务：
      - retention_days: 清理多少天前创建的对局
      - mode: all（清理所有过期对局，不论状态）/ non_playing（仅清理非 playing 的过期对局）

    返回实际使用的清理参数及被删除的对局数量。
    """
    _, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    cleanup_cfg = get_settings().cleanup
    retention_days = req.retention_days if req.retention_days is not None else cleanup_cfg.retention_days
    mode = req.mode if req.mode is not None else cleanup_cfg.mode

    try:
        deleted = db_manager.clean_old_games(retention_days, mode)
    except Exception as e:
        return _admin_error(500, f'清理对局失败: {e}')

    return {
        'code': 200,
        'status': 'success',
        'retention_days': retention_days,
        'mode': mode.value,
        'deleted': deleted,
    }
