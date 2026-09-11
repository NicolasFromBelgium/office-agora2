"""Members can comment on a task; empty notes are rejected."""

from pathlib import Path

from sqlalchemy import select
from tests.conftest import login

from agora.constants import Action
from agora.models import ActivityLog, Project, Task, TaskComment
from agora.seed import KICKOFF_TITLE, SEED_PROJECT_NAME
from agora.services.activity import describe_activity


def _kickoff(session) -> Task:
    project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
    task = session.scalar(
        select(Task).where(Task.project_id == project.id, Task.title == KICKOFF_TITLE)
    )
    assert task is not None
    return task


def test_comment_on_task_shows_on_detail_and_activity(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        task = _kickoff(session)
        project_id, task_id = task.project_id, task.id
    response = client.post(
        f"/projects/{project_id}/tasks/{task_id}/comments",
        data={"body": "On commence par le SWOT."},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "On commence par le SWOT." in response.text
    assert "Commentaires" in response.text
    with app.state.session_factory() as session:
        comments = list(session.scalars(select(TaskComment).where(TaskComment.task_id == task_id)))
        assert len(comments) == 1
        assert comments[0].body == "On commence par le SWOT."
        log = session.scalar(
            select(ActivityLog).where(
                ActivityLog.task_id == task_id,
                ActivityLog.action == Action.TASK_COMMENTED,
            )
        )
        assert log is not None
        assert "SWOT" in describe_activity(log)
    board = client.get(f"/projects/{project_id}/board")
    assert board.status_code == 200
    assert "1 comm." in board.text
    listing = client.get(f"/projects/{project_id}/list")
    assert listing.status_code == 200
    assert "Comm." in listing.text


def test_empty_comment_is_rejected(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        task = _kickoff(session)
        project_id, task_id = task.project_id, task.id
    response = client.post(
        f"/projects/{project_id}/tasks/{task_id}/comments",
        data={"body": "   "},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Écrivez d’abord un commentaire." in response.text
    with app.state.session_factory() as session:
        comments = session.scalars(select(TaskComment).where(TaskComment.task_id == task_id))
        count = len(list(comments))
    assert count == 0


def test_chat_css_keeps_long_text_inside_the_dock() -> None:
    css = (Path(__file__).resolve().parents[1] / "src" / "agora" / "static" / "app.css").read_text(
        encoding="utf-8"
    )
    assert "overflow-wrap: anywhere" in css
    assert ".chat-dock-compose textarea" in css
    assert "min-width: 0" in css
    assert ".chat-dock-actions" in css
