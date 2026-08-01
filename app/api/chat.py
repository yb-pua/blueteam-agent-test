"""AI 会话管理 API - 会话 CRUD 与消息读取。"""

from fastapi import HTTPException
from pydantic import BaseModel
from app.models import database as db
from . import api_router

class CreateSessionRequest(BaseModel):
    title: str = "新会话"

class RenameSessionRequest(BaseModel):
    title: str


@api_router.get("/chat/sessions")
async def list_sessions(limit: int = 50):
    sessions = await db.list_chat_sessions(limit=limit)
    return {"items": sessions}

@api_router.post("/chat/sessions")
async def create_session(req: CreateSessionRequest):
    sid = await db.create_chat_session(req.title)
    session = await db.get_chat_session(sid)
    # 操作日志
    await db.log_operation("session_create", {"session_id": sid, "title": req.title})
    return {"session": session}

@api_router.get("/chat/sessions/{session_id}/messages")
async def session_messages(session_id: int):
    if not await db.get_chat_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = await db.get_chat_messages(session_id)
    return {"items": messages}

@api_router.post("/chat/sessions/{session_id}/rename")
async def rename_session(session_id: int, req: RenameSessionRequest):
    if not await db.get_chat_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.rename_chat_session(session_id, req.title)
    return {"status": "ok"}

@api_router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: int):
    if not await db.get_chat_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.delete_chat_session(session_id)
    # 操作日志
    await db.log_operation("session_delete", {"session_id": session_id})
    return {"status": "ok"}
