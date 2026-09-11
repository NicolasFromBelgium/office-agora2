"""Project create, dashboard, and membership."""

from sqlalchemy import select
from tests.conftest import login

from agora.models import Project, ProjectMember, User
from agora.seed import SEED_PROJECT_NAME


def test_create_project(client, app) -> None:
    login(client)
    response = client.post(
        "/projects",
        data={"name": "Atelier", "description": "Workshop follow-up"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/projects/" in location
    assert location.endswith("/board")

    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == "Atelier"))
        assert project is not None
        assert project.description == "Workshop follow-up"
        nicolas = session.scalar(select(User).where(User.email == "leyssens.nicolas@gmail.com"))
        membership = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == nicolas.id,
            )
        )
        assert membership is not None
        assert membership.is_owner


def test_create_project_requires_name(client) -> None:
    login(client)
    response = client.post("/projects", data={"name": "  ", "description": ""})
    assert response.status_code == 422


def test_dashboard_lists_seed_project(client) -> None:
    login(client)
    response = client.get("/home")
    assert response.status_code == 200
    assert b"Leyssens" in response.content
    assert b"Continuer" in response.content
    assert b"Kick-off" in response.content
    assert b"SWOT" in response.content
    assert "Espace de travail familial" not in response.text


def test_invite_member(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        project_id = project.id
    response = client.post(
        f"/projects/{project_id}/members",
        data={"email": "colleague@example.com", "display_name": "Colleague"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.email == "colleague@example.com"))
        assert user is not None
        assert user.display_name == "Colleague"
