"""Task create, status changes, and assignment."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from agora.constants import TASK_STATUSES, Action, TaskStatus
from agora.models import Like, Notification, ProjectMember, Task, User, utcnow
from agora.services.activity import log_activity
from agora.services.files import remove_attachment
from agora.services.notifications import notify_assignment
from agora.settings import Settings

BRUSSELS = ZoneInfo("Europe/Brussels")


def next_position(session: Session, project_id: int, status: str) -> int:
    current = session.scalar(
        select(func.max(Task.position)).where(Task.project_id == project_id, Task.status == status)
    )
    return (current or 0) + 1


def board_tasks(session: Session, project_id: int) -> dict[str, list[Task]]:
    rows = list(
        session.scalars(
            select(Task)
            .where(Task.project_id == project_id)
            .options(
                selectinload(Task.assignee),
                selectinload(Task.files),
                selectinload(Task.comments),
                selectinload(Task.likes).selectinload(Like.user),
            )
            .order_by(Task.position, Task.id)
        )
    )
    grouped: dict[str, list[Task]] = {status.value: [] for status in TASK_STATUSES}
    for task in rows:
        grouped.setdefault(task.status, []).append(task)
    return grouped


def create_task(
    session: Session,
    *,
    project_id: int,
    actor: User,
    title: str,
    description: str = "",
    status: str = TaskStatus.TODO.value,
    assignee_id: int | None = None,
    due_at: datetime | None = None,
) -> Task:
    if status not in {s.value for s in TASK_STATUSES}:
        status = TaskStatus.TODO.value
    task = Task(
        project_id=project_id,
        title=title.strip(),
        description=description.strip(),
        status=status,
        assignee_id=assignee_id or None,
        position=next_position(session, project_id, status),
        created_by_id=actor.id,
        due_at=due_at,
    )
    session.add(task)
    session.flush()
    log_activity(
        session,
        project_id=project_id,
        actor=actor,
        action=Action.TASK_CREATED,
        task_id=task.id,
        details={"title": task.title, "status": task.status},
    )
    if task.assignee_id:
        assignee = session.get(User, task.assignee_id)
        if assignee is not None:
            notify_assignment(session, recipient=assignee, actor=actor, task=task)
    return task


def change_status(session: Session, *, task: Task, actor: User, new_status: str) -> Task:
    if new_status not in {s.value for s in TASK_STATUSES}:
        raise ValueError(f"Unknown status: {new_status}")
    old = task.status
    if old == new_status:
        return task
    task.status = new_status
    task.position = next_position(session, task.project_id, new_status)
    task.updated_at = utcnow()
    log_activity(
        session,
        project_id=task.project_id,
        actor=actor,
        action=Action.TASK_STATUS_CHANGED,
        task_id=task.id,
        details={"title": task.title, "from": old, "to": new_status},
    )
    session.flush()
    return task


def assign_task(
    session: Session,
    *,
    task: Task,
    actor: User,
    assignee: User | None,
) -> Task:
    task.assignee_id = assignee.id if assignee else None
    task.updated_at = utcnow()
    log_activity(
        session,
        project_id=task.project_id,
        actor=actor,
        action=Action.TASK_ASSIGNED,
        task_id=task.id,
        details={
            "title": task.title,
            "assignee": assignee.display_name if assignee else "non assigné",
        },
    )
    session.flush()
    if assignee is not None:
        notify_assignment(session, recipient=assignee, actor=actor, task=task)
    return task


def delete_task(session: Session, *, task: Task, actor: User, settings: Settings) -> None:
    title = task.title
    project_id = task.project_id
    for attachment in list(task.files):
        remove_attachment(
            session,
            attachment=attachment,
            actor=actor,
            settings=settings,
            write_activity=False,
        )
    for item in list(
        session.scalars(select(Notification).where(Notification.task_id == task.id))
    ):
        session.delete(item)
    session.delete(task)
    log_activity(
        session,
        project_id=project_id,
        actor=actor,
        action=Action.TASK_DELETED,
        details={"title": title},
    )
    session.flush()


def tasks_due_on(session: Session, user_id: int, day: datetime) -> list[Task]:
    """Tasks the user can see that are due on the given local calendar day."""
    if day.tzinfo is None:
        local_day = day.replace(tzinfo=BRUSSELS)
    else:
        local_day = day.astimezone(BRUSSELS)
    target = local_day.date()
    rows = list(
        session.scalars(
            select(Task)
            .join(ProjectMember, ProjectMember.project_id == Task.project_id)
            .where(ProjectMember.user_id == user_id, Task.due_at.is_not(None))
            .options(selectinload(Task.project), selectinload(Task.assignee))
            .order_by(Task.due_at, Task.id)
        )
    )
    due_today = []
    for task in rows:
        due = task.due_at
        if due is None:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=BRUSSELS)
        else:
            due = due.astimezone(BRUSSELS)
        if due.date() == target:
            due_today.append(task)
    return due_today
