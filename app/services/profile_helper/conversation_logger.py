"""Append-only conversation analytics logger — per-session JSONL.

Records EVERYTHING that happens in a session:
  - user messages
  - assistant text responses
  - UI blocks shown (choice / text_input / rating / copyable / actions)
  - LLM tool calls (read_skill, read_doc, write_profile, ask_choice, ...)
  - tool call results (truncated to avoid huge payloads)
  - fast-path events (welcome, ai-memory prompt generated)
  - errors

Log location:  workspace/profile_helper/logs/sessions/{session_id}.jsonl
Log format:    one JSON object per line (JSONL / NDJSON)
               {ts, session_id, user_id, event_type, role, content, extra}

This file is NEVER deleted by session resets or cleanup operations.
Each session gets its own file, making it easy to replay and debug.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

_logger = logging.getLogger(__name__)


# ── 日志目录 ─────────────────────────────────────────────────────────────────

def _sessions_log_dir() -> Path:
    base = os.getenv("PROFILE_HELPER_LOG_DIR", "")
    if base:
        return Path(base) / "sessions"
    workspace = Path(os.getenv("WORKSPACE_BASE", "./workspace")).resolve()
    return workspace / "profile_helper" / "logs" / "sessions"


def _session_log_path(session_id: str) -> Path:
    log_dir = _sessions_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{session_id}.jsonl"


# ── 核心写入 ──────────────────────────────────────────────────────────────────

def _write(session_id: str, user_id, event_type: str, **fields) -> None:
    """Low-level append one JSONL entry to the session log file."""
    try:
        entry: dict = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "session_id": session_id,
            "user_id": user_id,
            "event": event_type,
        }
        entry.update(fields)
        path = _session_log_path(session_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        _logger.warning("conversation_logger write failed (non-fatal): %s", exc)


def _sid(session: dict) -> str:
    return session.get("session_id", "unknown")


def _uid(session: dict):
    return session.get("user_id")


# ── 公共 API ──────────────────────────────────────────────────────────────────

def log_user_message(session: dict, content: str) -> None:
    """Log what the user typed / pasted."""
    _write(_sid(session), _uid(session),
           event_type="user_message",
           content=content[:10000])


def log_assistant_text(session: dict, content: str) -> None:
    """Log a text block returned by the assistant."""
    _write(_sid(session), _uid(session),
           event_type="assistant_text",
           content=content[:5000])


def log_ui_block(session: dict, block: dict) -> None:
    """Log a single UI block shown to the user."""
    btype = block.get("type", "unknown")
    entry: dict = {"block_type": btype}

    if btype == "text":
        entry["content"] = block.get("content", "")[:5000]
    elif btype == "choice":
        entry["question"] = block.get("question", "")
        entry["options"] = [
            {"id": o.get("id"), "label": o.get("label")}
            for o in block.get("options", [])
        ]
    elif btype == "text_input":
        entry["question"] = block.get("question", "")
        entry["placeholder"] = block.get("placeholder", "")
    elif btype == "rating":
        entry["question"] = block.get("question", "")
        entry["min_val"] = block.get("min_val")
        entry["max_val"] = block.get("max_val")
    elif btype == "copyable":
        entry["title"] = block.get("title", "")
        # 只记录前200字，避免把完整提示词存入日志
        entry["content_preview"] = (block.get("content") or "")[:200]
    elif btype == "actions":
        entry["message"] = block.get("message", "")
        entry["buttons"] = [
            {"id": b.get("id"), "label": b.get("label")}
            for b in block.get("buttons", [])
        ]
    elif btype == "chart":
        entry["chart_type"] = block.get("chart_type", "")
        entry["title"] = block.get("title", "")

    _write(_sid(session), _uid(session), event_type="ui_block", **entry)


def log_tool_call(session: dict, tool_name: str, arguments: dict) -> None:
    """Log an LLM tool call (before execution)."""
    # 对大型参数截断，避免日志过大
    args_str = json.dumps(arguments, ensure_ascii=False)
    if len(args_str) > 2000:
        args_str = args_str[:2000] + "...[truncated]"
    _write(_sid(session), _uid(session),
           event_type="tool_call",
           tool=tool_name,
           arguments=args_str)


def log_tool_result(session: dict, tool_name: str, result: str) -> None:
    """Log the result of a tool call (after execution)."""
    preview = result[:500] + ("...[truncated]" if len(result) > 500 else "")
    _write(_sid(session), _uid(session),
           event_type="tool_result",
           tool=tool_name,
           result_preview=preview,
           result_length=len(result))


def log_fast_path(session: dict, path_name: str) -> None:
    """Log when a fast-path (no LLM) is triggered."""
    _write(_sid(session), _uid(session),
           event_type="fast_path",
           path=path_name)


def log_llm_call(session: dict, model: str, message_count: int) -> None:
    """Log when an LLM API call is made."""
    _write(_sid(session), _uid(session),
           event_type="llm_call",
           model=model,
           message_count=message_count)


def log_llm_response(session: dict, has_tool_calls: bool, text_length: int) -> None:
    """Log the LLM's response metadata."""
    _write(_sid(session), _uid(session),
           event_type="llm_response",
           has_tool_calls=has_tool_calls,
           text_length=text_length)


def log_error(session: dict, error: str) -> None:
    """Log an error that occurred during processing."""
    _write(_sid(session), _uid(session),
           event_type="error",
           error=error[:1000])
