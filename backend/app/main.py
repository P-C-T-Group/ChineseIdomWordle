# -- coding: utf-8 --
'''
main.py 
EnterGate of ChineseIdomWordle backend (FastAPI)
(c) 2026 P.C.T.G. MIT License.
CODEOWNERS: @GZYZhy
'''

import asyncio
from fastapi import FastAPI, Response, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.services.routes import router
from app.schemas.game import ErrorResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
# 鉴权
import hashlib
# 数据库初始化
from app.database.initDB import initDB
from app.database import db_manager
# 统一配置
from app.core.config import get_settings
from app.core.logging_setup import setup_logging
from app.core.security import get_client_ip, _ip_in_list
# 日志
import logging

RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"

# 启动前初始化日志与配置
settings = get_settings()
setup_logging(settings)

log = logging.getLogger('uvicorn')


def get_token_sha256(raw_token: str) -> str:
    """
    计算传入token的sha256摘要
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# 启动前初始化数据库并清理过期 token / 过期对局
try:
    initDB()
    # 启动时清理过期 token
    try:
        db_manager.clean_expired_tokens()
    except Exception as e:
        log.warning(f"[DB] 启动时清理过期 token 失败，已跳过: {e}")
    # 启动时按配置清理一次过期对局（可通过 cleanup.run_on_startup 关闭）
    try:
        cleanup_cfg = settings.cleanup
        if cleanup_cfg.enabled and cleanup_cfg.run_on_startup:
            db_manager.clean_old_games(
                cleanup_cfg.retention_days, cleanup_cfg.mode)
    except Exception:
        pass
except Exception as e:
    db_type = settings.database.type.value
    err_msg = str(e)

    # 美观的错误输出
    border = "═" * 60
    print(f"\n{RED}╔{border}╗")
    print(f"║{RESET}  {RED}❌ 数据库初始化失败 - 服务无法启动{RESET}")
    print(f"{RED}╠{border}╣")
    print(f"{RED}║{RESET}  数据库类型: {db_type.upper()}")

    if db_type == "mysql":
        print(
            f"{RED}║{RESET}  连接地址:   {settings.database.host}:{settings.database.port}")
        print(f"{RED}║{RESET}  数据库名:   {settings.database.db}")
        print(f"{RED}║{RESET}  用户名:     {settings.database.user}")

        if "Connection refused" in err_msg:
            print(f"{RED}╠{border}╣")
            print(f"{RED}║{RESET}  💡 可能原因:")
            print(f"{RED}║{RESET}     1. MySQL 服务未启动，请先启动 MySQL")
            print(f"{RED}║{RESET}     2. 端口 {settings.database.port} 不正确")
            print(f"{RED}║{RESET}     3. 防火墙阻止了连接")
        elif "Access denied" in err_msg:
            print(f"{RED}╠{border}╣")
            print(f"{RED}║{RESET}  💡 可能原因:")
            print(f"{RED}║{RESET}     1. 用户名或密码错误")
            print(f"{RED}║{RESET}     2. 用户没有访问该数据库的权限")
        elif "Unknown database" in err_msg:
            print(f"{RED}╠{border}╣")
            print(f"{RED}║{RESET}  💡 可能原因:")
            print(f"{RED}║{RESET}     数据库 '{settings.database.db}' 不存在，请先创建")

    print(f"{RED}╠{border}╣")
    print(
        f"{RED}║{RESET}  错误详情: {err_msg[:100]}{'...' if len(err_msg) > 100 else ''}")
    print(f"{RED}╚{border}╝{RESET}\n")

    log.critical(f"[DB] 数据库初始化失败，服务无法启动: {e}")
    raise SystemExit(1) from e

app = FastAPI(title="IdomWordle API")

app.include_router(router)

# 后台定期清理：过期 token + 过期对局（自动化垃圾回收）
# 默认每小时执行一次；使用 asyncio 后台任务，保证过期数据不会长期积累。
# 清理间隔与对局清理策略来自配置文件 cleanup 节，支持热重载。
_cleanup_task = None


async def _periodic_clean_loop():
    """后台循环：定时清理过期 token，并按配置清理过期对局。"""
    from datetime import date, datetime
    _last_daily_clean_date = None
    try:
        while True:
            try:
                today = date.today()
                # 1) 每日0点清空日榜（跨天时执行）
                if _last_daily_clean_date != today:
                    yesterday = today.isoformat()
                    # 清理昨天的日榜（保留今天的）
                    db_manager.clean_daily_board(yesterday)
                    _last_daily_clean_date = today
                    log.info(f"[Cleanup] 已清空日榜（{yesterday}）")

                # 2) 过期 token 清理
                db_manager.clean_expired_tokens()

                # 3) 过期对局清理（受配置开关控制）
                cleanup_cfg = get_settings().cleanup
                if cleanup_cfg.enabled:
                    db_manager.clean_old_games(
                        cleanup_cfg.retention_days, cleanup_cfg.mode)

                # 4) 清理不活跃用户（每6小时检查一次）
                if datetime.now().hour % 6 == 0:
                    lb_cfg = get_settings().leaderboard
                    if lb_cfg.inactive_days > 0:
                        db_manager.clean_inactive_users(lb_cfg.inactive_days)
            except Exception:
                # 忽略清理错误，避免任务退出
                pass
            # 每次循环重新读取配置，支持热更新间隔
            interval = get_settings().cleanup.interval_seconds
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return


@app.on_event("startup")
async def _start_cleanup_task():
    global _cleanup_task
    # 启动后台清理任务（不阻塞启动）
    loop = asyncio.get_running_loop()
    _cleanup_task = loop.create_task(_periodic_clean_loop())


@app.on_event("shutdown")
async def _stop_cleanup_task():
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except Exception:
            pass


@app.middleware("http")
async def add_global_server_headers(request: Request, call_next):
    """
    全局中间件 -  注入响应头
    修改注释：为了使/docs的自动文档正常显示，把注入全局头提出一个单独的中间件
    """
    response = await call_next(request)
    response.headers["X-Server"] = "P-C-T-G-Wordle-API/1.0"
    response.headers["Server"] = "P-C-T-G-Wordle-API/1.0"
    return response


@app.middleware("http")
async def bearer_auth_middleware(request: Request, call_next):
    """
    全局中间件 - Token 鉴权（基于数据库实时校验）

    配置项（auth.enabled、auth.admin_token_hash 等）每次请求实时读取，
    以支持通过 /api/admin/config/reload 热更新。
    """
    current_path = request.url.path
    # 仅对 /api/ 开头的路径进行鉴权，其他路径（静态资源、SPA 路由、文档等）直接放行
    if not current_path.startswith("/api/") and current_path != "/api":
        return await call_next(request)
    # 文档端点免 Token
    if current_path in ("/api/docs", "/api/redoc", "/api/openapi.json", "/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    # 放行所有 OPTIONS 跨域预检请求
    if request.method == "OPTIONS":
        return await call_next(request)

    # 实时读取当前配置（支持热重载）
    current_settings = get_settings()

    # Token Auth 关闭则直接放行
    if not current_settings.auth.enabled:
        return await call_next(request)

    # 其他路径先校验 Authorization
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        err = ErrorResponse(code=401, status="fail",
                            message="缺少Authorization请求头")
        return JSONResponse(status_code=401, content=err.model_dump())

    raw_part = auth_header.split(" ", 1)
    if len(raw_part) != 2 or not raw_part[1].strip():
        err = ErrorResponse(code=401, status="fail", message="Token格式错误")
        return JSONResponse(status_code=401, content=err.model_dump())
    raw_token = raw_part[1].strip()
    token_hash = get_token_sha256(raw_token)

    # 管理员 Token（配置型）直接放行——每次实时取最新哈希，支持热更新
    admin_hash = current_settings.auth.admin_token_hash
    if admin_hash and token_hash == admin_hash:
        return await call_next(request)

    # 从数据库实时校验 Token
    try:
        token_row = db_manager.get_token_by_hash(token_hash)
    except Exception as e:
        log.error(f"[Auth] 查询 token 时出错: {e}")
        err = ErrorResponse(code=500, status="fail", message="Token 查询失败")
        return JSONResponse(status_code=500, content=err.model_dump())

    if not token_row:
        err = ErrorResponse(code=401, status="fail", message="Token无效或已过期")
        return JSONResponse(status_code=401, content=err.model_dump())

    # 若 token 配置了白名单 IP 列表，则校验客户端 IP
    whitelist = token_row.get("whitelist_ips") or []
    if whitelist:
        client_ip = get_client_ip(request)
        if not _ip_in_list(client_ip, whitelist):
            err = ErrorResponse(code=403, status="fail",
                                message="Token 不在允许的来源 IP 列表中")
            return JSONResponse(status_code=403, content=err.model_dump())

    # 更新 last_call_time（忽略错误）
    try:
        token_id = token_row.get("id")
        if isinstance(token_id, int):
            db_manager.update_last_call_time(token_id)
    except Exception:
        pass

    # Token 合法，继续处理请求
    response = await call_next(request)
    return response

# 跨域中间件（来源来自统一配置）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "OPTIONS"
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "Keep-Alive",
        "User-Agent"
    ],
)


@app.get("/")
def read_root(response: Response, request: Request):
    """
    根路径 - 自动检测：如果存在前端 index.html 则返回前端，否则返回 API 信息
    """
    from pathlib import Path
    from fastapi.responses import FileResponse
    client_index = Path(__file__).resolve(
    ).parent.parent.parent / "client" / "index.html"
    if client_index.exists():
        return FileResponse(str(client_index))
    result = {
        "code": 200,
        "status": "success",
        "message": "Welcome to Wordle API by P.C.T.G.",
    }
    response.headers["X-Server-Health"] = "OK"
    return result


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    自定义标准http错误采用的格式化 Starlette HTTP 异常处理器
    """
    err = ErrorResponse(
        code=exc.status_code,
        status="fail",
        message=exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=err.model_dump()
    )


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """
    自定义格式化 HTTP 异常处理器
    """
    error_data = ErrorResponse(
        code=exc.status_code,
        status="fail",
        message=exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_data.model_dump()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    '''
    格式化处理请求参数验证错误
    '''
    # 提取第一条错误提示作为统一message
    first_err = exc.errors()[0]
    msg = f"{first_err['loc'][-1]} 参数非法：{first_err['msg']}"
    err = ErrorResponse(
        code=422,
        status="fail",
        message=msg
    )
    return JSONResponse(status_code=422, content=err.model_dump())


@app.exception_handler(Exception)
async def global_unknown_exception_handler(request: Request, exc: Exception):
    '''
    兜底异常处理器，捕获所有未处理的异常
    '''
    err = ErrorResponse(
        code=500,
        status="fail",
        message="服务器内部异常，请稍后重试"
    )
    return JSONResponse(status_code=500, content=err.model_dump())
