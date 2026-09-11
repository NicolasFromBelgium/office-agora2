"""Agenda, calendar events, and task due dates."""

from sqlalchemy import select
from tests.conftest import login

from agora.constants import Action
from agora.models import ActivityLog, CalendarEvent, Project, Task
from agora.seed import KICKOFF_TITLE, SEED_PROJECT_NAME
from agora.services.dates import as_brussels, parse_due, parse_event_span, shift_month


def _project_id(app) -> int:
    with app.state.session_factory() as session:
        return session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id


def test_parse_due_rejects_blank_and_invalid() -> None:
    assert parse_due("", "") is None
    assert parse_due("not-a-date", "10:00") is None


def test_parse_due_date_only_is_midnight() -> None:
    due = parse_due("2026-09-15", "")
    assert due is not None
    assert due.year == 2026
    assert due.month == 9
    assert due.day == 15
    assert due.hour == 0
    assert due.minute == 0


def test_parse_event_span_defaults_one_hour() -> None:
    span = parse_event_span(
        start_date="2026-09-15",
        start_time="10:00",
        end_date="",
        end_time="",
        all_day=False,
    )
    assert span is not None
    start, end = span
    assert start.hour == 10
    assert end.hour == 11


def test_shift_month_wraps_year() -> None:
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2026, 12, 1) == (2027, 1)


def test_agenda_page_lists_kickoff(client, app) -> None:
    login(client)
    project_id = _project_id(app)
    page = client.get(f"/projects/{project_id}/agenda")
    assert page.status_code == 200
    assert "Agenda" in page.text
    assert KICKOFF_TITLE in page.text
    assert "compose-heading" in page.text
    assert "Créer" in page.text


def test_create_event_appears_on_agenda(client, app) -> None:
    login(client)
    project_id = _project_id(app)
    created = client.post(
        f"/projects/{project_id}/events",
        data={
            "title": "Point immo",
            "description": "Visite et offre",
            "start_date": "2026-09-15",
            "start_time": "10:00",
            "end_date": "2026-09-15",
            "end_time": "11:00",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert "/agenda?created=" in created.headers["location"]
    with app.state.session_factory() as session:
        event = session.scalar(select(CalendarEvent).where(CalendarEvent.title == "Point immo"))
        assert event is not None
        assert event.all_day is False
        assert as_brussels(event.starts_at).hour == 10
        log = session.scalar(
            select(ActivityLog).where(
                ActivityLog.action == Action.EVENT_CREATED,
                ActivityLog.project_id == project_id,
            )
        )
        assert log is not None
        event_id = event.id
    agenda = client.get(f"/projects/{project_id}/agenda?year=2026&month=9")
    assert agenda.status_code == 200
    assert "Point immo" in agenda.text
    detail = client.get(f"/projects/{project_id}/events/{event_id}")
    assert detail.status_code == 200
    assert "Visite et offre" in detail.text
    updated = client.post(
        f"/projects/{project_id}/events/{event_id}",
        data={
            "title": "Point immo (maj)",
            "description": "Offre révisée",
            "start_date": "2026-09-15",
            "start_time": "14:00",
            "end_date": "2026-09-15",
            "end_time": "15:00",
        },
        follow_redirects=True,
    )
    assert updated.status_code == 200
    assert "Point immo (maj)" in updated.text
    with app.state.session_factory() as session:
        event = session.get(CalendarEvent, event_id)
        assert event.title == "Point immo (maj)"
        assert as_brussels(event.starts_at).hour == 14


def test_all_day_event_and_delete(client, app) -> None:
    login(client)
    project_id = _project_id(app)
    client.post(
        f"/projects/{project_id}/events",
        data={
            "title": "Salon immobilier",
            "start_date": "2026-09-20",
            "all_day": "on",
        },
        follow_redirects=False,
    )
    with app.state.session_factory() as session:
        event = session.scalar(
            select(CalendarEvent).where(CalendarEvent.title == "Salon immobilier")
        )
        assert event is not None
        assert event.all_day is True
        event_id = event.id
    deleted = client.post(
        f"/projects/{project_id}/events/{event_id}/delete",
        data={"next": f"/projects/{project_id}/agenda"},
        follow_redirects=False,
    )
    assert deleted.status_code == 303
    with app.state.session_factory() as session:
        assert session.get(CalendarEvent, event_id) is None
        log = session.scalar(
            select(ActivityLog).where(ActivityLog.action == Action.EVENT_DELETED)
        )
        assert log is not None


def test_event_without_title_is_rejected(client, app) -> None:
    login(client)
    project_id = _project_id(app)
    response = client.post(
        f"/projects/{project_id}/events",
        data={"title": "   ", "start_date": "2026-09-15"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "titre" in response.text.lower()
    with app.state.session_factory() as session:
        assert session.scalar(select(CalendarEvent).where(CalendarEvent.title == "   ")) is None


def test_create_task_with_due_date_shows_on_agenda(client, app) -> None:
    login(client)
    project_id = _project_id(app)
    created = client.post(
        f"/projects/{project_id}/tasks",
        data={
            "title": "Relancer le notaire",
            "status": "todo",
            "due_date": "2026-09-22",
            "due_time": "16:30",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    with app.state.session_factory() as session:
        task = session.scalar(select(Task).where(Task.title == "Relancer le notaire"))
        assert task is not None
        assert task.due_at is not None
        due = as_brussels(task.due_at)
        assert due.day == 22
        assert due.hour == 16
        assert due.minute == 30
        task_id = task.id
    agenda = client.get(f"/projects/{project_id}/agenda?year=2026&month=9")
    assert "Relancer le notaire" in agenda.text
    detail = client.get(f"/projects/{project_id}/tasks/{task_id}")
    assert detail.status_code == 200
    assert 'name="due_date"' in detail.text
    saved = client.post(
        f"/projects/{project_id}/tasks/{task_id}",
        data={
            "title": "Relancer le notaire",
            "description": "Appeler avant 17h",
            "status": "todo",
            "assignee_id": "",
            "due_date": "2026-09-23",
            "due_time": "",
        },
        follow_redirects=True,
    )
    assert saved.status_code == 200
    with app.state.session_factory() as session:
        task = session.get(Task, task_id)
        due = as_brussels(task.due_at)
        assert due.day == 23
        assert due.hour == 0
