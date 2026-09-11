"""Idempotent seed: Leyssens project, members, kick-off du jour."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from agora.constants import MemberRole, TaskStatus
from agora.db import make_engine, make_session_factory, run_migrations
from agora.models import (
    ActivityLog,
    ChatMessage,
    FileAttachment,
    Project,
    ProjectMember,
    Task,
    User,
)
from agora.services.assistant import BOT_EMAIL, BOT_NAME
from agora.services.passwords import hash_password
from agora.services.projects import create_project
from agora.services.snapshot import write_state_file
from agora.services.tasks import create_task
from agora.settings import Settings, load_settings

BRUSSELS = ZoneInfo("Europe/Brussels")

SEED_USERS: tuple[tuple[str, str], ...] = (
    ("olivia.leyssens@gmail.com", "Olivia Leyssens"),
    ("adrien.leyssens@live.be", "Adrien Leyssens"),
    ("leyssens.nicolas@gmail.com", "Nicolas Leyssens"),
    ("laurentleyssens1@gmail.com", "Laurent Leyssens"),
)

SEED_PROJECT_NAME = "Leyssens Immo SRL"
LEGACY_PROJECT_NAMES = ("Leyssens",)
SEED_PROJECT_DESCRIPTION = ""

OWNER_EMAIL = "leyssens.nicolas@gmail.com"

KICKOFF_TITLE = "Kick-off"
KICKOFF_DESCRIPTION = (
    "Réunion de lancement.\n\n"
    "Ordre du jour :\n"
    "• Idées\n"
    "• Finance\n"
    "• Produire une analyse SWOT\n"
    "• Sélectionner ou affiner les projets"
)

# Anciens exemples / restes de test à retirer du tableau.
DEMO_TASK_TITLES = frozenset(
    {
        "Acte / house admin",
        "Atelier registration",
        "EPC / roof",
        "AREI",
        "Insurance quote",
    }
)


def kickoff_due_at(now: datetime | None = None) -> datetime:
    current = now or datetime.now(BRUSSELS)
    if current.tzinfo is None:
        current = current.replace(tzinfo=BRUSSELS)
    else:
        current = current.astimezone(BRUSSELS)
    return current.replace(hour=13, minute=0, second=0, microsecond=0)


def _get_or_create_user(
    session: Session,
    email: str,
    display_name: str,
    settings: Settings,
    *,
    is_bot: bool = False,
) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(settings.seed_default_password, settings.bcrypt_rounds),
            is_bot=is_bot,
        )
        session.add(user)
        session.flush()
    elif is_bot and not user.is_bot:
        user.is_bot = True
    return user


def _remove_demo_tasks(session: Session, project_id: int) -> None:
    stale = list(
        session.scalars(
            select(Task).where(Task.project_id == project_id, Task.title.in_(DEMO_TASK_TITLES))
        )
    )
    for task in stale:
        session.execute(delete(ActivityLog).where(ActivityLog.task_id == task.id))
        session.execute(delete(FileAttachment).where(FileAttachment.task_id == task.id))
        session.delete(task)


def _remove_demo_noise(session: Session, project_id: int, settings: Settings) -> None:
    leftovers = list(
        session.scalars(
            select(FileAttachment).where(
                FileAttachment.project_id == project_id,
                FileAttachment.original_filename.in_(("agora-notes.txt", "notes.txt")),
            )
        )
    )
    for attachment in leftovers:
        path = settings.upload_dir / str(project_id) / attachment.stored_name
        if path.is_file():
            path.unlink()
        session.delete(attachment)


def seed_database(session: Session, settings: Settings) -> Project:
    users = {
        email: _get_or_create_user(session, email, name, settings) for email, name in SEED_USERS
    }
    owner = users[OWNER_EMAIL]

    project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
    if project is None:
        for legacy_name in LEGACY_PROJECT_NAMES:
            project = session.scalar(select(Project).where(Project.name == legacy_name))
            if project is not None:
                project.name = SEED_PROJECT_NAME
                break
    if project is None:
        project = create_project(
            session,
            owner=owner,
            name=SEED_PROJECT_NAME,
            description=SEED_PROJECT_DESCRIPTION,
        )
    else:
        project.description = SEED_PROJECT_DESCRIPTION

    for user in users.values():
        membership = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == user.id,
            )
        )
        if membership is None:
            role = MemberRole.OWNER.value if user.id == owner.id else MemberRole.MEMBER.value
            session.add(ProjectMember(project_id=project.id, user_id=user.id, role=role))

    _remove_demo_tasks(session, project.id)
    _remove_demo_noise(session, project.id, settings)

    due = kickoff_due_at()
    kickoff = session.scalar(
        select(Task).where(Task.project_id == project.id, Task.title == KICKOFF_TITLE)
    )
    if kickoff is None:
        create_task(
            session,
            project_id=project.id,
            actor=owner,
            title=KICKOFF_TITLE,
            description=KICKOFF_DESCRIPTION,
            status=TaskStatus.TODO.value,
            assignee_id=owner.id,
            due_at=due,
        )
    else:
        kickoff.description = KICKOFF_DESCRIPTION
        kickoff.due_at = due
        kickoff.assignee_id = owner.id
        if kickoff.status == TaskStatus.DONE.value:
            kickoff.status = TaskStatus.TODO.value

    bot = _get_or_create_user(session, BOT_EMAIL, BOT_NAME, settings, is_bot=True)
    bot_member = session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == bot.id,
        )
    )
    if bot_member is None:
        session.add(
            ProjectMember(project_id=project.id, user_id=bot.id, role=MemberRole.MEMBER.value)
        )
    intro = session.scalar(
        select(ChatMessage).where(
            ChatMessage.project_id == project.id,
            ChatMessage.author_id == bot.id,
        )
    )
    if intro is None:
        session.add(
            ChatMessage(
                project_id=project.id,
                author_id=bot.id,
                body=(
                    "Salut, c’est Grok — je suis sur le projet avec vous.\n\n"
                    "Pour le kick-off de 13h : idées, finance, SWOT, puis on choisit "
                    "ou affine les projets.\n"
                    "Dites-moi @Grok si vous voulez un classement, une liste de documents "
                    "à rassembler, ou que je crée les tâches proposées."
                ),
            )
        )
    write_state_file(session, settings)

    session.commit()
    return project


def main() -> None:
    settings = load_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    with factory() as session:
        seed_database(session, settings)
    print(f"Seeded {SEED_PROJECT_NAME} ({len(SEED_USERS)} members).")


if __name__ == "__main__":
    main()
