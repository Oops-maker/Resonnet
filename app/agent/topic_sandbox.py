"""Topic-level sandbox isolation manager.

Implements isolation principles from session-level-isolation-implementation.md,
applied at topic granularity:

- Topic as the minimum isolation unit (workspace/topics/{topic_id}/)
- Per-topic exclusive lock for discussion operations (one at a time)
- Concurrent-but-tracked expert reply operations (audit trail only)
- Workspace boundary validation (path must stay inside topic workspace)
- Structured audit logging  → config/audit.jsonl
- Sandbox state metadata    → config/sandbox_meta.json

Design principles (from reference doc):
1. Persistence and execution decoupled: workspace long-lived, sandbox ephemeral
2. Default minimal permissions: agents constrained by tools + prompt boundary
3. Auditable: every agent invocation logged with start/end/error events
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-topic in-memory operation registry
# ---------------------------------------------------------------------------

class _TopicRegistry:
    """Thread-safe in-memory registry of active topic operations.

    Tracks:
    - Exclusive operations (discussion): only one allowed per topic at a time.
    - Expert reply operations: multiple allowed concurrently per topic,
      tracked for audit purposes.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # topic_id -> {"operation": str, "agent_id": str, "started_at": str}
        self._exclusive: dict[str, dict] = {}
        # topic_id -> set of active agent_ids (non-exclusive, e.g. expert replies)
        self._replies: dict[str, set[str]] = {}

    def register_exclusive(self, topic_id: str, operation: str, agent_id: str) -> bool:
        """Try to register an exclusive operation. Returns True if registered."""
        with self._lock:
            if topic_id in self._exclusive:
                return False
            self._exclusive[topic_id] = {
                "operation": operation,
                "agent_id": agent_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            return True

    def unregister_exclusive(self, topic_id: str, agent_id: str) -> None:
        with self._lock:
            entry = self._exclusive.get(topic_id)
            if entry and entry.get("agent_id") == agent_id:
                del self._exclusive[topic_id]

    def get_active_exclusive(self, topic_id: str) -> Optional[dict]:
        with self._lock:
            return dict(self._exclusive[topic_id]) if topic_id in self._exclusive else None

    def is_exclusive_locked(self, topic_id: str) -> bool:
        with self._lock:
            return topic_id in self._exclusive

    def register_reply(self, topic_id: str, agent_id: str) -> None:
        with self._lock:
            self._replies.setdefault(topic_id, set()).add(agent_id)

    def unregister_reply(self, topic_id: str, agent_id: str) -> None:
        with self._lock:
            if topic_id in self._replies:
                self._replies[topic_id].discard(agent_id)

    def get_active_replies(self, topic_id: str) -> set[str]:
        with self._lock:
            return set(self._replies.get(topic_id, set()))


# Module-level singleton
_registry = _TopicRegistry()


# ---------------------------------------------------------------------------
# Workspace path validation
# ---------------------------------------------------------------------------

def validate_workspace_path(path: str | Path, ws_path: Path) -> bool:
    """Return True if *path* is strictly within *ws_path* (topic workspace).

    Uses ``Path.relative_to()`` on resolved paths so symlinks and ``..``
    sequences cannot escape the boundary.
    """
    try:
        Path(path).resolve().relative_to(ws_path.resolve())
        return True
    except (ValueError, RuntimeError):
        return False


def assert_workspace_path(path: str | Path, ws_path: Path, context: str = "") -> None:
    """Raise ``ValueError`` if *path* is outside *ws_path*."""
    if not validate_workspace_path(path, ws_path):
        msg = f"Path '{path}' is outside topic workspace '{ws_path}'"
        if context:
            msg = f"{msg} [{context}]"
        logger.error(msg)
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def log_audit_event(ws_path: Path, event_type: str, details: dict) -> None:
    """Append a structured audit event to ``config/audit.jsonl``.

    Each line is a JSON object with ``timestamp`` and ``event_type`` fields
    merged with *details*.  File is created on first write.
    """
    audit_file = ws_path / "config" / "audit.jsonl"
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **details,
    }
    try:
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to write audit event to %s: %s", audit_file, exc)


