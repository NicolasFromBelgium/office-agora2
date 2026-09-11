"""Calendar events, stored per project."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.constants import Action
from agora.models import CalendarEvent, User, utcnow
from agora.services.activity import log_activity
from agora.services.dates import as_brussels


def get_event(session: Session, project_id: int, event_id: int) -> CalendarEvent | None:
    event = session.scalar(
        select(CalendarEvent)
        .where(CalendarEvent.id == event_id, CalendarEvent.project_id == project_id)
        .options(selectinload(CalendarEvent.created_by))
    )
    return event


def events_between(
    session: Session,
    project_id: int,
    start: datetime,
    end: datetime,
) -> list[CalendarEvent]:
    return list(
        session.scalars(
            select(CalendarEvent)
            .where(
                CalendarEvent.project_id == project_id,
                CalendarEvent.starts_at < end,
                CalendarEvent.ends_at >= start,
            )
            .options(selectinload(CalendarEvent.created_by))
            .order_by(CalendarEvent.starts_at, CalendarEvent.id)
        )
    )


def create_event(
    session: Session,
    *,
    project_id: int,
    actor: User,
    title: str,
    description: str = "",
    starts_at: datetime,
    ends_at: datetime,
    all_day: bool = False,
) -> CalendarEvent:
    title = title.strip()
    starts_at = as_brussels(starts_at)
    ends_at = as_brussels(ends_at)
    if ends_at < starts_at:
        ends_at = starts_at
    event = CalendarEvent(
        project_id=project_id,
        title=title,
        description=description.strip(),
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
        created_by_id=actor.id,
    )
    session.add(event)
    session.flush()
    log_activity(
        session,
        project_id=project_id,
        actor=actor,
        action=Action.EVENT_CREATED,
        details={"title": event.title},
    )
    return event


def update_event(
    session: Session,
    *,
    event: CalendarEvent,
    actor: User,
    title: str,
    description: str,
    starts_at: datetime,
    ends_at: datetime,
    all_day: bool,
) -> CalendarEvent:
    title = title.strip()
    starts_at = as_brussels(starts_at)
    ends_at = as_brussels(ends_at)
    if ends_at < starts_at:
        ends_at = starts_at
    event.title = title
    event.description = description.strip()
    event.starts_at = starts_at
    event.ends_at = ends_at
    event.all_day = all_day
    event.updated_at = utcnow()
    log_activity(
        session,
        project_id=event.project_id,
        actor=actor,
        action=Action.EVENT_UPDATED,
        details={"title": event.title},
    )
    session.flush()
    return event


def delete_event(session: Session, *, event: CalendarEvent, actor: User) -> None:
    title = event.title
    project_id = event.project_id
    session.delete(event)
    log_activity(
        session,
        project_id=project_id,
        actor=actor,
        action=Action.EVENT_DELETED,
        details={"title": title},
    )
    session.flush()
