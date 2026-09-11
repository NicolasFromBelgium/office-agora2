"""Project agenda and calendar events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from agora.models import utcnow
from agora.services.agenda import month_view
from agora.services.dates import date_input, local_now, parse_event_span, time_input
from agora.services.events import create_event, delete_event, get_event, update_event
from agora.web.deps import NotFound, get_db, require_project, shell_context
from agora.web.templating import render, set_flash

router = APIRouter(tags=["agenda"])


def _as_bool(raw: str) -> bool:
    return (raw or "").strip().lower() in {"1", "on", "true", "yes"}


def _safe_next(project_id: int, next_url: str) -> str:
    prefix = f"/projects/{project_id}"
    path = next_url or ""
    idx = path.find(prefix)
    if idx >= 0:
        return path[idx:]
    return f"{prefix}/agenda"


@router.get("/projects/{project_id}/agenda")
def project_agenda(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    year: int | None = None,
    month: int | None = None,
):
    project, membership, user = loaded
    today = local_now()
    year = year or today.year
    month = month or today.month
    if month < 1 or month > 12 or year < 2000 or year > 2100:
        year, month = today.year, today.month
    created_event_id = None
    raw = request.query_params.get("created")
    if raw and raw.isdigit():
        created_event_id = int(raw)
    return render(
        request,
        "projects/agenda.html",
        project=project,
        membership=membership,
        agenda=month_view(db, project.id, year, month),
        created_event_id=created_event_id,
        active_tab="agenda",
        **shell_context(request, db, user),
    )


@router.post("/projects/{project_id}/events")
def create_event_route(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    title: str = Form(...),
    description: str = Form(""),
    start_date: str = Form(""),
    start_time: str = Form(""),
    end_date: str = Form(""),
    end_time: str = Form(""),
    all_day: str = Form(""),
):
    project, _membership, user = loaded
    title = title.strip()
    if not title:
        set_flash(request, "Un événement a besoin d’un titre.", "error")
        return RedirectResponse(f"/projects/{project.id}/agenda", status_code=303)
    span = parse_event_span(
        start_date=start_date,
        start_time=start_time,
        end_date=end_date,
        end_time=end_time,
        all_day=_as_bool(all_day),
    )
    if span is None:
        set_flash(request, "Indiquez une date de début.", "error")
        return RedirectResponse(f"/projects/{project.id}/agenda", status_code=303)
    starts_at, ends_at = span
    event = create_event(
        db,
        project_id=project.id,
        actor=user,
        title=title,
        description=description,
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=_as_bool(all_day),
    )
    db.commit()
    return RedirectResponse(
        f"/projects/{project.id}/agenda?created={event.id}",
        status_code=303,
    )


@router.get("/projects/{project_id}/events/{event_id}")
def event_detail(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    event = get_event(db, project.id, event_id)
    if event is None:
        raise NotFound("Événement introuvable.")
    return render(
        request,
        "events/detail.html",
        project=project,
        membership=membership,
        event=event,
        start_date=date_input(event.starts_at),
        start_time=time_input(event.starts_at),
        end_date=date_input(event.ends_at),
        end_time=time_input(event.ends_at),
        active_tab="agenda",
        **shell_context(request, db, user),
    )


@router.post("/projects/{project_id}/events/{event_id}")
def update_event_route(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    title: str = Form(...),
    description: str = Form(""),
    start_date: str = Form(""),
    start_time: str = Form(""),
    end_date: str = Form(""),
    end_time: str = Form(""),
    all_day: str = Form(""),
):
    project, _membership, user = loaded
    event = get_event(db, project.id, event_id)
    if event is None:
        raise NotFound("Événement introuvable.")
    title = title.strip()
    if not title:
        set_flash(request, "Un événement a besoin d’un titre.", "error")
        return RedirectResponse(f"/projects/{project.id}/events/{event.id}", status_code=303)
    span = parse_event_span(
        start_date=start_date,
        start_time=start_time,
        end_date=end_date,
        end_time=end_time,
        all_day=_as_bool(all_day),
    )
    if span is None:
        set_flash(request, "Indiquez une date de début.", "error")
        return RedirectResponse(f"/projects/{project.id}/events/{event.id}", status_code=303)
    starts_at, ends_at = span
    update_event(
        db,
        event=event,
        actor=user,
        title=title,
        description=description,
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=_as_bool(all_day),
    )
    event.updated_at = utcnow()
    db.commit()
    set_flash(request, "Événement enregistré.", "info")
    return RedirectResponse(f"/projects/{project.id}/events/{event.id}", status_code=303)


@router.post("/projects/{project_id}/events/{event_id}/delete")
def delete_event_route(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    next: str = Form(""),
):
    project, _membership, user = loaded
    event = get_event(db, project.id, event_id)
    if event is None:
        raise NotFound("Événement introuvable.")
    title = event.title
    delete_event(db, event=event, actor=user)
    db.commit()
    set_flash(request, f"« {title} » a été supprimé.", "info")
    return RedirectResponse(_safe_next(project.id, next), status_code=303)
