"""Month agenda: tasks with due dates plus calendar events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.constants import TaskStatus
from agora.models import CalendarEvent, ProjectMember, Task
from agora.services.dates import (
    WEEKDAYS_SHORT,
    as_brussels,
    is_date_only,
    local_now,
    month_grid_start,
    month_label,
    shift_month,
    start_of_day,
    time_label,
)
from agora.services.events import events_between
from agora.services.tasks import tasks_due_on


@dataclass
class AgendaChip:
    kind: str
    id: int
    title: str
    href: str
    time_label: str
    overdue: bool = False
    all_day: bool = False


@dataclass
class AgendaDay:
    day: date
    in_month: bool
    is_today: bool
    items: list[AgendaChip] = field(default_factory=list)


@dataclass
class AgendaMonth:
    year: int
    month: int
    label: str
    weekdays: tuple[str, ...]
    weeks: list[list[AgendaDay]]
    prev_year: int
    prev_month: int
    next_year: int
    next_month: int


@dataclass
class DayItem:
    kind: str
    id: int
    project_id: int
    title: str
    description: str
    when: datetime
    href: str


def _task_overdue(task: Task, now: datetime) -> bool:
    if task.due_at is None or task.status == TaskStatus.DONE.value:
        return False
    return as_brussels(task.due_at) < now


def _task_chip(task: Task, now: datetime) -> AgendaChip:
    due = as_brussels(task.due_at) if task.due_at is not None else now
    return AgendaChip(
        kind="task",
        id=task.id,
        title=task.title,
        href=f"/projects/{task.project_id}/tasks/{task.id}",
        time_label=time_label(due),
        overdue=_task_overdue(task, now),
        all_day=is_date_only(due),
    )


def _event_chip(event: CalendarEvent) -> AgendaChip:
    start = as_brussels(event.starts_at)
    return AgendaChip(
        kind="event",
        id=event.id,
        title=event.title,
        href=f"/projects/{event.project_id}/events/{event.id}",
        time_label="" if event.all_day else time_label(start),
        all_day=event.all_day,
    )


def month_view(session: Session, project_id: int, year: int, month: int) -> AgendaMonth:
    today = local_now().date()
    grid_start = month_grid_start(year, month)
    grid_end = grid_start + timedelta(days=42)
    range_start = start_of_day(grid_start)
    range_end = start_of_day(grid_end)
    now = local_now()

    tasks = list(
        session.scalars(
            select(Task)
            .where(
                Task.project_id == project_id,
                Task.due_at.is_not(None),
                Task.due_at >= range_start,
                Task.due_at < range_end,
            )
            .order_by(Task.due_at, Task.id)
        )
    )
    events = events_between(session, project_id, range_start, range_end)

    by_day: dict[date, list[AgendaChip]] = {}
    for task in tasks:
        if task.due_at is None:
            continue
        by_day.setdefault(as_brussels(task.due_at).date(), []).append(_task_chip(task, now))
    for event in events:
        start_day = as_brussels(event.starts_at).date()
        end_day = as_brussels(event.ends_at).date()
        cursor = start_day
        while cursor <= end_day:
            chip = _event_chip(event)
            if cursor != start_day:
                chip.time_label = ""
            by_day.setdefault(cursor, []).append(chip)
            cursor += timedelta(days=1)

    weeks: list[list[AgendaDay]] = []
    cursor = grid_start
    for _ in range(6):
        week: list[AgendaDay] = []
        for _ in range(7):
            week.append(
                AgendaDay(
                    day=cursor,
                    in_month=cursor.month == month,
                    is_today=cursor == today,
                    items=by_day.get(cursor, []),
                )
            )
            cursor += timedelta(days=1)
        weeks.append(week)

    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)
    return AgendaMonth(
        year=year,
        month=month,
        label=month_label(year, month),
        weekdays=WEEKDAYS_SHORT,
        weeks=weeks,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
    )


def items_for_user_on(session: Session, user_id: int, day: datetime) -> list[DayItem]:
    local_day = as_brussels(day).date()
    tasks = tasks_due_on(session, user_id, day)
    events = list(
        session.scalars(
            select(CalendarEvent)
            .join(ProjectMember, ProjectMember.project_id == CalendarEvent.project_id)
            .where(ProjectMember.user_id == user_id)
            .options(selectinload(CalendarEvent.project))
            .order_by(CalendarEvent.starts_at, CalendarEvent.id)
        )
    )
    items: list[DayItem] = []
    for task in tasks:
        if task.due_at is None:
            continue
        items.append(
            DayItem(
                kind="task",
                id=task.id,
                project_id=task.project_id,
                title=task.title,
                description=task.description,
                when=as_brussels(task.due_at),
                href=f"/projects/{task.project_id}/tasks/{task.id}",
            )
        )
    for event in events:
        start = as_brussels(event.starts_at).date()
        end = as_brussels(event.ends_at).date()
        if start <= local_day <= end:
            items.append(
                DayItem(
                    kind="event",
                    id=event.id,
                    project_id=event.project_id,
                    title=event.title,
                    description=event.description,
                    when=as_brussels(event.starts_at),
                    href=f"/projects/{event.project_id}/events/{event.id}",
                )
            )
    items.sort(key=lambda item: (item.when, item.kind, item.id))
    return items
