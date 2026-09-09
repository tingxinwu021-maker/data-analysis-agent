"""FastAPI 入口。"""
from fastapi import FastAPI

from .config import settings
from .routers import analyze, chat, dashboard, feedback, files, trace

app = FastAPI(title="Data Analysis Agent", version="0.1.0")
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(analyze.router)
app.include_router(dashboard.router)
app.include_router(feedback.router)
app.include_router(trace.router)


@app.get("/health")
def health() -> dict:
    """健康检查：确认服务与配置加载正常。"""
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "db": "mysql",
        "mysql_database": settings.mysql_database,
    }
