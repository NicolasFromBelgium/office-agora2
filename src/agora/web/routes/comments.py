"""Task comments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from agora.models import TaskComment
from agora.services.comments import CommentRejected, add_comment, comments_for_task, delete_comment
from agora.web.deps import NotFound, get_db, require_project
from agora.web.routes.tasks import _task_or_404
from agora.web.templating import render, set_flash

router = APIRouter(tags=["comments"])


@router.post("/projects/{project_id}/tasks/{task_id}/comments")
def post_comment(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    body: str = Form(""),
):
    project, _membership, user = loaded
    task = _task_or_404(db, project.id, task_id)
    try:
        add_comment(db, task=task, author=user, body=body)
        db.commit()
    except CommentRejected as exc:
        db.rollback()
        set_flash(request, exc.message, "error")
    next_url = f"/projects/{project.id}/tasks/{task.id}"
    if request.headers.get("HX-Request"):
        return render(
            request,
            "partials/task_comments.html",
            project=project,
            task=task,
            comments=comments_for_task(db, task.id),
            current_user=user,
        )
    return RedirectResponse(next_url, status_code=303)


@router.post("/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/delete")
def delete_comment_route(
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
    delete_comment(db, task=task, comment=comment, actor=user)
    db.commit()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "partials/task_comments.html",
            project=project,
            task=task,
            comments=comments_for_task(db, task.id),
            current_user=user,
        )
    set_flash(request, "Commentaire supprimé.", "info")
    return RedirectResponse(f"/projects/{project.id}/tasks/{task.id}", status_code=303)
