"""Header bell: assigned tasks and unread assignment notices."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from agora.models import User
from agora.services.notifications import bell_context, mark_all_read, unread_count
from agora.web.deps import get_db, require_user
from agora.web.templating import render

router = APIRouter(tags=["notifications"])


@router.get("/notifications/badge")
def notification_badge(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    return render(
        request,
        "partials/notif_badge.html",
        current_user=user,
        unread_count=unread_count(db, user.id),
    )


@router.post("/notifications/read-all")
def read_all_notifications(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    mark_all_read(db, user.id)
    db.commit()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "partials/notifications.html",
            current_user=user,
            notif_oob=True,
            **bell_context(db, user.id),
        )
    referer = request.headers.get("referer")
    if referer:
        return RedirectResponse(referer, status_code=303)
    return RedirectResponse("/", status_code=303)
