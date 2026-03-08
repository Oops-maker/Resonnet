"""In-memory session management with cleanup and profile auto-save."""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import date
from pathlib import Path

from app.core.config import get_profile_helper_profiles_dir
from app.services.profile_helper.tools import load_template

_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = max(60, int(os.getenv("PROFILE_HELPER_SESSION_TTL_SECONDS", "3600")))
SESSION_MAX_COUNT = max(10, int(os.getenv("PROFILE_HELPER_SESSION_MAX_COUNT", "1000")))
PLACEHOLDER_IDENTIFIERS = {"[姓名/标识]", "姓名/标识"}
PROFILE_TITLE_PREFIXES = (
    "# 科研人员画像 — ",
    "# 科研数字分身 — ",
)


def _now() -> float:
    return time.time()


def _load_template_with_date() -> str:
    today_str = date.today().strftime("%Y-%m-%d")
    return load_template().replace("YYYY-MM-DD", today_str)


def _today_unnamed() -> str:
    return f"unnamed-{date.today().strftime('%Y-%m-%d')}"


def _sanitize_identifier(identifier: str) -> str:
    cleaned = identifier.strip()
    if cleaned in PLACEHOLDER_IDENTIFIERS or not cleaned:
        return _today_unnamed()
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or _today_unnamed()


def _extract_profile_identifier(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for prefix in PROFILE_TITLE_PREFIXES:
            if stripped.startswith(prefix):
                return _sanitize_identifier(stripped[len(prefix) :])
        if stripped.startswith("# "):
            return _sanitize_identifier(stripped[2:])
        break
    return _today_unnamed()


def _normalize_existing_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    return Path(path_value)


def _profiles_dir() -> Path:
    return get_profile_helper_profiles_dir()


def _session_suffix(session: dict) -> str:
    sid = session.get("session_id") or ""
    if sid:
        return sid.replace("-", "")[:8]
    return uuid.uuid4().hex[:8]


def _target_profile_path(content: str, session: dict) -> Path:
    identifier = _extract_profile_identifier(content)
    suffix = _session_suffix(session)
    return _profiles_dir() / f"{identifier}-{suffix}.md"


def _target_forum_profile_path(session: dict) -> Path:
    profile_path = _normalize_existing_path(session.get("profile_path"))
    if not profile_path:
        profile_path = _target_profile_path(session.get("profile", ""), session)
    return profile_path.with_name(f"{profile_path.stem}-论坛画像.md")


def _relocate_file_if_needed(current_path: Path | None, target_path: Path) -> None:
    if not current_path or current_path == target_path or not current_path.exists():
        return
    if target_path.exists():
        current_path.unlink()
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.rename(target_path)


def _new_session(session_id: str) -> dict:
    now = _now()
    return {
        "session_id": session_id,
        "messages": [],
        "profile": _load_template_with_date(),
        "forum_profile": "",
        "profile_path": None,
        "forum_profile_path": None,
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


def save_profile(session: dict, content: str) -> Path:
    """Persist the development profile to disk and session memory."""
    profiles_dir = _profiles_dir()
    profiles_dir.mkdir(parents=True, exist_ok=True)

    target_path = _target_profile_path(content, session)
    current_path = _normalize_existing_path(session.get("profile_path"))
    _relocate_file_if_needed(current_path, target_path)
    target_path.write_text(content, encoding="utf-8")

    session["profile"] = content
    session["profile_path"] = str(target_path)

    forum_content = session.get("forum_profile", "")
    if forum_content:
        forum_target_path = _target_forum_profile_path(session)
        forum_current_path = _normalize_existing_path(session.get("forum_profile_path"))
        _relocate_file_if_needed(forum_current_path, forum_target_path)
        forum_target_path.write_text(forum_content, encoding="utf-8")
        session["forum_profile_path"] = str(forum_target_path)

    _touch(session)
    return target_path


def save_forum_profile(session: dict, content: str) -> Path:
    """Persist the forum profile to disk and session memory."""
    profiles_dir = _profiles_dir()
    profiles_dir.mkdir(parents=True, exist_ok=True)

    profile_content = session.get("profile", "")
    if profile_content:
        save_profile(session, profile_content)

    target_path = _target_forum_profile_path(session)
    current_path = _normalize_existing_path(session.get("forum_profile_path"))
    _relocate_file_if_needed(current_path, target_path)
    target_path.write_text(content, encoding="utf-8")

    session["forum_profile"] = content
    session["forum_profile_path"] = str(target_path)
    _touch(session)
    return target_path


def get_or_create(session_id: str | None = None) -> tuple[str, dict]:
    """Get or create session. Returns (session_id, session_data)."""
    _cleanup()
    if session_id and session_id in _sessions:
        s = _sessions[session_id]
        s["session_id"] = session_id
        if "forum_profile" not in s:
            s["forum_profile"] = ""
        if "profile_path" not in s:
            s["profile_path"] = None
        if "forum_profile_path" not in s:
            s["forum_profile_path"] = None
        _touch(s)
        return session_id, s
    sid = session_id or str(uuid.uuid4())
    _sessions[sid] = _new_session(sid)
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
    _sessions[session_id] = _new_session(session_id)
    return _sessions[session_id]
