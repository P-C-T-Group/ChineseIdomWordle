from fastapi import FastAPI, Response, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    result = {
        "code": 200,
        "status": "success",
        "message": "Welcome to Wordle API by P.C.T.G.",
    }
    response.headers["X-Server-Health"] = "OK"
    return result

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    error_data = ErrorResponse(
        code=exc.status_code,
        status="fail",
        message=exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_data.model_dump()
    )