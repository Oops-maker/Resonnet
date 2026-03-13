"""Import legacy workspace topic.json and posts/*.json into the database."""

from __future__ import annotations

import json
from pathlib import Path

from app.db.migrations import run_db_migrations
from app.db.models import DiscussionRunRecord, PostRecord, TopicRecord
from app.db.session import session_scope
from app.models.discussion_turns import sync_discussion_turns
from app.models.schemas import DiscussionStatus, TopicMode, TopicStatus
from app.models.store import utc_now
from app.core.config import get_workspace_base


def _parse_datetime(value: str | None):
    from datetime import datetime, timezone

    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def import_workspace_topics(workspace_base: Path) -> None:
    topics_dir = workspace_base / "topics"
    if not topics_dir.exists():
        return

    topic_dirs = sorted(p for p in topics_dir.iterdir() if p.is_dir())
    imported_topic_dirs: list[Path] = []
    with session_scope() as session:
        for topic_dir in topic_dirs:
            topic_file = topic_dir / "topic.json"
            if not topic_file.exists():
                continue
            imported_topic_dirs.append(topic_dir)

            raw = json.loads(topic_file.read_text(encoding="utf-8"))
            topic_id = raw["id"]
            discussion_status = raw.get("discussion_status", DiscussionStatus.PENDING.value)
            if discussion_status == DiscussionStatus.RUNNING.value:
                discussion_status = DiscussionStatus.FAILED.value

            topic_row = session.get(TopicRecord, topic_id)
            if topic_row is None:
                topic_row = TopicRecord(
                    id=topic_id,
                    session_id=raw.get("session_id") or topic_id,
                    title=raw["title"],
                    body=raw.get("body", ""),
                    category=raw.get("category"),
                    status=raw.get("status", TopicStatus.OPEN.value),
                    mode=raw.get("mode", TopicMode.DISCUSSION.value),
                    num_rounds=int(raw.get("num_rounds") or 5),
                    expert_names=list(raw.get("expert_names") or []),
                    discussion_status=discussion_status,
                    created_at=_parse_datetime(raw.get("created_at")) or utc_now(),
                    updated_at=_parse_datetime(raw.get("updated_at")) or utc_now(),
                    moderator_mode_id=raw.get("moderator_mode_id"),
                    moderator_mode_name=raw.get("moderator_mode_name"),
                    preview_image=raw.get("preview_image"),
                )
                session.add(topic_row)
            else:
                topic_row.title = raw["title"]
                topic_row.body = raw.get("body", "")
                topic_row.category = raw.get("category")
                topic_row.status = raw.get("status", TopicStatus.OPEN.value)
                topic_row.mode = raw.get("mode", TopicMode.DISCUSSION.value)
                topic_row.num_rounds = int(raw.get("num_rounds") or 5)
                topic_row.expert_names = list(raw.get("expert_names") or [])
                topic_row.discussion_status = discussion_status
                topic_row.created_at = _parse_datetime(raw.get("created_at")) or topic_row.created_at
                topic_row.updated_at = _parse_datetime(raw.get("updated_at")) or utc_now()
                topic_row.moderator_mode_id = raw.get("moderator_mode_id")
                topic_row.moderator_mode_name = raw.get("moderator_mode_name")
                topic_row.preview_image = raw.get("preview_image")

            discussion_result = raw.get("discussion_result") or {}
            run_row = session.get(DiscussionRunRecord, topic_id)
            if run_row is None:
                run_row = DiscussionRunRecord(
                    topic_id=topic_id,
                    status=discussion_status,
                    turns_count=int(discussion_result.get("turns_count") or 0),
                    cost_usd=discussion_result.get("cost_usd"),
                    completed_at=_parse_datetime(discussion_result.get("completed_at")),
                    updated_at=_parse_datetime(raw.get("updated_at")) or utc_now(),
                )
                session.add(run_row)
            else:
                run_row.status = discussion_status
                run_row.turns_count = int(discussion_result.get("turns_count") or 0)
                run_row.cost_usd = discussion_result.get("cost_usd")
                run_row.completed_at = _parse_datetime(discussion_result.get("completed_at"))
                run_row.updated_at = _parse_datetime(raw.get("updated_at")) or utc_now()

            posts_dir = topic_dir / "posts"
            if not posts_dir.exists():
                continue
            for post_file in sorted(posts_dir.glob("*.json")):
                post_raw = json.loads(post_file.read_text(encoding="utf-8"))
                post_row = session.get(PostRecord, post_raw["id"])
                if post_row is None:
                    session.add(
                        PostRecord(
                            id=post_raw["id"],
                            topic_id=topic_id,
                            author=post_raw["author"],
                            author_type=post_raw["author_type"],
                            expert_name=post_raw.get("expert_name"),
                            expert_label=post_raw.get("expert_label"),
                            body=post_raw.get("body", ""),
                            mentions=list(post_raw.get("mentions") or []),
                            in_reply_to_id=post_raw.get("in_reply_to_id"),
                            status=post_raw.get("status", "completed"),
                            created_at=_parse_datetime(post_raw["created_at"]) or utc_now(),
                        )
                    )
                else:
                    post_row.topic_id = topic_id
                    post_row.author = post_raw["author"]
                    post_row.author_type = post_raw["author_type"]
                    post_row.expert_name = post_raw.get("expert_name")
                    post_row.expert_label = post_raw.get("expert_label")
                    post_row.body = post_raw.get("body", "")
                    post_row.mentions = list(post_raw.get("mentions") or [])
                    post_row.in_reply_to_id = post_raw.get("in_reply_to_id")
                    post_row.status = post_raw.get("status", "completed")
                    post_row.created_at = _parse_datetime(post_raw["created_at"]) or utc_now()

    for topic_dir in imported_topic_dirs:
        sync_discussion_turns(topic_dir)


def main() -> None:
    run_db_migrations()
    import_workspace_topics(get_workspace_base())


if __name__ == "__main__":
    main()
