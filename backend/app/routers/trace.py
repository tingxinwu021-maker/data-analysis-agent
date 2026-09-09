"""追踪接口：GET /traces（最近查询记录，供排查）。"""
from fastapi import APIRouter

from ..observability import trace

router = APIRouter(tags=["trace"])


@router.get("/traces")
def list_traces() -> list:
    return trace.recent(50)
