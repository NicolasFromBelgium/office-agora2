"""Toggle likes on tasks and comments. No activity, no notifications."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.models import Like, TaskComment, User


def _names(likes: list[Like]) -> list[str]:
    return [item.user.display_name for item in likes if item.user]


def button_context(likes: list[Like], user_id: int) -> dict:
    return {
        "liked": any(item.user_id == user_id for item in likes),
        "count": len(likes),
        "names": _names(likes),
    }


def likes_for_task(session: Session, task_id: int) -> list[Like]:
    return list(
        session.scalars(
            select(Like)
            .where(Like.task_id == task_id, Like.comment_id.is_(None))
            .options(selectinload(Like.user))
            .order_by(Like.id)
        )
    )


def likes_for_comment(session: Session, comment_id: int) -> list[Like]:
    return list(
        session.scalars(
            select(Like)
            .where(Like.comment_id == comment_id)
            .options(selectinload(Like.user))
            .order_by(Like.id)
        )
    )


def toggle_task_like(session: Session, *, user: User, task_id: int) -> tuple[bool, list[Like]]:
    existing = session.scalar(
        select(Like).where(
            Like.user_id == user.id,
            Like.task_id == task_id,
            Like.comment_id.is_(None),
        )
    )
    if existing is not None:
        session.delete(existing)
        session.flush()
    else:
        session.add(Like(user_id=user.id, task_id=task_id, comment_id=None))
        session.flush()
    likes = likes_for_task(session, task_id)
    liked = any(item.user_id == user.id for item in likes)
    return liked, likes


def toggle_comment_like(
    session: Session, *, user: User, comment: TaskComment
) -> tuple[bool, list[Like]]:
    existing = session.scalar(
        select(Like).where(Like.user_id == user.id, Like.comment_id == comment.id)
    )
    if existing is not None:
        session.delete(existing)
        session.flush()
    else:
        session.add(Like(user_id=user.id, task_id=None, comment_id=comment.id))
        session.flush()
    likes = likes_for_comment(session, comment.id)
    liked = any(item.user_id == user.id for item in likes)
    return liked, likes
