"""Comments on tasks."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.constants import Action
from agora.models import Like, Task, TaskComment, User, utcnow
from agora.services.activity import log_activity

MAX_COMMENT_CHARS = 4000


class CommentRejected(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def add_comment(session: Session, *, task: Task, author: User, body: str) -> TaskComment:
    text = (body or "").strip()
    if not text:
        raise CommentRejected("Écrivez d’abord un commentaire.")
    comment = TaskComment(
        task_id=task.id,
        author_id=author.id,
        body=text[:MAX_COMMENT_CHARS],
    )
    session.add(comment)
    task.updated_at = utcnow()
    session.flush()
    log_activity(
        session,
        project_id=task.project_id,
        actor=author,
        action=Action.TASK_COMMENTED,
        task_id=task.id,
        details={"title": task.title, "body": comment.body[:120]},
    )
    return comment


def delete_comment(session: Session, *, task: Task, comment: TaskComment, actor: User) -> None:
    session.delete(comment)
    task.updated_at = utcnow()
    log_activity(
        session,
        project_id=task.project_id,
        actor=actor,
        action=Action.COMMENT_DELETED,
        task_id=task.id,
        details={"title": task.title},
    )
    session.flush()


def comments_for_task(session: Session, task_id: int) -> list[TaskComment]:
    return list(
        session.scalars(
            select(TaskComment)
            .where(TaskComment.task_id == task_id)
            .options(
                selectinload(TaskComment.author),
                selectinload(TaskComment.likes).selectinload(Like.user),
            )
            .order_by(TaskComment.created_at.asc(), TaskComment.id.asc())
        )
    )
