"""Likes on tasks and comments toggle and stay unique per user."""

from sqlalchemy import select
from tests.conftest import login

from agora.models import ActivityLog, Like, Project, Task, TaskComment
from agora.seed import KICKOFF_TITLE, SEED_PROJECT_NAME


def _kickoff(session) -> Task:
    project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
    task = session.scalar(
        select(Task).where(Task.project_id == project.id, Task.title == KICKOFF_TITLE)
    )
    assert task is not None
    return task


def test_like_and_unlike_task(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        task = _kickoff(session)
        project_id, task_id = task.project_id, task.id
    liked = client.post(
        f"/projects/{project_id}/tasks/{task_id}/like",
        follow_redirects=True,
    )
    assert liked.status_code == 200
    assert "like-btn-on" in liked.text
    with app.state.session_factory() as session:
        likes = list(session.scalars(select(Like).where(Like.task_id == task_id)))
        assert len(likes) == 1
        logs = list(session.scalars(select(ActivityLog).where(ActivityLog.task_id == task_id)))
        assert all(entry.action != "like" for entry in logs)
    again = client.post(
        f"/projects/{project_id}/tasks/{task_id}/like",
        follow_redirects=True,
    )
    assert again.status_code == 200
    assert "like-btn-on" not in again.text
    with app.state.session_factory() as session:
        likes = list(session.scalars(select(Like).where(Like.task_id == task_id)))
        assert likes == []


def test_like_comment(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        task = _kickoff(session)
        project_id, task_id = task.project_id, task.id
    client.post(
        f"/projects/{project_id}/tasks/{task_id}/comments",
        data={"body": "Bonne idée."},
    )
    with app.state.session_factory() as session:
        comment = session.scalar(select(TaskComment).where(TaskComment.body == "Bonne idée."))
        comment_id = comment.id
    response = client.post(
        f"/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/like",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "like-btn-on" in response.text
    with app.state.session_factory() as session:
        likes = list(session.scalars(select(Like).where(Like.comment_id == comment_id)))
        assert len(likes) == 1
        assert likes[0].task_id is None


def test_board_shows_task_like_control(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    board = client.get(f"/projects/{project_id}/board")
    assert board.status_code == 200
    assert "like-btn" in board.text
    assert "J’aime" in board.text
