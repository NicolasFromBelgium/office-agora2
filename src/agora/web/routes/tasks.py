"""Task create, status, assignment, and detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.constants import TASK_STATUSES
from agora.models import ActivityLog, Like, Task, TaskComment, User, utcnow
from agora.services.comments import comments_for_task
from agora.services.dates import parse_due
from agora.services.notifications import mark_task_read
from agora.services.tasks import assign_task, board_tasks, change_status, create_task, delete_task
from agora.web.deps import NotFound, get_db, require_project, shell_context
from agora.web.templating import render, set_flash

router = APIRouter(tags=["tasks"])


def _safe_next(project_id: int, next_url: str) -> str:
    prefix = f"/projects/{project_id}"
    path = next_url or ""
    idx = path.find(prefix)
    if idx >= 0:
        return path[idx:]
    return f"{prefix}/board"


def _task_or_404(db: Session, project_id: int, task_id: int) -> Task:
    task = db.scalar(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.assignee),
            selectinload(Task.files),
            selectinload(Task.created_by),
            selectinload(Task.likes).selectinload(Like.user),
            selectinload(Task.comments).selectinload(TaskComment.author),
            selectinload(Task.comments).selectinload(TaskComment.likes).selectinload(Like.user),
        )
    )
    if task is None or task.project_id != project_id:
        raise NotFound("Tâche introuvable.")
    return task


def _parse_assignee(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@router.post("/projects/{project_id}/tasks")
def create_task_route(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    title: str = Form(...),
    description: str = Form(""),
    status: str = Form("todo"),
    assignee_id: str = Form(""),
    due_date: str = Form(""),
    due_time: str = Form(""),
    next: str = Form(""),
):
    project, _membership, user = loaded
    title = title.strip()
    if not title:
        set_flash(request, "Une tâche a besoin d’un titre.", "error")
        return RedirectResponse(f"/projects/{project.id}/board", status_code=303)
    assignee = None
    parsed = _parse_assignee(assignee_id)
    if parsed is not None:
        assignee = db.get(User, parsed)
        if assignee is None or all(m.user_id != parsed for m in project.members):
            assignee = None
    task = create_task(
        db,
        project_id=project.id,
        actor=user,
        title=title,
        description=description,
        status=status,
        assignee_id=assignee.id if assignee else None,
        due_at=parse_due(due_date, due_time),
    )
    db.commit()
    return RedirectResponse(
        f"/projects/{project.id}/board?created={task.id}",
        status_code=303,
    )


@router.post("/projects/{project_id}/tasks/{task_id}/status")
def update_status(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    status: str = Form(...),
    next: str = Form(""),
):
    project, membership, user = loaded
    task = _task_or_404(db, project.id, task_id)
    if status not in {s.value for s in TASK_STATUSES}:
        set_flash(request, "Statut inconnu.", "error")
        return RedirectResponse(_safe_next(project.id, next), status_code=303)
    change_status(db, task=task, actor=user, new_status=status)
    db.commit()
    next_url = _safe_next(project.id, next)
    if request.headers.get("HX-Request") and next_url.endswith("/board"):
        columns = board_tasks(db, project.id)
        return render(
            request,
            "projects/_board.html",
            project=project,
            membership=membership,
            columns=columns,
            **shell_context(request, db, user),
        )
    if request.headers.get("HX-Request"):
        return RedirectResponse(next_url, status_code=303, headers={"HX-Redirect": next_url})
    return RedirectResponse(next_url, status_code=303)


@router.get("/projects/{project_id}/tasks/{task_id}")
def task_detail(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    task = _task_or_404(db, project.id, task_id)
    mark_task_read(db, user.id, task.id)
    db.commit()
    logs = list(
        db.scalars(
            select(ActivityLog)
            .where(ActivityLog.task_id == task.id)
            .options(selectinload(ActivityLog.actor))
            .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        )
    )
    return render(
        request,
        "tasks/detail.html",
        project=project,
        membership=membership,
        task=task,
        comments=comments_for_task(db, task.id),
        logs=logs,
        active_tab="board",
        **shell_context(request, db, user),
    )


@router.post("/projects/{project_id}/tasks/{task_id}")
def update_task(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    title: str = Form(...),
    description: str = Form(""),
    status: str = Form(...),
    assignee_id: str = Form(""),
    due_date: str = Form(""),
    due_time: str = Form(""),
):
    project, _membership, user = loaded
    task = _task_or_404(db, project.id, task_id)
    title = title.strip()
    if not title:
        set_flash(request, "Une tâche a besoin d’un titre.", "error")
        return RedirectResponse(f"/projects/{project.id}/tasks/{task.id}", status_code=303)
    task.title = title
    task.description = description.strip()
    task.due_at = parse_due(due_date, due_time)
    task.updated_at = utcnow()
    if status != task.status and status in {s.value for s in TASK_STATUSES}:
        change_status(db, task=task, actor=user, new_status=status)
    parsed = _parse_assignee(assignee_id)
    new_assignee = db.get(User, parsed) if parsed is not None else None
    member_ids = {m.user_id for m in project.members}
    if parsed is not None and (new_assignee is None or parsed not in member_ids):
        new_assignee = task.assignee
    if (new_assignee.id if new_assignee else None) != task.assignee_id:
        assign_task(db, task=task, actor=user, assignee=new_assignee)
    db.commit()
    set_flash(request, "Tâche enregistrée.", "info")
    return RedirectResponse(f"/projects/{project.id}/tasks/{task.id}", status_code=303)


@router.post("/projects/{project_id}/tasks/{task_id}/delete")
def delete_task_route(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    next: str = Form(""),
):
    project, _membership, user = loaded
    task = _task_or_404(db, project.id, task_id)
    title = task.title
    delete_task(db, task=task, actor=user, settings=request.app.state.settings)
    db.commit()
    set_flash(request, f"« {title} » a été supprimée.", "info")
    return RedirectResponse(_safe_next(project.id, next), status_code=303)
