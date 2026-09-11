"""Activity log wording."""

from agora.constants import Action
from agora.models import ActivityLog, User
from agora.services.activity import describe_activity


def test_describe_status_change() -> None:
    actor = User(email="a@example.com", display_name="Olivia Leyssens", password_hash="x")
    entry = ActivityLog(
        project_id=1,
        actor=actor,
        action=Action.TASK_STATUS_CHANGED,
        details={"title": "AREI", "from": "todo", "to": "doing"},
    )
    text = describe_activity(entry)
    assert "Olivia Leyssens" in text
    assert "AREI" in text
    assert "À faire" in text
    assert "En cours" in text


def test_describe_task_comment() -> None:
    actor = User(email="a@example.com", display_name="Nicolas Leyssens", password_hash="x")
    entry = ActivityLog(
        project_id=1,
        actor=actor,
        action=Action.TASK_COMMENTED,
        details={"title": "Kick-off", "body": "On commence par le SWOT."},
    )
    text = describe_activity(entry)
    assert "Nicolas Leyssens" in text
    assert "Kick-off" in text
    assert "SWOT" in text


def test_describe_deletes() -> None:
    actor = User(email="a@example.com", display_name="Nicolas Leyssens", password_hash="x")
    task = describe_activity(
        ActivityLog(
            project_id=1,
            actor=actor,
            action=Action.TASK_DELETED,
            details={"title": "Kick-off"},
        )
    )
    assert "supprimé la tâche" in task
    file_text = describe_activity(
        ActivityLog(
            project_id=1,
            actor=actor,
            action=Action.FILE_DELETED,
            details={"filename": "notes.txt"},
        )
    )
    assert "notes.txt" in file_text
    event_text = describe_activity(
        ActivityLog(
            project_id=1,
            actor=actor,
            action=Action.EVENT_CREATED,
            details={"title": "Point immo"},
        )
    )
    assert "événement" in event_text
    assert "Point immo" in event_text
