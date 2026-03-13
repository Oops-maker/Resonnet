"""Database-backed topic store."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional

from sqlalchemy import select

from app.db.models import DiscussionRunRecord, TopicRecord
from app.db.session import session_scope
from app.core.topic_defaults import DEFAULT_TOPIC_EXPERT_NAMES
from .schemas import (
    DiscussionResult,
    DiscussionStatus,
    Topic,
    TopicCreate,
    TopicMode,
    TopicStatus,
    TopicUpdate,
)

# Legacy compatibility: tests and old docs may still import this symbol.
topics_db: Dict[str, Topic] = {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def _dt_to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _build_discussion_result(topic_row: TopicRecord, run_row: DiscussionRunRecord | None) -> DiscussionResult | None:
    if run_row is None:
        return None
    return DiscussionResult(
        discussion_history="",
        discussion_summary="",
        turns_count=run_row.turns_count or 0,
        cost_usd=run_row.cost_usd,
        completed_at=_dt_to_iso(run_row.completed_at),
    )


def _build_topic(topic_row: TopicRecord, run_row: DiscussionRunRecord | None = None) -> Topic:
    return Topic(
        id=topic_row.id,
        session_id=topic_row.session_id,
        title=topic_row.title,
        body=topic_row.body,
        category=topic_row.category,
        status=TopicStatus(topic_row.status),
        mode=TopicMode(topic_row.mode),
        num_rounds=topic_row.num_rounds,
        expert_names=list(topic_row.expert_names or []),
        discussion_result=_build_discussion_result(topic_row, run_row),
        discussion_status=DiscussionStatus(topic_row.discussion_status),
        created_at=_dt_to_iso(topic_row.created_at),
        updated_at=_dt_to_iso(topic_row.updated_at),
        moderator_mode_id=topic_row.moderator_mode_id,
        moderator_mode_name=topic_row.moderator_mode_name,
        preview_image=topic_row.preview_image,
    )


def initialize_store_from_workspace():
    """Reset stale running discussions after process restart."""
    with session_scope() as session:
        running_topics = session.scalars(
            select(TopicRecord).where(TopicRecord.discussion_status == DiscussionStatus.RUNNING.value)
        ).all()
        now = utc_now()
        for topic in running_topics:
            topic.discussion_status = DiscussionStatus.FAILED.value
            topic.updated_at = now
            if topic.discussion_run is not None:
                topic.discussion_run.status = DiscussionStatus.FAILED.value
                topic.discussion_run.updated_at = now


def sync_store_with_workspace():
    """No-op after moving topic/post state to the database."""
    return None


def create_topic(data: TopicCreate) -> Topic:
    topic_id = str(uuid.uuid4())
    now = utc_now()
    with session_scope() as session:
        topic_row = TopicRecord(
            id=topic_id,
            session_id=topic_id,
            title=data.title,
            body=data.body if data.body else "",
            category=data.category,
            status=TopicStatus.OPEN.value,
            mode=TopicMode.DISCUSSION.value,
            num_rounds=5,
            expert_names=list(DEFAULT_TOPIC_EXPERT_NAMES),
            discussion_status=DiscussionStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )
        session.add(topic_row)
        session.add(
            DiscussionRunRecord(
                topic_id=topic_id,
                status=DiscussionStatus.PENDING.value,
                turns_count=0,
                updated_at=now,
            )
        )
        session.flush()
        session.refresh(topic_row)
        return _build_topic(topic_row, topic_row.discussion_run)


def get_topic(topic_id: str) -> Optional[Topic]:
    with session_scope() as session:
        topic_row = session.get(TopicRecord, topic_id)
        if not topic_row:
            return None
        return _build_topic(topic_row, topic_row.discussion_run)


def list_topics() -> List[Topic]:
    with session_scope() as session:
        topic_rows = session.scalars(
            select(TopicRecord).order_by(TopicRecord.updated_at.desc())
        ).all()
        return [_build_topic(topic_row, topic_row.discussion_run) for topic_row in topic_rows]


def update_topic(topic_id: str, data: TopicUpdate) -> Optional[Topic]:
    with session_scope() as session:
        topic_row = session.get(TopicRecord, topic_id)
        if not topic_row:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(topic_row, key, value)
        topic_row.updated_at = utc_now()
        session.flush()
        session.refresh(topic_row)
        return _build_topic(topic_row, topic_row.discussion_run)


def close_topic(topic_id: str) -> Optional[Topic]:
    with session_scope() as session:
        topic_row = session.get(TopicRecord, topic_id)
        if not topic_row:
            return None
        topic_row.status = TopicStatus.CLOSED.value
        topic_row.updated_at = utc_now()
        session.flush()
        session.refresh(topic_row)
        return _build_topic(topic_row, topic_row.discussion_run)


def update_topic_discussion(
    topic_id: str,
    status: DiscussionStatus,
    result: Optional[DiscussionResult] = None,
) -> Optional[Topic]:
    with session_scope() as session:
        topic_row = session.get(TopicRecord, topic_id)
        if not topic_row:
            return None

        now = utc_now()
        topic_row.discussion_status = status.value
        topic_row.updated_at = now

        run_row = topic_row.discussion_run
        if run_row is None:
            run_row = DiscussionRunRecord(
                topic_id=topic_id,
                status=status.value,
                turns_count=0,
                updated_at=now,
            )
            session.add(run_row)
            topic_row.discussion_run = run_row

        run_row.status = status.value
        run_row.updated_at = now
        if result:
            run_row.turns_count = result.turns_count
            run_row.cost_usd = result.cost_usd
            run_row.completed_at = _parse_iso_datetime(result.completed_at)
        session.flush()
        session.refresh(topic_row)
        return _build_topic(topic_row, topic_row.discussion_run)


def set_topic_moderator_mode_fields(
    topic_id: str,
    *,
    mode_id: str,
    mode_name: str,
    num_rounds: int | None = None,
) -> Optional[Topic]:
    with session_scope() as session:
        topic_row = session.get(TopicRecord, topic_id)
        if not topic_row:
            return None
        topic_row.moderator_mode_id = mode_id
        topic_row.moderator_mode_name = mode_name
        if num_rounds is not None:
            topic_row.num_rounds = num_rounds
        topic_row.updated_at = utc_now()
        session.flush()
        session.refresh(topic_row)
        return _build_topic(topic_row, topic_row.discussion_run)
