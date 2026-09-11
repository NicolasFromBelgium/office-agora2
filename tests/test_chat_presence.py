"""Chat posting and presence heartbeat."""

from sqlalchemy import select
from tests.conftest import login

from agora.models import ChatMessage, Project, User
from agora.seed import SEED_PROJECT_NAME
from agora.services.presence import is_online


def test_chat_post_and_list(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    page = client.get(f"/projects/{project_id}/chat")
    assert page.status_code == 200
    response = client.post(
        f"/projects/{project_id}/chat",
        data={"body": "Roof quote arrived."},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Roof quote arrived." in response.content
    with app.state.session_factory() as session:
        messages = list(
            session.scalars(select(ChatMessage).where(ChatMessage.project_id == project_id))
        )
        assert any("Roof quote" in m.body for m in messages)


def test_presence_heartbeat_marks_online(client, app) -> None:
    login(client)
    response = client.post("/presence/heartbeat")
    assert response.status_code == 200
    assert b"Nicolas" in response.content
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.email == "leyssens.nicolas@gmail.com"))
        assert user.last_seen_at is not None
        assert is_online(user, timeout_seconds=45)
