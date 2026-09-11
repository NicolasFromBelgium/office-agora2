"""Seed creates the Leyssens project and family members."""

from sqlalchemy import select

from agora.models import Project, ProjectMember, Task, User
from agora.seed import DEMO_TASK_TITLES, KICKOFF_TITLE, OWNER_EMAIL, SEED_PROJECT_NAME, SEED_USERS


def test_seed_creates_leyssens_members(app) -> None:
    with app.state.session_factory() as session:
        emails = {email for email, _name in SEED_USERS}
        found = {row.email for row in session.scalars(select(User))}
        assert emails <= found

        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        assert project is not None
        members = list(
            session.scalars(select(ProjectMember).where(ProjectMember.project_id == project.id))
        )
        assert len(members) == 5
        owner = session.scalar(select(User).where(User.email == OWNER_EMAIL))
        assert owner is not None
        assert project.owner_id == owner.id

        titles = {
            row.title
            for row in session.scalars(select(Task).where(Task.project_id == project.id))
        }
        assert KICKOFF_TITLE in titles
        assert titles.isdisjoint(DEMO_TASK_TITLES)
        kickoff = session.scalar(
            select(Task).where(Task.project_id == project.id, Task.title == KICKOFF_TITLE)
        )
        assert kickoff is not None
        assert kickoff.due_at is not None
        assert "SWOT" in kickoff.description


def test_seed_is_idempotent(app) -> None:
    from agora.seed import seed_database

    with app.state.session_factory() as session:
        seed_database(session, app.state.settings)
        seed_database(session, app.state.settings)
        count = len(list(session.scalars(select(User))))
        projects = list(session.scalars(select(Project).where(Project.name == SEED_PROJECT_NAME)))
    assert count == 5
    assert len(projects) == 1


def test_seed_renames_legacy_leyssens_project(app) -> None:
    from agora.seed import seed_database

    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        assert project is not None
        project.name = "Leyssens"
        session.commit()
        seed_database(session, app.state.settings)
        renamed = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        leftover = session.scalar(select(Project).where(Project.name == "Leyssens"))
    assert renamed is not None
    assert leftover is None
