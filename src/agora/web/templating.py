"""Jinja2 templates and a small render helper."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.templating import Jinja2Templates

from agora.constants import STATUS_LABELS, TASK_STATUSES, status_label
from agora.services.activity import describe_activity
from agora.services.dates import date_input, local_now, time_input
from agora.services.files import extension_of, file_kind
from agora.web.urls import href as prefixed_href

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
BRUSSELS = ZoneInfo("Europe/Brussels")
MONTHS_FR = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.globals["describe_activity"] = describe_activity
templates.env.globals["STATUS_LABELS"] = STATUS_LABELS
templates.env.globals["TASK_STATUSES"] = TASK_STATUSES
templates.env.globals["status_label"] = status_label
templates.env.globals["file_kind"] = file_kind
templates.env.globals["file_ext"] = extension_of
templates.env.autoescape = True


def _local(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(BRUSSELS)


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    local = _local(value)
    return f"{local.day} {MONTHS_FR[local.month - 1]} {local.year} {local.hour}h{local.minute:02d}"


def format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    local = _local(value)
    return f"{local.hour}h{local.minute:02d}"


def format_due(value: datetime | None) -> str:
    if value is None:
        return ""
    local = _local(value)
    day = f"{local.day} {MONTHS_FR[local.month - 1]}"
    if local.hour == 0 and local.minute == 0:
        return day
    return f"{day} {local.hour}h{local.minute:02d}"


def is_overdue(value: datetime | None, status: str = "") -> bool:
    if value is None or status == "done":
        return False
    return _local(value) < datetime.now(BRUSSELS)


templates.env.filters["dt"] = format_datetime
templates.env.filters["hm"] = format_time
templates.env.filters["due"] = format_due
templates.env.filters["overdue"] = is_overdue
templates.env.filters["date_input"] = date_input
templates.env.filters["time_input"] = time_input

FLASH_KEY = "_flash"


def set_flash(request: Request, message: str, category: str = "info") -> None:
    request.session[FLASH_KEY] = {"message": message, "category": category}


def pop_flash(request: Request) -> dict[str, str] | None:
    return request.session.pop(FLASH_KEY, None)


def render(request: Request, template_name: str, status_code: int = 200, **context: Any):
    settings = request.app.state.settings

    def u(path: str) -> str:
        return prefixed_href(settings.root_path, path)

    payload = {
        "request": request,
        "flash": pop_flash(request),
        "current_user": context.get("current_user"),
        "online_users": context.get("online_users") or [],
        "projects": context.get("projects") or [],
        "settings": settings,
        "u": u,
        "today_iso": local_now().date().isoformat(),
        "now": local_now(),
        **context,
    }
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=payload,
        status_code=status_code,
    )
