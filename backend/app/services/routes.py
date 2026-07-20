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
from app.schemas.leaderboard import (
    UploadRecordRequest,
)
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
from app.services import leaderboard_service
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
      - cleanup.*（垃圾清理策略，后台任务每次循环实时读取）

    不会被热更新、需重启服务才能生效的项：
      - database.*（为维持运行稳定，热重载不改变数据库连接配置）
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

    # 1) 保存当前数据库配置（热重载不改变数据库配置，维持运行稳定）
    old_settings = get_settings()
    old_database = old_settings.database

    # 2) 重新加载配置（会重新读取 TOML + 环境变量并做校验）
    try:
        new_settings = reload_settings()
    except Exception as e:
        # 重载失败：保留旧配置，返回错误
        return _admin_error(500, f'配置重载失败（已保留旧配置）：{e}')

    # 3) 用旧数据库配置覆盖新加载的配置，使热重载不影响数据库连接
    new_settings.database = old_database

    applied: list[str] = []
    errors: list[str] = []

    # 4) 重新配置日志
    try:
        setup_logging(new_settings)
        applied.append('logging')
    except Exception as e:
        errors.append(f'logging: {e}')

    # 5) 重新加载成语库（使 idiom_library 路径 / 字库内容变更生效）
    idiom_count = 0
    try:
        idiom_count = reload_idioms()
        applied.append('idiom_library')
    except Exception as e:
        errors.append(f'idiom_library: {e}')

    # auth / security / game / cleanup 等模块每次调用都实时 get_settings()，
    # Settings 单例已被 reload_settings() 更新，自动生效，无需额外操作。
    # database 配置已被旧值覆盖，热重载期间保持不变；修改数据库配置需重启服务。
    applied.extend(['auth', 'security', 'game', 'cleanup'])

    result = {
        'code': 200,
        'status': 'success',
        'applied': applied,
        'idioms_reloaded': idiom_count,
        'requires_restart': [
            'database.*（为维持运行稳定，热重载不重载数据库配置，需重启生效）',
            'security.cors_origins（CORS 中间件在启动时实例化，无法热更新）',
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


# ----------------- 排行榜相关接口 -----------------

def _get_lb_cookie(request: Request) -> Optional[str]:
    """从请求中获取排行榜cookie token"""
    cookie_name = get_settings().leaderboard.cookie_name
    return request.cookies.get(cookie_name)


def _set_lb_cookie(response: JSONResponse, cookie_token: str, request: Request) -> None:
    """设置排行榜cookie"""
    cookie_name, max_age_days = leaderboard_service._get_cookie_settings()
    max_age = max_age_days * 24 * 3600
    is_secure = request.url.scheme == 'https' if hasattr(
        request, 'url') else False
    response.set_cookie(
        key=cookie_name,
        value=cookie_token,
        max_age=max_age,
        httponly=True,
        samesite='lax',
        secure=is_secure
    )


@router.post("/leaderboard/upload")
async def api_upload_leaderboard(req: UploadRecordRequest, request: Request):
    """首次上传战绩到排行榜"""
    client_ip = get_client_ip(request)
    cookie_token = _get_lb_cookie(request)

    # 首次创建存档必须提供用户名
    username = (req.username or "").strip()
    if not cookie_token and not username:
        raise HTTPException(status_code=400, detail="请输入用户名")

    try:
        user, new_cookie, is_new = leaderboard_service.upload_records(
            cookie_token, username, req.records, client_ip
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 构建统计概览
    stats = {}
    for diff in ['easy', 'medium', 'hard']:
        total = user.get(f'{diff}_total', 0)
        won = user.get(f'{diff}_won', 0)
        rounds = user.get(f'{diff}_win_rounds', 0)
        stats[diff] = {
            'total': total,
            'won': won,
            'win_rate': won / total if total > 0 else 0,
            'avg_rounds': rounds / won if won > 0 else 0
        }

    resp = JSONResponse(content={
        'code': 200,
        'status': 'success',
        'user_id': user['user_id'],
        'username': user['username'],
        'ip_location': user['ip_location'],
        'message': "存档创建成功！" if is_new else "战绩上传成功！",
        'stats': stats
    })
    _set_lb_cookie(resp, new_cookie, request)
    return resp


@router.post("/leaderboard/append")
async def api_append_leaderboard(req: UploadRecordRequest, request: Request):
    """追加新战绩到已有存档"""
    cookie_token = _get_lb_cookie(request)
    if not cookie_token:
        raise HTTPException(status_code=400, detail="未找到存档，请先创建存档")

    try:
        user = leaderboard_service.append_records(cookie_token, req.records)
        if req.username and req.username.strip():
            db_manager.update_username(user['user_id'], req.username.strip())
            updated_user = db_manager.get_user_by_id(user['user_id'])
            if updated_user:
                user = updated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stats = {}
    for diff in ['easy', 'medium', 'hard']:
        total = user.get(f'{diff}_total', 0)
        won = user.get(f'{diff}_won', 0)
        rounds = user.get(f'{diff}_win_rounds', 0)
        stats[diff] = {
            'total': total,
            'won': won,
            'win_rate': won / total if total > 0 else 0,
            'avg_rounds': rounds / won if won > 0 else 0
        }

    return {
        'code': 200,
        'status': 'success',
        'user_id': user['user_id'],
        'username': user['username'],
        'ip_location': user['ip_location'],
        'message': "战绩追加成功！",
        'stats': stats
    }


class SubmitDailyRequest(BaseModel):
    """提交日榜成绩请求"""
    game_id: str
    difficulty: str
    won: bool
    rounds: int


@router.post("/leaderboard/daily/submit")
async def api_submit_daily(req: SubmitDailyRequest, request: Request):
    """提交每日挑战成绩到日榜"""
    cookie_token = _get_lb_cookie(request)
    if not cookie_token:
        raise HTTPException(status_code=400, detail="未找到存档，无法提交日榜成绩")

    try:
        success = leaderboard_service.submit_daily_score(
            cookie_token, req.game_id, req.difficulty, req.won, req.rounds
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        'code': 200,
        'status': 'success',
        'message': "今日成绩已提交" if success else "今日成绩已提交过",
        'duplicate': not success
    }


@router.get("/leaderboard/{difficulty}")
async def api_get_leaderboard(difficulty: str, request: Request):
    """获取用户排行榜（三种榜单）"""
    if difficulty not in ['easy', 'medium', 'hard']:
        raise HTTPException(status_code=400, detail="无效的难度")

    cookie_token = _get_lb_cookie(request)
    profile = leaderboard_service.get_user_profile(cookie_token)
    user_id = profile['user_id'] if profile else None

    lb_data = leaderboard_service.get_leaderboard_data(difficulty, user_id)

    def format_entry(entry, board_type):
        value = entry['value']
        if board_type == 'win_rate':
            value = round(value * 100, 1)
        elif board_type == 'avg_rounds':
            value = round(value, 2)
        return {
            'rank': entry['rank'],
            'user_id': entry['user_id'],
            'username': entry['username'],
            'ip_location': entry['ip_location'],
            'value': value,
            'total_games': entry['total'],
            'won_games': entry['won'],
            'win_rate': round(entry['win_rate'] * 100, 1),
            'avg_rounds': round(entry['avg_rounds'], 2)
        }

    wins = [format_entry(e, 'wins') for e in lb_data['wins']]
    win_rate = [format_entry(e, 'win_rate') for e in lb_data['win_rate']]
    avg_rounds = [format_entry(e, 'avg_rounds') for e in lb_data['avg_rounds']]

    return {
        'code': 200,
        'status': 'success',
        'difficulty': difficulty,
        'wins': wins,
        'win_rate': win_rate,
        'avg_rounds': avg_rounds,
        'my_rank': lb_data['my_rank'],
        'my_profile': profile
    }


@router.get("/leaderboard/{difficulty}/daily")
async def api_get_daily_leaderboard(difficulty: str, request: Request):
    """获取每日挑战排行榜"""
    if difficulty not in ['easy', 'medium', 'hard']:
        raise HTTPException(status_code=400, detail="无效的难度")

    cookie_token = _get_lb_cookie(request)
    profile = leaderboard_service.get_user_profile(cookie_token)
    user_id = profile['user_id'] if profile else None

    daily_data = leaderboard_service.get_daily_leaderboard_data(
        difficulty, user_id)

    daily_list = []
    for entry in daily_data['daily']:
        daily_list.append({
            'rank': entry['rank'],
            'user_id': entry['user_id'],
            'username': entry['username'],
            'ip_location': entry['ip_location'],
            'rounds': entry['rounds']
        })

    from datetime import date
    return {
        'code': 200,
        'status': 'success',
        'difficulty': difficulty,
        'date': date.today().isoformat(),
        'daily': daily_list,
        'my_rank': daily_data['my_rank'],
        'my_profile': profile
    }


@router.get("/leaderboard/profile/me")
async def api_get_my_profile(request: Request):
    """获取当前用户存档信息"""
    cookie_token = _get_lb_cookie(request)
    profile = leaderboard_service.get_user_profile(cookie_token)
    return {
        'code': 200,
        'status': 'success',
        'profile': profile
    }


@router.post("/leaderboard/profile/delete")
async def api_delete_my_profile(request: Request):
    """用户删除自己的存档"""
    cookie_token = _get_lb_cookie(request)
    if not cookie_token:
        raise HTTPException(status_code=400, detail="未找到存档")
    success = leaderboard_service.delete_user_archive(cookie_token)

    resp = JSONResponse(content={
        'code': 200 if success else 400,
        'status': 'success' if success else 'fail',
        'message': '存档已删除' if success else '删除失败'
    })

    if success:
        cookie_name = get_settings().leaderboard.cookie_name
        resp.delete_cookie(key=cookie_name)

    return resp


# ----------------- 管理员排行榜管理接口 -----------------

@router.get('/admin/leaderboard/users')
async def admin_list_lb_users(request: Request):
    """管理员：列出排行榜用户"""
    _, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    cfg = get_settings().database
    users = []
    if cfg.type.value == 'sqlite':
        import sqlite3
        conn = sqlite3.connect(str(cfg.sqlite_path_resolved))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT user_id, username, ip_location, create_time, update_time, easy_total, medium_total, hard_total FROM top_user ORDER BY update_time DESC LIMIT 500")
            users = [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    else:
        import pymysql
        conn = pymysql.connect(
            host=cfg.host, port=cfg.port, user=cfg.user,
            password=cfg.password, database=cfg.db, charset=cfg.charset,
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT user_id, username, ip_location, create_time, update_time, easy_total, medium_total, hard_total FROM top_user ORDER BY update_time DESC LIMIT 500")
                users = cursor.fetchall()
        finally:
            conn.close()

    return {'code': 200, 'status': 'success', 'total': len(users), 'users': users}


class AdminDeleteUserRequest(BaseModel):
    """管理员删除用户请求"""
    user_id: str


@router.post('/admin/leaderboard/delete')
async def admin_delete_lb_user(req: AdminDeleteUserRequest, request: Request):
    """管理员：删除指定用户ID的存档并吊销其cookie"""
    _, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    success = leaderboard_service.admin_delete_user(req.user_id)
    return {
        'code': 200 if success else 404,
        'status': 'success' if success else 'fail',
        'message': f'用户 {req.user_id} 已删除' if success else '用户不存在'
    }


@router.post('/admin/leaderboard/clean-daily')
async def admin_clean_daily(request: Request):
    """管理员：手动清空日榜"""
    _, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    deleted = db_manager.clean_daily_board()
    return {
        'code': 200,
        'status': 'success',
        'message': f'日榜已清空，删除{deleted}条记录'
    }


@router.post('/admin/leaderboard/clean-inactive')
async def admin_clean_inactive(request: Request):
    """管理员：手动清理不活跃用户"""
    _, auth_err = _verify_admin(request)
    if auth_err is not None:
        return auth_err

    inactive_days = get_settings().leaderboard.inactive_days
    deleted = db_manager.clean_inactive_users(inactive_days)
    return {
        'code': 200,
        'status': 'success',
        'message': f'已清理{inactive_days}天不活跃用户，删除{deleted}条记录'
    }
