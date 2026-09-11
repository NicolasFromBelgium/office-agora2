"""HTTP snapshot so Grok (or a script) can read project state."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from agora.models import User
from agora.services.snapshot import capture_state, render_markdown, write_state_file
from agora.web.deps import get_db, require_user

router = APIRouter(tags=["state"])


@router.get("/api/state.json")
def state_json(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    state = capture_state(db)
    write_state_file(db, request.app.state.settings)
    return JSONResponse(state)


@router.get("/api/state.md")
def state_markdown(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    state = capture_state(db)
    write_state_file(db, request.app.state.settings)
    return PlainTextResponse(render_markdown(state), media_type="text/markdown; charset=utf-8")
