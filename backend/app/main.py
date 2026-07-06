from fastapi import FastAPI, Response, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError 
from app.services.routes import router
from app.schemas.game import ErrorResponse

class UTF8JSONResponse(JSONResponse):
    """
    默认响应体
    在此处植入全局头
    显式声明 charset=utf-8 的 JSON 响应，避免浏览器中文乱码
    """
    media_type = "application/json; charset=utf-8"
    def __init__(self, content, *args, **kwargs):
        super().__init__(content, *args, **kwargs)
        # 全局头
        self.headers["X-Server"] = "P-C-T-G-Wordle-API/1.0"
        self.headers["Server"] = "P-C-T-G-Wordle-API/1.0"


app = FastAPI(title="IdomWordle API", default_response_class=UTF8JSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

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