# -- coding: utf-8 --
'''
main.py 
EnterGate of ChineseIdomWordle backend (FastAPI)
(c) 2026 P.C.T.G. MIT License.
CODEOWNERS: @GZYZhy
'''

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
from app.core.security import is_admin_allowed, get_client_ip, _ip_in_list
# 日志
import logging

RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"

# 启动前初始化日志与配置
settings = get_settings()
setup_logging(settings)

# 管理员 Token 哈希来自统一配置
ADMIN_TOKEN_HASH = settings.auth.admin_token_hash

# 加载日志记录器
log = logging.getLogger('uvicorn')


def get_token_sha256(raw_token: str) -> str:
    """
    计算传入token的sha256摘要
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# 启动前初始化数据库并清理过期 token
try:
    initDB()
    # 启动时清理过期 token
    try:
        db_manager.clean_expired_tokens()
    except Exception:
        pass
except Exception as e:
    log.critical(f"[DB] 数据库初始化失败，服务无法启动: {e}")
    raise RuntimeError(f"数据库初始化失败，请检查数据库配置与连接: {e}") from e

app = FastAPI(title="IdomWordle API")

app.include_router(router)


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
    """
    current_path = request.url.path
    # 根路径（健康检查）及文档端点免 Token
    if current_path in ("/", "/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    # 放行所有 OPTIONS 跨域预检请求
    if request.method == "OPTIONS":
        return await call_next(request)

    # Token Auth 关闭则直接放行
    if not settings.auth.enabled:
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

    # 管理员 Token（配置型）直接放行
    if ADMIN_TOKEN_HASH and token_hash == ADMIN_TOKEN_HASH:
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
            err = ErrorResponse(code=403, status="fail", message="Token 不在允许的来源 IP 列表中")
            return JSONResponse(status_code=403, content=err.model_dump())

    # 更新 last_call_time（忽略错误）
    try:
        db_manager.update_last_call_time(token_row.get("id"))
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
def read_root(response: Response):
    """
    根路径 - API 入口信息
    """
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
