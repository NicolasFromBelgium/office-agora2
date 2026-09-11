"""Project chat: Teams-style list + compose, also served in the floating dock."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.models import ChatMessage
from agora.services.assistant import respond
from agora.web.deps import get_db, require_project, shell_context
from agora.web.templating import render, set_flash

router = APIRouter(tags=["chat"])


def _messages(db: Session, project_id: int) -> list[ChatMessage]:
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.project_id == project_id)
            .options(selectinload(ChatMessage.author))
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(500)
        )
    )


@router.get("/projects/{project_id}/chat")
def chat_page(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    return render(
        request,
        "projects/chat.html",
        project=project,
        membership=membership,
        messages=_messages(db, project.id),
        active_tab="chat",
        **shell_context(request, db, user),
    )


@router.get("/projects/{project_id}/chat/messages")
def chat_messages(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    return render(
        request,
        "partials/messages.html",
        project=project,
        membership=membership,
        messages=_messages(db, project.id),
        current_user=user,
    )


@router.post("/projects/{project_id}/chat")
def post_message(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    body: str = Form(...),
):
    project, membership, user = loaded
    text = body.strip()
    if not text:
        set_flash(request, "Écrivez d’abord un message.", "error")
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
    db.add(ChatMessage(project_id=project.id, author_id=user.id, body=text[:4000]))
    db.commit()
    lowered = text.lower()
    if "@grok" in lowered or lowered.startswith("grok"):
        try:
            respond(
                db,
                settings=request.app.state.settings,
                project=project,
                question=text,
            )
            db.commit()
        except RuntimeError:
            db.rollback()
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


@router.get("/chat/dock/{project_id}")
def chat_dock(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    return render(
        request,
        "partials/chat_dock.html",
        project=project,
        membership=membership,
        messages=_messages(db, project.id),
        **shell_context(request, db, user),
    )
