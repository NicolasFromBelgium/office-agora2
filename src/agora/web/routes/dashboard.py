"""Authenticated home: user, presence, continue last project, project list."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from agora.models import Project, User
from agora.services.agenda import items_for_user_on
from agora.services.momentum import member_scores, nudge
from agora.web.deps import get_db, last_board_path, require_user, shell_context
from agora.web.templating import render
from agora.web.urls import redirect

router = APIRouter(tags=["dashboard"])
BRUSSELS = ZoneInfo("Europe/Brussels")


@router.get("/")
def home(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    board = last_board_path(db, user)
    if board:
        return redirect(request, board)
    return dashboard(request, db, user)


@router.get("/home")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    ctx = shell_context(request, db, user)
    last_project = None
    if user.last_project_id:
        last_project = next((p for p in ctx["projects"] if p.id == user.last_project_id), None)
        if last_project is None:
            last_project = db.get(Project, user.last_project_id)
            if last_project is None or all(p.id != last_project.id for p in ctx["projects"]):
                last_project = None
    today = items_for_user_on(db, user.id, datetime.now(BRUSSELS))
    crew = []
    elan_nudge = ""
    if last_project is not None:
        crew = member_scores(
            db,
            project_id=last_project.id,
            timeout_seconds=request.app.state.settings.presence_timeout_seconds,
        )
        elan_nudge = nudge(crew, user)
    return render(
        request,
        "dashboard.html",
        last_project=last_project,
        today_items=today,
        crew=crew,
        elan_nudge=elan_nudge,
        **ctx,
    )
