"""Project create, membership, and listing."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.constants import Action, MemberRole
from agora.models import Project, ProjectMember, User
from agora.services.activity import log_activity
from agora.services.passwords import hash_password
from agora.settings import Settings


def user_projects(session: Session, user_id: int) -> list[Project]:
    stmt = (
        select(Project)
        .join(ProjectMember)
        .where(ProjectMember.user_id == user_id, Project.archived_at.is_(None))
        .options(selectinload(Project.members).selectinload(ProjectMember.user))
        .order_by(Project.updated_at.desc(), Project.id.desc())
    )
    return list(session.scalars(stmt).unique())


def get_membership(session: Session, project_id: int, user_id: int) -> ProjectMember | None:
    return session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )


def create_project(
    session: Session,
    *,
    owner: User,
    name: str,
    description: str = "",
) -> Project:
    project = Project(name=name.strip(), description=description.strip(), owner_id=owner.id)
    session.add(project)
    session.flush()
    session.add(
        ProjectMember(project_id=project.id, user_id=owner.id, role=MemberRole.OWNER.value)
    )
    log_activity(
        session,
        project_id=project.id,
        actor=owner,
        action=Action.PROJECT_CREATED,
        details={"name": project.name},
    )
    owner.last_project_id = project.id
    session.flush()
    return project


def add_member(
    session: Session,
    *,
    project: Project,
    actor: User,
    email: str,
    display_name: str,
    settings: Settings,
) -> tuple[User, bool]:
    """Add a member by email. Creates an invite-only account when missing.

    Returns (user, created).
    """
    normalized = email.strip().lower()
    user = session.scalar(select(User).where(User.email == normalized))
    created = False
    if user is None:
        name = display_name.strip() or normalized.split("@")[0]
        user = User(
            email=normalized,
            display_name=name,
            password_hash=hash_password(settings.seed_default_password, settings.bcrypt_rounds),
        )
        session.add(user)
        session.flush()
        created = True
    existing = get_membership(session, project.id, user.id)
    if existing is None:
        session.add(
            ProjectMember(project_id=project.id, user_id=user.id, role=MemberRole.MEMBER.value)
        )
        log_activity(
            session,
            project_id=project.id,
            actor=actor,
            action=Action.MEMBER_ADDED,
            details={"email": user.email, "name": user.display_name},
        )
        session.flush()
    return user, created
