"""Likes on tasks and comments.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "likes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "comment_id",
            sa.Integer(),
            sa.ForeignKey("task_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(task_id IS NOT NULL AND comment_id IS NULL) OR "
            "(task_id IS NULL AND comment_id IS NOT NULL)",
            name="ck_like_target",
        ),
        sa.UniqueConstraint("user_id", "task_id", name="uq_like_user_task"),
        sa.UniqueConstraint("user_id", "comment_id", name="uq_like_user_comment"),
    )
    op.create_index("ix_likes_task_id", "likes", ["task_id"])
    op.create_index("ix_likes_comment_id", "likes", ["comment_id"])


def downgrade() -> None:
    op.drop_table("likes")
