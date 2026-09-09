"""仪表盘接口：保存 / 列出 / 删除图表。"""
from fastapi import APIRouter
from pydantic import BaseModel

from ..dashboard import store

router = APIRouter(prefix="/dashboards", tags=["dashboard"])


class DashboardItem(BaseModel):
    title: str
    question: str = ""
    sql: str = ""
    columns: list = []
    rows: list = []
    chart_type: str = "table"
    mode: str = "chat"


@router.get("")
def list_dashboards() -> list:
    return store.list_all()


@router.post("")
def create_dashboard(item: DashboardItem) -> dict:
    return store.add(item.model_dump())


@router.delete("/{item_id}")
def delete_dashboard(item_id: str) -> dict:
    store.delete(item_id)
    return {"ok": True}
