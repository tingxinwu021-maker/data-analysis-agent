"""反馈接口：GET /feedback（评审）、POST /feedback（提交 👍/👎）。"""
from fastapi import APIRouter
from pydantic import BaseModel

from ..feedback import store

router = APIRouter(prefix="/feedback", tags=["feedback"])


class Feedback(BaseModel):
    question: str = ""
    sql: str = ""
    rating: str = "up"   # up | down
    note: str = ""


@router.get("")
def list_feedback() -> list:
    return store.list_all()


@router.post("")
def create_feedback(fb: Feedback) -> dict:
    return store.add(fb.model_dump())
