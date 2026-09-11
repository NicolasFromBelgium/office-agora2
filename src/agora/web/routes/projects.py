"""Projects: create, board, list, activity, invite."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.models import ActivityLog, User
from agora.services.momentum import member_scores, nudge
from agora.services.projects import add_member, create_project
from agora.services.tasks import board_tasks
from agora.web.deps import get_db, require_project, require_user, shell_context
from agora.web.templating import render, set_flash

router = APIRouter(tags=["projects"])


@router.get("/projects/new")
def new_project_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    return render(request, "projects/new.html", **shell_context(request, db, user))


@router.post("/projects")
def create_project_route(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    name: str = Form(...),
    description: str = Form(""),
):
    name = name.strip()
    if not name:
        set_flash(request, "Donnez un nom au projet.", "error")
        return render(
            request,
            "projects/new.html",
            status_code=422,
            description=description,
            **shell_context(request, db, user),
        )
    project = create_project(db, owner=user, name=name, description=description)
    db.commit()
    return RedirectResponse(f"/projects/{project.id}/board", status_code=303)


@router.get("/projects/{project_id}")
def project_home(project_id: int, loaded=Depends(require_project)):
    project, _membership, _user = loaded
    return RedirectResponse(f"/projects/{project.id}/board", status_code=303)


@router.get("/projects/{project_id}/board")
def project_board(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    columns = board_tasks(db, project.id)
    created_id = None
    raw_created = request.query_params.get("created")
    if raw_created and raw_created.isdigit():
        created_id = int(raw_created)
    crew = member_scores(
        db,
        project_id=project.id,
        timeout_seconds=request.app.state.settings.presence_timeout_seconds,
    )
    return render(
        request,
        "projects/board.html",
        project=project,
        membership=membership,
        columns=columns,
        created_id=created_id,
        crew=crew,
        elan_nudge=nudge(crew, user),
        active_tab="board",
        **shell_context(request, db, user),
    )


@router.get("/projects/{project_id}/list")
def project_list(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    columns = board_tasks(db, project.id)
    tasks = [task for status_tasks in columns.values() for task in status_tasks]
    return render(
        request,
        "projects/list.html",
        project=project,
        membership=membership,
        tasks=tasks,
        active_tab="list",
        **shell_context(request, db, user),
    )


@router.get("/projects/{project_id}/activity")
def project_activity(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    logs = list(
        db.scalars(
            select(ActivityLog)
            .where(ActivityLog.project_id == project.id)
            .options(selectinload(ActivityLog.actor), selectinload(ActivityLog.task))
            .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
            .limit(200)
        )
    )
    return render(
        request,
        "projects/activity.html",
        project=project,
        membership=membership,
        logs=logs,
        active_tab="activity",
        **shell_context(request, db, user),
    )


@router.post("/projects/{project_id}/members")
def invite_member(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    email: str = Form(...),
    display_name: str = Form(""),
):
    project, membership, user = loaded
    if not membership.is_owner:
        set_flash(request, "Seul le propriétaire du projet peut inviter.", "error")
        return RedirectResponse(f"/projects/{project.id}/board", status_code=303)
    if not email.strip():
        set_flash(request, "L’e-mail est obligatoire.", "error")
        return RedirectResponse(f"/projects/{project.id}/board", status_code=303)
    invited, created = add_member(
        db,
        project=project,
        actor=user,
        email=email,
        display_name=display_name,
        settings=request.app.state.settings,
    )
    db.commit()
    if created:
        set_flash(
            request,
            f"{invited.display_name} peut se connecter avec le mot de passe d’invitation.",
            "info",
        )
    else:
        set_flash(request, f"{invited.display_name} fait partie de ce projet.", "info")
    referer = request.headers.get("referer") or f"/projects/{project.id}/board"
    # Stay on the project, not an external referer.
    target = f"/projects/{project.id}/board"
    if referer and f"/projects/{project.id}" in referer:
        target = referer
    return RedirectResponse(target, status_code=303)
