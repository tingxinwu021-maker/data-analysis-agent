"""代码分析接口：POST /analyze"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agent.code_agent import analyze

router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    file_id: str
    question: str


@router.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest) -> dict:
    try:
        return analyze(req.file_id, req.question)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
