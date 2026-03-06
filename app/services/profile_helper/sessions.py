"""In-memory session management with lightweight cleanup."""
import os
import time
import uuid

from app.services.profile_helper.tools import load_template

_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = max(60, int(os.getenv("PROFILE_HELPER_SESSION_TTL_SECONDS", "3600")))
SESSION_MAX_COUNT = max(10, int(os.getenv("PROFILE_HELPER_SESSION_MAX_COUNT", "1000")))


def _now() -> float:
    return time.time()


def _new_session() -> dict:
    now = _now()
    return {
        "messages": [],
        "profile": load_template(),
        "forum_profile": "",
        "created_at": now,
        "updated_at": now,
    }


def _touch(session: dict) -> None:
    session["updated_at"] = _now()


def _is_expired(session: dict, now: float) -> bool:
    updated = float(session.get("updated_at") or 0)
    return (now - updated) > SESSION_TTL_SECONDS


def _cleanup() -> None:
    """Drop expired sessions and cap total count."""
    now = _now()
    expired = [sid for sid, s in _sessions.items() if _is_expired(s, now)]
    for sid in expired:
        _sessions.pop(sid, None)

    overflow = len(_sessions) - SESSION_MAX_COUNT
    if overflow > 0:
        oldest = sorted(
            _sessions.items(),
            key=lambda kv: float(kv[1].get("updated_at") or 0),
        )
        for sid, _ in oldest[:overflow]:
            _sessions.pop(sid, None)


def get_or_create(session_id: str | None = None) -> tuple[str, dict]:
    """Get or create session. Returns (session_id, session_data)."""
    _cleanup()
    if session_id and session_id in _sessions:
        s = _sessions[session_id]
        if "forum_profile" not in s:
            s["forum_profile"] = ""
        _touch(s)
        return session_id, s
    sid = session_id or str(uuid.uuid4())
    _sessions[sid] = _new_session()
    _cleanup()
    return sid, _sessions[sid]


def get(session_id: str) -> dict | None:
    """Get session by id, or None if not found."""
    s = _sessions.get(session_id)
    if not s:
        return None
    if _is_expired(s, _now()):
        _sessions.pop(session_id, None)
        return None
    _touch(s)
    return s


def reset(session_id: str) -> dict:
    """Reset session: clear messages and restore template profile."""
    _sessions[session_id] = _new_session()
    return _sessions[session_id]


def list_ids() -> list[str]:
    """List current active session IDs after best-effort cleanup."""
    _cleanup()
    return list(_sessions.keys())
