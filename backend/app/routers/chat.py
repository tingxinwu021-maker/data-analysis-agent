"""对话接口：POST /chat（一次性）、POST /chat/stream（SSE 流式）、DELETE /chat/session/{id}（清会话）。"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agent import conversation
from ..agent.sql_agent import answer, answer_stream

router = APIRouter(tags=["chat"])


class Question(BaseModel):
    question: str
    session_id: str | None = None


@router.post("/chat")
def chat_endpoint(q: Question) -> dict:
    return answer(q.question, q.session_id)


@router.post("/chat/stream")
def chat_stream_endpoint(q: Question) -> StreamingResponse:
    def gen():
        for event in answer_stream(q.question, q.session_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.delete("/chat/session/{session_id}")
def clear_session(session_id: str) -> dict:
    """清空一个会话的历史（前端「新对话」时调用，释放内存）。"""
    conversation.clear(session_id)
    return {"ok": True}
