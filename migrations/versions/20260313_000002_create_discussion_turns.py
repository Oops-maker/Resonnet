"""create discussion turns table

Revision ID: 20260313_000002
Revises: 20260313_000001
Create Date: 2026-03-13 22:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260313_000002"
down_revision = "20260313_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discussion_turns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("topic_id", sa.String(length=36), nullable=False),
        sa.Column("turn_key", sa.String(length=255), nullable=False),
        sa.Column("round_num", sa.Integer(), nullable=True),
        sa.Column("expert_name", sa.String(length=255), nullable=True),
        sa.Column("expert_label", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id", "turn_key", name="uq_discussion_turns_topic_turn_key"),
    )
    op.create_index(op.f("ix_discussion_turns_topic_id"), "discussion_turns", ["topic_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_discussion_turns_topic_id"), table_name="discussion_turns")
    op.drop_table("discussion_turns")