# ---------------------------------------------------------------------------
# Sandbox metadata persistence
# ---------------------------------------------------------------------------

def _read_sandbox_meta(ws_path: Path) -> dict:
    meta_file = ws_path / "config" / "sandbox_meta.json"
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_sandbox_meta(ws_path: Path, meta: dict) -> None:
    meta_file = ws_path / "config" / "sandbox_meta.json"
    try:
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        meta_file.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning("Failed to write sandbox meta: %s", exc)


def init_sandbox_meta(ws_path: Path) -> None:
    """Initialize sandbox metadata for a newly created topic workspace.

    Idempotent: does nothing if ``config/sandbox_meta.json`` already exists.
    """
    meta_file = ws_path / "config" / "sandbox_meta.json"
    if not meta_file.exists():
        now = datetime.now(timezone.utc).isoformat()
        _write_sandbox_meta(ws_path, {
            "created_at": now,
            "status": "idle",
            "last_active_at": now,
        })


def update_sandbox_meta(
    ws_path: Path,
    status: str,
    active_operation: Optional[str] = None,
    agent_id: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Update ``config/sandbox_meta.json`` with current sandbox state.

    Args:
        ws_path: Topic workspace root path.
        status: ``"idle"`` or ``"running"``.
        active_operation: Human-readable operation name; cleared when ``status="idle"``.
        agent_id: Current agent identifier; used for traceability.
        error: Last error message to persist (best-effort).
    """
    now = datetime.now(timezone.utc).isoformat()
    meta = _read_sandbox_meta(ws_path)

    if "created_at" not in meta:
        meta["created_at"] = now

    meta["status"] = status
    meta["last_active_at"] = now

    if agent_id is not None:
        meta["last_agent_id"] = agent_id

    if status == "running" and active_operation is not None:
        meta["active_operation"] = active_operation
    elif status == "idle":
        meta.pop("active_operation", None)

    if error is not None:
        meta["last_error"] = error

    _write_sandbox_meta(ws_path, meta)


def get_sandbox_status(topic_id: str, ws_path: Path) -> dict:
    """Return the current sandbox status for a topic.

    Merges authoritative in-memory state (running operations) with persisted
    disk metadata (last_active_at, last_error, etc.).
    """
    active_excl = _registry.get_active_exclusive(topic_id)
    active_replies = _registry.get_active_replies(topic_id)

    if active_excl:
        return {
            "status": "running",
            "operation": active_excl.get("operation"),
            "agent_id": active_excl.get("agent_id"),
            "started_at": active_excl.get("started_at"),
            "active_expert_replies": list(active_replies),
        }

    if active_replies:
        return {
            "status": "running",
            "operation": "expert_replies",
            "active_expert_replies": list(active_replies),
        }

    # No in-memory activity — return persisted metadata
    meta = _read_sandbox_meta(ws_path)
    return {
        "status": meta.get("status", "idle"),
        "last_active_at": meta.get("last_active_at"),
        "last_agent_id": meta.get("last_agent_id"),
        "last_error": meta.get("last_error"),
        "active_expert_replies": [],
    }


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class TopicLockError(Exception):
    """Raised when a topic is already locked for an exclusive operation."""

    def __init__(self, topic_id: str, operation: str) -> None:
        self.topic_id = topic_id
        self.operation = operation
        super().__init__(
            f"Topic '{topic_id}' is locked for operation: {operation}"
        )


# ---------------------------------------------------------------------------
# Context managers
# ---------------------------------------------------------------------------

@contextmanager
def exclusive_topic_sandbox(
    topic_id: str,
    ws_path: Path,
    operation: str,
) -> Generator[str, None, None]:
    """Context manager for exclusive topic operations (e.g., discussion).

    Guarantees that only one exclusive operation runs per topic at a time.
    Logs audit events and updates sandbox metadata on enter/exit/error.

    Safe to use inside ``async`` functions as a synchronous ``with`` block
    (the registry uses threading.Lock which is non-blocking on contested paths).

    Yields:
        agent_id (str): Short unique identifier for this invocation.

    Raises:
        TopicLockError: If the topic is already locked for another operation.
    """
    agent_id = uuid.uuid4().hex[:8]

    if not _registry.register_exclusive(topic_id, operation, agent_id):
        active = _registry.get_active_exclusive(topic_id)
        raise TopicLockError(
            topic_id,
            active.get("operation", "unknown") if active else "unknown",
        )

    log_audit_event(ws_path, "sandbox_enter", {
        "topic_id": topic_id,
        "operation": operation,
        "agent_id": agent_id,
        "exclusive": True,
    })
    update_sandbox_meta(ws_path, "running", active_operation=operation, agent_id=agent_id)
    logger.info("[Sandbox] topic=%s locked for %s (agent_id=%s)", topic_id, operation, agent_id)

    try:
        yield agent_id
    except Exception as exc:
        log_audit_event(ws_path, "sandbox_error", {
            "topic_id": topic_id,
            "operation": operation,
            "agent_id": agent_id,
            "error": str(exc)[:500],
        })
        update_sandbox_meta(ws_path, "idle", error=str(exc)[:500])
        raise
    finally:
        _registry.unregister_exclusive(topic_id, agent_id)
        log_audit_event(ws_path, "sandbox_exit", {
            "topic_id": topic_id,
            "operation": operation,
            "agent_id": agent_id,
        })
        # Only reset to idle if no replies are still active
        if not _registry.get_active_replies(topic_id):
            update_sandbox_meta(ws_path, "idle")
        logger.info(
            "[Sandbox] topic=%s unlocked after %s (agent_id=%s)",
            topic_id, operation, agent_id,
        )


@contextmanager
def tracked_topic_sandbox(
    topic_id: str,
    ws_path: Path,
    operation: str,
) -> Generator[str, None, None]:
    """Context manager for tracked (non-exclusive) topic operations (e.g., expert reply).

    Multiple expert replies may run concurrently per topic, but each is
    registered and audited individually.  Does NOT prevent concurrent
    exclusive operations from registering (the API layer handles that via
    the discussion_status check).

    Safe to use inside daemon threads with their own event loops.

    Yields:
        agent_id (str): Short unique identifier for this invocation.
    """
    agent_id = uuid.uuid4().hex[:8]

    _registry.register_reply(topic_id, agent_id)
    log_audit_event(ws_path, "sandbox_enter", {
        "topic_id": topic_id,
        "operation": operation,
        "agent_id": agent_id,
        "exclusive": False,
    })
    update_sandbox_meta(ws_path, "running", active_operation=operation, agent_id=agent_id)
    logger.info("[Sandbox] topic=%s tracking %s (agent_id=%s)", topic_id, operation, agent_id)

    try:
        yield agent_id
    except Exception as exc:
        log_audit_event(ws_path, "sandbox_error", {
            "topic_id": topic_id,
            "operation": operation,
            "agent_id": agent_id,
            "error": str(exc)[:500],
        })
        raise
    finally:
        _registry.unregister_reply(topic_id, agent_id)
        log_audit_event(ws_path, "sandbox_exit", {
            "topic_id": topic_id,
            "operation": operation,
            "agent_id": agent_id,
        })
        # Only reset to idle if no more active operations for this topic
        if (
            not _registry.get_active_replies(topic_id)
            and not _registry.is_exclusive_locked(topic_id)
        ):
            update_sandbox_meta(ws_path, "idle")
        logger.info(
            "[Sandbox] topic=%s untracked %s (agent_id=%s)",
            topic_id, operation, agent_id,
        )
