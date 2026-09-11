"""Session cookie login and logout. No public registration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from agora.models import User
from agora.services.passwords import verify_password
from agora.web.deps import get_current_user, get_db, last_board_path
from agora.web.templating import render, set_flash

router = APIRouter(tags=["auth"])


@router.get("/login")
def login_form(
    request: Request,
    next: str = "/",
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if user is not None:
        target = next if next.startswith("/") else "/"
        if target in {"/", ""}:
            board = last_board_path(db, user)
            if board:
                target = board
        return RedirectResponse(target, status_code=303)
    return render(request, "login.html", next=next)


@router.post("/login")
def login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    normalized = email.strip().lower()
    user = db.scalar(
        select(User).where(
            User.email == normalized,
            User.is_active.is_(True),
            User.is_bot.is_(False),
        )
    )
    if user is None or not verify_password(password, user.password_hash):
        set_flash(request, "E-mail ou mot de passe incorrect.", "error")
        return render(request, "login.html", status_code=401, next=next, email=normalized)

    request.session.clear()
    request.session["user_id"] = user.id
    target = next if next.startswith("/") else "/"
    if target in {"/", ""}:
        board = last_board_path(db, user)
        if board:
            target = board
    return RedirectResponse(target, status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
