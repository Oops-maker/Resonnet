"""In-memory session management: session_id -> {messages, profile}."""
import uuid

from app.services.profile_helper.tools import load_template

_sessions: dict[str, dict] = {}


def get_or_create(session_id: str | None = None) -> tuple[str, dict]:
    """Get or create session. Returns (session_id, session_data)."""
    if session_id and session_id in _sessions:
        s = _sessions[session_id]
        if "forum_profile" not in s:
            s["forum_profile"] = ""
        return session_id, s
    sid = session_id or str(uuid.uuid4())
    _sessions[sid] = {
        "messages": [],
        "profile": load_template(),
        "forum_profile": "",
    }
    return sid, _sessions[sid]


def get(session_id: str) -> dict | None:
    """Get session by id, or None if not found."""
    return _sessions.get(session_id)


def reset(session_id: str) -> dict:
    """Reset session: clear messages and restore template profile."""
    _sessions[session_id] = {
        "messages": [],
        "profile": load_template(),
        "forum_profile": "",
    }
    return _sessions[session_id]
