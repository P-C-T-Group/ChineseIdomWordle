from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.services.routes import router


class UTF8JSONResponse(JSONResponse):
    """显式声明 charset=utf-8 的 JSON 响应，避免浏览器中文乱码"""
    media_type = "application/json; charset=utf-8"


app = FastAPI(title="成语 Wordle API", default_response_class=UTF8JSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def read_root():
    return {"message": "欢迎使用成语 Wordle API"}
