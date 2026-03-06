"""Profile helper API: chat, session, profile, download."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.services.profile_helper import agent as profile_agent
from app.services.profile_helper import sessions as profile_sessions

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    model: str | None = None


@router.post("/chat", response_class=StreamingResponse)
async def chat_stream(req: ChatRequest):
    """Streaming chat: SSE response."""
    session_id, session = profile_sessions.get_or_create(req.session_id)
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    def generate():
        import json

        try:
            for chunk in profile_agent.run_agent(
                req.message, session, stream=True, model=req.model
            ):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        },
    )


@router.get("/profile/{session_id}")
async def get_profile(session_id: str):
    """Get development and forum profile content for session."""
    session = profile_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return {
        "profile": session["profile"],
        "forum_profile": session.get("forum_profile", ""),
    }


@router.get("/download/{session_id}")
async def download_profile(session_id: str):
    """Download development profile as .md."""
    session = profile_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return Response(
        content=session["profile"].encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="profile.md"'},
    )


@router.get("/download/{session_id}/forum")
async def download_forum_profile(session_id: str):
    """Download forum profile as .md."""
    session = profile_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    content = session.get("forum_profile", "")
    if not content:
        raise HTTPException(status_code=404, detail="尚未生成论坛画像")
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="forum-profile.md"'},
    )


@router.post("/session/reset/{session_id}")
async def session_reset(session_id: str):
    """Reset session: clear messages, restore blank profile."""
    session = profile_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    profile_sessions.reset(session_id)
    return {"ok": True, "session_id": session_id}


@router.get("/session")
async def session_get(session_id: str | None = None):
    """Get or create session, return session_id."""
    sid, _ = profile_sessions.get_or_create(session_id)
    return {"session_id": sid}
