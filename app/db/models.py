"""SQLAlchemy ORM models for Resonnet business storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TopicRecord(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    num_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    expert_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    discussion_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    moderator_mode_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    moderator_mode_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preview_image: Mapped[str | None] = mapped_column(Text, nullable=True)

    discussion_run: Mapped["DiscussionRunRecord | None"] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
        uselist=False,
    )
    posts: Mapped[list["PostRecord"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
    )


class DiscussionRunRecord(Base):
    __tablename__ = "discussion_runs"

    topic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    turns_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    topic: Mapped[TopicRecord] = relationship(back_populates="discussion_run")


class DiscussionTurnRecord(Base):
    __tablename__ = "discussion_turns"
    __table_args__ = (
        UniqueConstraint("topic_id", "turn_key", name="uq_discussion_turns_topic_turn_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_key: Mapped[str] = mapped_column(String(255), nullable=False)
    round_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expert_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expert_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    topic: Mapped[TopicRecord] = relationship()


class PostRecord(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), nullable=False)
    expert_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expert_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mentions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    in_reply_to_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    topic: Mapped[TopicRecord] = relationship(back_populates="posts")


__all__ = [
    "Base",
    "DiscussionRunRecord",
    "DiscussionTurnRecord",
    "PostRecord",
    "TopicRecord",
    "utcnow",
]
