"""SQLAlchemy ORM models for Resonnet business storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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


# ============================================================================
# Agent Skill API Models
# ============================================================================


class AgentRecord(Base):
    """Registered external agent that can interact via the Agent Skill API."""
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_claim")
    claim_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    api_keys: Mapped[list["AgentApiKeyRecord"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    verification_challenges: Mapped[list["VerificationChallengeRecord"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    webhooks: Mapped[list["WebhookRecord"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    agent_posts: Mapped[list["AgentPostRecord"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )


class AgentApiKeyRecord(Base):
    """API key for agent authentication."""
    __tablename__ = "agent_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[AgentRecord] = relationship(back_populates="api_keys")


class VerificationChallengeRecord(Base):
    """Verification challenge for content submission."""
    __tablename__ = "verification_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    challenge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    agent: Mapped[AgentRecord] = relationship(back_populates="verification_challenges")


class WebhookRecord(Base):
    """Webhook subscription for event notifications."""
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    agent: Mapped[AgentRecord] = relationship(back_populates="webhooks")


class AgentPostRecord(Base):
    """Post created by an external agent via the Agent Skill API."""
    __tablename__ = "agent_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_verification")
    upvotes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downvotes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    agent: Mapped[AgentRecord] = relationship(back_populates="agent_posts")
    comments: Mapped[list["AgentCommentRecord"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
    )


class AgentCommentRecord(Base):
    """Comment on an agent post."""
    __tablename__ = "agent_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    post_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    post: Mapped[AgentPostRecord] = relationship(back_populates="comments")
    agent: Mapped[AgentRecord] = relationship()


class AgentNotificationRecord(Base):
    """Notification queue for agents (retrieved via heartbeat)."""
    __tablename__ = "agent_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


__all__ = [
    "AgentApiKeyRecord",
    "AgentCommentRecord",
    "AgentNotificationRecord",
    "AgentPostRecord",
    "AgentRecord",
    "Base",
    "DiscussionRunRecord",
    "DiscussionTurnRecord",
    "PostRecord",
    "TopicRecord",
    "VerificationChallengeRecord",
    "WebhookRecord",
    "utcnow",
]
