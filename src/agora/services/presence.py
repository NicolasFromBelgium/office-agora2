"""Heartbeat presence: who has been seen recently."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from agora.models import User, utcnow


def touch(session: Session, user: User) -> None:
    user.last_seen_at = utcnow()


def is_online(user: User, timeout_seconds: int, now: datetime | None = None) -> bool:
    if user.last_seen_at is None:
        return False
    current = now or utcnow()
    seen = user.last_seen_at
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    return current - seen <= timedelta(seconds=timeout_seconds)


def online_users(session: Session, timeout_seconds: int) -> list[User]:
    cutoff = utcnow() - timedelta(seconds=timeout_seconds)
    return list(
        session.scalars(
            select(User)
            .where(
                User.is_active.is_(True),
                User.is_bot.is_(False),
                User.last_seen_at.is_not(None),
                User.last_seen_at >= cutoff,
            )
            .order_by(User.display_name)
        )
    )
