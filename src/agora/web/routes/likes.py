"""Toggle likes on a task or a comment."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from agora.models import TaskComment
from agora.services.likes import button_context, toggle_comment_like, toggle_task_like
from agora.web.deps import NotFound, get_db, require_project
from agora.web.routes.tasks import _task_or_404
from agora.web.templating import render

router = APIRouter(tags=["likes"])


def _like_partial(request: Request, *, action: str, likes, user_id: int):
    return render(
        request,
        "partials/like_button.html",
        action=action,
        **button_context(likes, user_id),
    )


@router.post("/projects/{project_id}/tasks/{task_id}/like")
def like_task(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, _membership, user = loaded
    task = _task_or_404(db, project.id, task_id)
    _liked, likes = toggle_task_like(db, user=user, task_id=task.id)
    db.commit()
    action = f"/projects/{project.id}/tasks/{task.id}/like"
    if request.headers.get("HX-Request"):
        return _like_partial(request, action=action, likes=likes, user_id=user.id)
    return RedirectResponse(f"/projects/{project.id}/tasks/{task.id}", status_code=303)


@router.post("/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/like")
def like_comment(
    request: Request,
    task_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, _membership, user = loaded
    task = _task_or_404(db, project.id, task_id)
    comment = db.get(TaskComment, comment_id)
    if comment is None or comment.task_id != task.id:
        raise NotFound("Commentaire introuvable.")
    _liked, likes = toggle_comment_like(db, user=user, comment=comment)
    db.commit()
    action = f"/projects/{project.id}/tasks/{task.id}/comments/{comment.id}/like"
    if request.headers.get("HX-Request"):
        return _like_partial(request, action=action, likes=likes, user_id=user.id)
    return RedirectResponse(f"/projects/{project.id}/tasks/{task.id}", status_code=303)
