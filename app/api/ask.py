from pydantic import BaseModel
from app.agent.orchestrator import ask as agent_ask
from app.models import database as db
from . import api_router

class AskRequest(BaseModel):
    question: str
    session_id: int | None = None
    sources: list[str] | None = None  # 用户选择的情报来源（None=全部）
    thinking: str | None = None       # 思考强度 low/medium/high（None=不指定）

class AskResponse(BaseModel):
    answer: str
    session_id: int

@api_router.post("/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    answer, session_id = await agent_ask(req.question, req.session_id, req.sources, req.thinking)
    # 操作日志：记录提问摘要（前 50 字）
    await db.log_operation("chat_ask", {"question": req.question.strip()[:50], "session_id": session_id})
    return AskResponse(answer=answer, session_id=session_id)
