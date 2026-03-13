"""Create topic storage tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260313_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topics",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("num_rounds", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("expert_names", sa.JSON(), nullable=False),
        sa.Column("discussion_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("moderator_mode_id", sa.String(length=64), nullable=True),
        sa.Column("moderator_mode_name", sa.String(length=255), nullable=True),
        sa.Column("preview_image", sa.Text(), nullable=True),
    )
    op.create_index("ix_topics_updated_at", "topics", ["updated_at"], unique=False)
    op.create_index("ix_topics_discussion_status", "topics", ["discussion_status"], unique=False)

    op.create_table(
        "discussion_runs",
        sa.Column("topic_id", sa.String(length=36), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("turns_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("topic_id", sa.String(length=36), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("author_type", sa.String(length=32), nullable=False),
        sa.Column("expert_name", sa.String(length=255), nullable=True),
        sa.Column("expert_label", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("mentions", sa.JSON(), nullable=False),
        sa.Column("in_reply_to_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_posts_topic_id", "posts", ["topic_id"], unique=False)
    op.create_index("ix_posts_created_at", "posts", ["created_at"], unique=False)
    op.create_index("ix_posts_in_reply_to_id", "posts", ["in_reply_to_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_posts_in_reply_to_id", table_name="posts")
    op.drop_index("ix_posts_created_at", table_name="posts")
    op.drop_index("ix_posts_topic_id", table_name="posts")
    op.drop_table("posts")
    op.drop_table("discussion_runs")
    op.drop_index("ix_topics_discussion_status", table_name="topics")
    op.drop_index("ix_topics_updated_at", table_name="topics")
    op.drop_table("topics")
