"""Topic posts backed by the database."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import uuid

from sqlalchemy import select

from app.db.models import PostRecord
from app.db.session import session_scope

logger = logging.getLogger(__name__)


def _topic_id_from_ws_path(ws_path: Path) -> str:
    return ws_path.name


def _parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _post_to_dict(record: PostRecord) -> dict:
    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "id": record.id,
        "topic_id": record.topic_id,
        "author": record.author,
        "author_type": record.author_type,
        "expert_name": record.expert_name,
        "expert_label": record.expert_label,
        "body": record.body,
        "mentions": list(record.mentions or []),
        "in_reply_to_id": record.in_reply_to_id,
        "status": record.status,
        "created_at": created_at.isoformat(),
    }


def _refresh_posts_context(ws_path: Path) -> None:
    shared_dir = ws_path / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    context_path = shared_dir / "posts_context.md"
    posts = load_posts(ws_path)
    if not posts:
        context_path.write_text("# Posts Context\n\n_No posts yet._\n", encoding="utf-8")
        return

    parts = ["# Posts Context"]
    for post in posts:
        author = post.get("expert_label") or post.get("author") or "unknown"
        status = post.get("status", "completed")
        created_at = post.get("created_at", "")
        header = f"## {author} ({post.get('author_type', 'unknown')}, {status})"
        body = post.get("body", "").strip() or "_empty_"
        parts.append(f"{header}\n\n- created_at: {created_at}\n- id: {post.get('id')}\n\n{body}")
    context_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def save_post(ws_path: Path, post: dict) -> Path:
    """Upsert a post into the database. Returns a virtual workspace path."""
    topic_id = _topic_id_from_ws_path(ws_path)
    created_at = _parse_iso_datetime(post["created_at"])
    with session_scope() as session:
        existing = session.get(PostRecord, post["id"])
        if existing is None:
            existing = PostRecord(
                id=post["id"],
                topic_id=topic_id,
                author=post["author"],
                author_type=post["author_type"],
                expert_name=post.get("expert_name"),
                expert_label=post.get("expert_label"),
                body=post["body"],
                mentions=list(post.get("mentions") or []),
                in_reply_to_id=post.get("in_reply_to_id"),
                status=post.get("status", "completed"),
                created_at=created_at,
            )
            session.add(existing)
        else:
            existing.topic_id = topic_id
            existing.author = post["author"]
            existing.author_type = post["author_type"]
            existing.expert_name = post.get("expert_name")
            existing.expert_label = post.get("expert_label")
            existing.body = post["body"]
            existing.mentions = list(post.get("mentions") or [])
            existing.in_reply_to_id = post.get("in_reply_to_id")
            existing.status = post.get("status", existing.status)
            existing.created_at = created_at
        logger.info("Saved post %s to database for topic %s", post["id"], topic_id)
    _refresh_posts_context(ws_path)
    return ws_path / "posts" / f"{post['id']}.json"


def load_posts(ws_path: Path) -> list[dict]:
    """Load all posts for a topic ordered by created_at ascending."""
    topic_id = _topic_id_from_ws_path(ws_path)
    with session_scope() as session:
        rows = session.scalars(
            select(PostRecord)
            .where(PostRecord.topic_id == topic_id)
            .order_by(PostRecord.created_at.asc(), PostRecord.id.asc())
        ).all()
        return [_post_to_dict(row) for row in rows]


def load_post(ws_path: Path, post_id: str) -> dict | None:
    """Load a single post by id and topic."""
    topic_id = _topic_id_from_ws_path(ws_path)
    with session_scope() as session:
        row = session.scalar(
            select(PostRecord).where(
                PostRecord.id == post_id,
                PostRecord.topic_id == topic_id,
            )
        )
        if row is None:
            return None
        return _post_to_dict(row)


def make_post(
    topic_id: str,
    author: str,
    author_type: str,
    body: str,
    expert_name: str | None = None,
    expert_label: str | None = None,
    in_reply_to_id: str | None = None,
    status: str = "completed",
) -> dict:
    """Build a new post dict (not yet persisted)."""
    mentions = re.findall(r"@(\w+)", body)
    return {
        "id": str(uuid.uuid4()),
        "topic_id": topic_id,
        "author": author,
        "author_type": author_type,
        "expert_name": expert_name,
        "expert_label": expert_label,
        "body": body,
        "mentions": mentions,
        "in_reply_to_id": in_reply_to_id,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
