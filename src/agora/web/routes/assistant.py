"""Ask Grok: posts a teammate reply in the project chat."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from agora.services.assistant import respond
from agora.web.deps import get_db, require_project
from agora.web.routes.chat import _messages
from agora.web.templating import render, set_flash

router = APIRouter(tags=["assistant"])


@router.post("/projects/{project_id}/assistant")
def ask_grok(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    body: str = Form(""),
):
    project, membership, user = loaded
    question = (body or "").strip()
    try:
        respond(
            db,
            settings=request.app.state.settings,
            project=project,
            question=question,
            create_tasks="crée" in question.lower() and "tâche" in question.lower(),
        )
        db.commit()
    except RuntimeError as exc:
        db.rollback()
        set_flash(request, str(exc), "error")
    if request.headers.get("HX-Request"):
        return render(
            request,
            "partials/messages.html",
            project=project,
            membership=membership,
            messages=_messages(db, project.id),
            current_user=user,
        )
    return RedirectResponse(f"/projects/{project.id}/chat", status_code=303)
