"""Request dependencies: database session, login, project membership."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.models import Project, ProjectMember, User
from agora.services.notifications import bell_context
from agora.services.presence import online_users, touch
from agora.services.projects import get_membership, user_projects
from agora.web.urls import redirect


def last_board_path(db: Session, user: User) -> str | None:
    projects = user_projects(db, user.id)
    if not projects:
        return None
    if user.last_project_id and any(item.id == user.last_project_id for item in projects):
        return f"/projects/{user.last_project_id}/board"
    return f"/projects/{projects[0].id}/board"


class NotAuthenticated(Exception):
    """Raised when a session is missing; converted to a login redirect."""


class NotFound(Exception):
    """Project or record is missing, or the user is not a member."""


def get_db(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        return None
    touch(db, user)
    db.commit()
    return user


def require_user(request: Request, user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        raise NotAuthenticated(next_url)
    return user


def require_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> tuple[Project, ProjectMember, User]:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.members).selectinload(ProjectMember.user))
    )
    if project is None:
        raise NotFound("Projet introuvable.")
    membership = get_membership(db, project.id, user.id)
    if membership is None:
        raise NotFound("Projet introuvable.")
    if not project.is_archived:
        user.last_project_id = project.id
        db.commit()
    request.state.project = project
    request.state.membership = membership
    return project, membership, user


def shell_context(request: Request, db: Session, user: User) -> dict:
    projects = user_projects(db, user.id)
    chat_project = next((item for item in projects if item.id == user.last_project_id), None)
    if chat_project is None and projects:
        chat_project = projects[0]
    return {
        "current_user": user,
        "projects": projects,
        "online_users": online_users(db, request.app.state.settings.presence_timeout_seconds),
        "chat_project": chat_project,
        **bell_context(db, user.id),
    }


def login_redirect(request: Request, next_url: str | None = None):
    if next_url and next_url.startswith("/"):
        return redirect(request, f"/login?next={next_url}")
    return redirect(request, "/login")
