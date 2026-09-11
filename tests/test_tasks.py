"""Task status changes write an activity log."""

from sqlalchemy import select
from tests.conftest import login

from agora.constants import Action, TaskStatus
from agora.models import ActivityLog, Project, Task
from agora.seed import KICKOFF_TITLE, SEED_PROJECT_NAME


def _leyssens_task(session, title: str = KICKOFF_TITLE) -> Task:
    project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
    task = session.scalar(select(Task).where(Task.project_id == project.id, Task.title == title))
    assert task is not None
    return task


def test_status_change_writes_activity_log(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        task = _leyssens_task(session)
        project_id, task_id = task.project_id, task.id
        old_status = task.status

    response = client.post(
        f"/projects/{project_id}/tasks/{task_id}/status",
        data={"status": TaskStatus.DOING.value, "next": f"/projects/{project_id}/board"},
        follow_redirects=False,
    )
    assert response.status_code in {200, 303}

    with app.state.session_factory() as session:
        task = session.get(Task, task_id)
        assert task.status == TaskStatus.DOING.value
        logs = list(
            session.scalars(
                select(ActivityLog).where(
                    ActivityLog.task_id == task_id,
                    ActivityLog.action == Action.TASK_STATUS_CHANGED,
                )
            )
        )
        assert logs
        latest = logs[-1]
        assert latest.details is not None
        assert latest.details["from"] == old_status
        assert latest.details["to"] == TaskStatus.DOING.value
        assert latest.actor_id is not None


def test_create_task_on_board(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        project_id = project.id
    response = client.post(
        f"/projects/{project_id}/tasks",
        data={
            "title": "Note de suivi",
            "status": "todo",
            "next": f"/projects/{project_id}/board",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with app.state.session_factory() as session:
        task = session.scalar(select(Task).where(Task.title == "Note de suivi"))
        assert task is not None
        assert response.headers["location"].endswith(f"/board?created={task.id}")
        created = session.scalar(
            select(ActivityLog).where(
                ActivityLog.task_id == task.id,
                ActivityLog.action == Action.TASK_CREATED,
            )
        )
        assert created is not None


def test_task_detail_and_assign(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        task = _leyssens_task(session, KICKOFF_TITLE)
        project_id, task_id = task.project_id, task.id
        from agora.models import User

        olivia = session.scalar(select(User).where(User.email == "olivia.leyssens@gmail.com"))
        olivia_id = olivia.id
    page = client.get(f"/projects/{project_id}/tasks/{task_id}")
    assert page.status_code == 200
    assert KICKOFF_TITLE.encode() in page.content
    response = client.post(
        f"/projects/{project_id}/tasks/{task_id}",
        data={
            "title": KICKOFF_TITLE,
            "description": "Updated note",
            "status": TaskStatus.TODO.value,
            "assignee_id": str(olivia_id),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.state.session_factory() as session:
        task = session.get(Task, task_id)
        assert task.description == "Updated note"
        assert task.assignee_id == olivia_id
        assert task.status == TaskStatus.TODO.value


def test_project_root_redirects_to_board(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    response = client.get(f"/projects/{project_id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/board")


def test_board_and_list_pages(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    board = client.get(f"/projects/{project_id}/board")
    assert board.status_code == 200
    assert KICKOFF_TITLE.encode() in board.content
    assert "col-add" in board.text
    assert "compose-heading" in board.text
    assert "agoraCompose" in board.text
    assert "agoraCompose({ kind: 'task'" in board.text
    assert "compose.js" in board.text
    assert 'id="compose-overlay"' in board.text
    js = client.get("/static/compose.js")
    assert js.status_code == 200
    assert b"function openCompose" in js.content or b"openCompose" in js.content
    listing = client.get(f"/projects/{project_id}/list")
    assert listing.status_code == 200
    assert KICKOFF_TITLE.encode() in listing.content
    assert "compose-heading" in listing.text


def test_new_task_is_highlighted_on_board(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    created = client.post(
        f"/projects/{project_id}/tasks",
        data={
            "title": "Tâche mise en avant",
            "description": "Depuis la fenêtre",
            "status": "doing",
            "assignee_id": "",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    location = created.headers["location"]
    assert "created=" in location
    board = client.get(location)
    assert board.status_code == 200
    assert "Tâche mise en avant" in board.text
    assert "task-just-created" in board.text
    assert "En cours" in board.text
    activity = client.get(f"/projects/{project_id}/activity")
    assert activity.status_code == 200
