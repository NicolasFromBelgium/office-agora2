"""In-app notifications: assignments and the header bell."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from agora.constants import Action, TaskStatus
from agora.models import Notification, ProjectMember, Task, User, utcnow

BELL_LIMIT = 20
ASSIGNED_LIMIT = 12


def notify_assignment(
    session: Session,
    *,
    recipient: User,
    actor: User,
    task: Task,
) -> Notification | None:
    if recipient.id == actor.id or recipient.is_bot:
        return None
    item = Notification(
        user_id=recipient.id,
        actor_id=actor.id,
        project_id=task.project_id,
        task_id=task.id,
        kind=Action.TASK_ASSIGNED,
        title=task.title,
    )
    session.add(item)
    session.flush()
    return item


def unread_count(session: Session, user_id: int) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        or 0
    )


def recent_notifications(session: Session, user_id: int) -> list[Notification]:
    return list(
        session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .options(
                selectinload(Notification.actor),
                selectinload(Notification.project),
                selectinload(Notification.task),
            )
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(BELL_LIMIT)
        )
    )


def assigned_open_tasks(session: Session, user_id: int) -> list[Task]:
    return list(
        session.scalars(
            select(Task)
            .join(ProjectMember, ProjectMember.project_id == Task.project_id)
            .where(
                ProjectMember.user_id == user_id,
                Task.assignee_id == user_id,
                Task.status != TaskStatus.DONE.value,
            )
            .options(selectinload(Task.project))
            .order_by(Task.updated_at.desc(), Task.id.desc())
            .limit(ASSIGNED_LIMIT)
        )
    )


def bell_context(session: Session, user_id: int) -> dict:
    return {
        "unread_count": unread_count(session, user_id),
        "notifications": recent_notifications(session, user_id),
        "assigned_tasks": assigned_open_tasks(session, user_id),
    }


def mark_all_read(session: Session, user_id: int) -> None:
    now = utcnow()
    rows = list(
        session.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
    )
    for item in rows:
        item.read_at = now


def mark_task_read(session: Session, user_id: int, task_id: int) -> None:
    now = utcnow()
    rows = list(
        session.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.task_id == task_id,
                Notification.read_at.is_(None),
            )
        )
    )
    for item in rows:
        item.read_at = now
