"""Short-polling heartbeat for connected users."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from agora.models import User
from agora.services.presence import online_users, touch
from agora.web.deps import get_db, require_user
from agora.web.templating import render

router = APIRouter(tags=["presence"])


@router.post("/presence/heartbeat")
def heartbeat(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    touch(db, user)
    db.commit()
    people = online_users(db, request.app.state.settings.presence_timeout_seconds)
    return render(
        request,
        "partials/presence.html",
        current_user=user,
        online_users=people,
    )
