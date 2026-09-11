"""Weekly élan rewards creating and finishing work."""

from sqlalchemy import select
from tests.conftest import login

from agora.constants import TaskStatus
from agora.models import Project, Task
from agora.seed import KICKOFF_TITLE, OWNER_EMAIL, SEED_PROJECT_NAME
from agora.services.momentum import member_scores, nudge


def test_creating_and_completing_tasks_earns_elan(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        project_id = project.id
    client.post(
        f"/projects/{project_id}/tasks",
        data={"title": "Préparer SWOT", "status": "todo", "next": f"/projects/{project_id}/board"},
        follow_redirects=False,
    )
    with app.state.session_factory() as session:
        task = session.scalar(select(Task).where(Task.title == "Préparer SWOT"))
        task_id = task.id
    client.post(
        f"/projects/{project_id}/tasks/{task_id}/status",
        data={"status": TaskStatus.DONE.value, "next": f"/projects/{project_id}/board"},
        follow_redirects=False,
    )
    with app.state.session_factory() as session:
        scores = member_scores(session, project_id=project_id, timeout_seconds=45)
        nicolas = next(item for item in scores if item.user.email == OWNER_EMAIL)
        assert nicolas.created >= 1
        assert nicolas.completed >= 1
        assert nicolas.points >= 3 + 5
        text = nudge(scores, nicolas.user)
        assert "élan" in text.lower() or "menez" in text


def test_board_and_dashboard_show_crew(client, app) -> None:
    login(client)
    home = client.get("/home")
    assert home.status_code == 200
    assert "Équipe".encode() in home.content or "élan".encode() in home.content
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    board = client.get(f"/projects/{project_id}/board")
    assert board.status_code == 200
    assert b"Nicolas" in board.content
    assert KICKOFF_TITLE.encode() in board.content


def test_chat_dock_available_everywhere(client, app) -> None:
    login(client)
    home = client.get("/home")
    assert home.status_code == 200
    assert b"chat-fab" in home.content
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    dock = client.get(f"/chat/dock/{project_id}")
    assert dock.status_code == 200
    assert b"Discussion" in dock.content
