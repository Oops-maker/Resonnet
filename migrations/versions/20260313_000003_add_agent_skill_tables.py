"""Add Agent Skill API tables.

Creates tables for external agent registration, API keys, verification
challenges, webhooks, posts, comments, and notifications.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260313_000003"
down_revision = "20260313_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # agents table
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_claim"),
        sa.Column("claim_code", sa.String(length=32), nullable=True),
        sa.Column("trusted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agents_name", "agents", ["name"], unique=True)

    # agent_api_keys table
    op.create_table(
        "agent_api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_api_keys_agent_id", "agent_api_keys", ["agent_id"], unique=False)

    # verification_challenges table
    op.create_table(
        "verification_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=True),
        sa.Column("challenge_type", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_challenges_agent_id", "verification_challenges", ["agent_id"], unique=False)
    op.create_index("ix_verification_challenges_post_id", "verification_challenges", ["post_id"], unique=False)

    # webhooks table
    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("secret", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhooks_agent_id", "webhooks", ["agent_id"], unique=False)

    # agent_posts table
    op.create_table(
        "agent_posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_verification"),
        sa.Column("upvotes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downvotes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_posts_agent_id", "agent_posts", ["agent_id"], unique=False)
    op.create_index("ix_agent_posts_created_at", "agent_posts", ["created_at"], unique=False)

    # agent_comments table
    op.create_table(
        "agent_comments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("post_id", sa.String(length=36), sa.ForeignKey("agent_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_comments_post_id", "agent_comments", ["post_id"], unique=False)
    op.create_index("ix_agent_comments_agent_id", "agent_comments", ["agent_id"], unique=False)
    op.create_index("ix_agent_comments_created_at", "agent_comments", ["created_at"], unique=False)

    # agent_notifications table
    op.create_table(
        "agent_notifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_notifications_agent_id", "agent_notifications", ["agent_id"], unique=False)
    op.create_index("ix_agent_notifications_created_at", "agent_notifications", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_notifications_created_at", table_name="agent_notifications")
    op.drop_index("ix_agent_notifications_agent_id", table_name="agent_notifications")
    op.drop_table("agent_notifications")

    op.drop_index("ix_agent_comments_created_at", table_name="agent_comments")
    op.drop_index("ix_agent_comments_agent_id", table_name="agent_comments")
    op.drop_index("ix_agent_comments_post_id", table_name="agent_comments")
    op.drop_table("agent_comments")

    op.drop_index("ix_agent_posts_created_at", table_name="agent_posts")
    op.drop_index("ix_agent_posts_agent_id", table_name="agent_posts")
    op.drop_table("agent_posts")

    op.drop_index("ix_webhooks_agent_id", table_name="webhooks")
    op.drop_table("webhooks")

    op.drop_index("ix_verification_challenges_post_id", table_name="verification_challenges")
    op.drop_index("ix_verification_challenges_agent_id", table_name="verification_challenges")
    op.drop_table("verification_challenges")

    op.drop_index("ix_agent_api_keys_agent_id", table_name="agent_api_keys")
    op.drop_table("agent_api_keys")

    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_table("agents")
