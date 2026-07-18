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
# 统一配置
from app.core.config import get_settings
from app.core.logging_setup import setup_logging
from app.core.security import is_admin_allowed
# 日志
import logging

RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"

# 启动前初始化日志与配置
settings = get_settings()
setup_logging(settings)

# Token 摘要文件路径与管理员 Token 哈希均来自统一配置
# 路径已由 Settings 统一解析为绝对路径
TOKEN_FILE_PATH = settings.auth.token_file_resolved
ADMIN_TOKEN_HASH = settings.auth.admin_token_hash

# 缓存合法哈希列表
valid_token_hashes: set[str] = set()
enable_auth: bool = settings.auth.enabled

# 加载日志记录器
log = logging.getLogger('uvicorn')


def load_valid_token_hashes() -> None:
    """
    读取txt内所有sha256合法token摘要，存入全局集合缓存
    文件存在但无有效内容时，自动关闭鉴权校验
    """
    global valid_token_hashes, enable_auth
    valid_token_hashes.clear()
    # 鉴权总开关关闭则直接清空并跳过文件读取
    if not settings.auth.enabled:
        enable_auth = False
        log.info("[Auth] 配置已关闭全局 Token 校验")
        return
    # 判断文件是否存在
    if not TOKEN_FILE_PATH.exists():
        raise RuntimeError(
            f"\n {RED}Token摘要文件（{TOKEN_FILE_PATH}）不存在，如需关闭Token鉴权，请在配置中设置 auth.enabled=false。 \n 请使用ctrl+c退出程序后修正配置。{RESET}"
        )
    with open(TOKEN_FILE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:  # 跳过空行
                valid_token_hashes.add(line)
    if len(valid_token_hashes) == 0:
        enable_auth = False
        log.info("[Auth] Token摘要列表无有效Token，已自动关闭全局Token校验")
    else:
        enable_auth = True
        log.info(f"[Auth] 成功加载 {len(valid_token_hashes)} 条合法Token摘要")


def get_token_sha256(raw_token: str) -> str:
    """
    计算传入token的sha256摘要
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# 启动前加载合法token哈希
load_valid_token_hashes()

# 启动前初始化数据库
try:
    initDB()
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
    全局中间件 - Bearer Token 鉴权
    """
    current_path = request.url.path
    # 根路径（健康检查）、重载token端点、（可能的）文档端点免Token
    if current_path in ("/", "/api/admin/reload-token", "/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    # 放行所有 OPTIONS 跨域预检请求
    if request.method == "OPTIONS":
        return await call_next(request)

    # Token Auth关闭则直接放行
    if not enable_auth:
        return await call_next(request)

    # 其他路径先校验Token，校验失败直接拦截
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        err = ErrorResponse(code=401, status="fail",
                            message="缺少Authorization请求头")
        return JSONResponse(status_code=401, content=err.model_dump())

    # Token分割
    raw_part = auth_header.split(" ", 1)
    if len(raw_part) != 2 or not raw_part[1].strip():
        err = ErrorResponse(code=401, status="fail", message="Token格式错误")
        return JSONResponse(status_code=401, content=err.model_dump())
    raw_token = raw_part[1].strip()

    token_hash = get_token_sha256(raw_token)
    if token_hash not in valid_token_hashes:
        err = ErrorResponse(code=401, status="fail", message="Token无效")
        return JSONResponse(status_code=401, content=err.model_dump())

    # Token合法则放行
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


@app.get("/api/admin/reload-token")
def reload_token_list(request: Request):
    """
    管理员接口 - 重载token列表
    """
    # 管理员白名单 IP 校验
    if not is_admin_allowed(request):
        return JSONResponse(status_code=403, content=ErrorResponse(code=403, status="fail", message="来源IP无权访问管理员接口").model_dump())
    # 未配置管理员 Token 哈希则拒绝
    if not ADMIN_TOKEN_HASH:
        return JSONResponse(status_code=403, content=ErrorResponse(code=403, status="fail", message="未配置管理员Token").model_dump())
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or not parts[1].strip():
            return JSONResponse(status_code=403, content=ErrorResponse(code=403, status="fail", message="管理员Token格式错误").model_dump())
        admin_token = parts[1].strip()
        if get_token_sha256(admin_token) == ADMIN_TOKEN_HASH:
            load_valid_token_hashes()
            return {"code": 200, "status": "success", "message": "重载成功", "total_valid": len(valid_token_hashes)}
    # 无管理员权限
    return JSONResponse(status_code=403, content=ErrorResponse(code=403, status="fail", message="无管理员操作权限").model_dump())


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
