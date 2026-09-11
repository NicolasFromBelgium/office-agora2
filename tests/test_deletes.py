"""Members can delete tasks, comments, and attachments."""

from sqlalchemy import select
from tests.conftest import login

from agora.constants import Action
from agora.models import ActivityLog, FileAttachment, Project, Task, TaskComment
from agora.seed import KICKOFF_TITLE, SEED_PROJECT_NAME


def test_delete_comment(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        task = session.scalar(
            select(Task).where(Task.project_id == project.id, Task.title == KICKOFF_TITLE)
        )
        project_id, task_id = project.id, task.id
    client.post(
        f"/projects/{project_id}/tasks/{task_id}/comments",
        data={"body": "À jeter"},
    )
    with app.state.session_factory() as session:
        comment = session.scalar(select(TaskComment).where(TaskComment.body == "À jeter"))
        comment_id = comment.id
    response = client.post(
        f"/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Commentaire supprimé." in response.text
    with app.state.session_factory() as session:
        assert session.get(TaskComment, comment_id) is None
        log = session.scalar(
            select(ActivityLog).where(ActivityLog.action == Action.COMMENT_DELETED)
        )
        assert log is not None


def test_delete_attachment(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    client.post(
        f"/projects/{project_id}/files",
        files={"file": ("jetable.txt", b"bye", "text/plain")},
    )
    with app.state.session_factory() as session:
        attachment = session.scalar(
            select(FileAttachment).where(FileAttachment.original_filename == "jetable.txt")
        )
        assert attachment is not None
        file_id = attachment.id
        stored = app.state.settings.upload_dir / str(project_id) / attachment.stored_name
        assert stored.is_file()
    response = client.post(
        f"/projects/{project_id}/files/{file_id}/delete",
        data={"next": f"/projects/{project_id}/files"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "a été supprimé" in response.text
    assert f'files/{file_id}/download' not in response.text
    assert not stored.is_file()
    with app.state.session_factory() as session:
        assert session.get(FileAttachment, file_id) is None


def test_delete_task_removes_comments_and_files(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    client.post(
        f"/projects/{project_id}/tasks",
        data={"title": "Tâche jetable", "status": "todo", "next": f"/projects/{project_id}/board"},
    )
    with app.state.session_factory() as session:
        task = session.scalar(select(Task).where(Task.title == "Tâche jetable"))
        task_id = task.id
    client.post(
        f"/projects/{project_id}/tasks/{task_id}/comments",
        data={"body": "commentaire lié"},
    )
    client.post(
        f"/projects/{project_id}/tasks/{task_id}/files",
        files={"file": ("annexe.txt", b"x", "text/plain")},
    )
    response = client.post(
        f"/projects/{project_id}/tasks/{task_id}/delete",
        data={"next": f"/projects/{project_id}/board"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Tâche jetable" not in response.text or "a été supprimée" in response.text
    with app.state.session_factory() as session:
        assert session.get(Task, task_id) is None
        leftover = session.scalars(select(TaskComment).where(TaskComment.body == "commentaire lié"))
        assert list(leftover) == []
        files = list(
            session.scalars(
                select(FileAttachment).where(FileAttachment.original_filename == "annexe.txt")
            )
        )
        assert files == []
        log = session.scalar(select(ActivityLog).where(ActivityLog.action == Action.TASK_DELETED))
        assert log is not None
