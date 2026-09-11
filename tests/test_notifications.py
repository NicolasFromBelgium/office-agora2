"""Assignment notifications appear on the bell with a red dot until read."""

from sqlalchemy import select
from tests.conftest import SEED_PASSWORD, login

from agora.models import Notification, Project, Task, User
from agora.seed import SEED_PROJECT_NAME

OLIVIA = "olivia.leyssens@gmail.com"


def test_assigning_someone_else_creates_unread_notification(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        olivia = session.scalar(select(User).where(User.email == OLIVIA))
        project_id, olivia_id = project.id, olivia.id
    created = client.post(
        f"/projects/{project_id}/tasks",
        data={
            "title": "Relire le SWOT",
            "status": "todo",
            "assignee_id": str(olivia_id),
            "next": f"/projects/{project_id}/board",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    with app.state.session_factory() as session:
        note = session.scalar(
            select(Notification).where(
                Notification.user_id == olivia_id,
                Notification.title == "Relire le SWOT",
            )
        )
        assert note is not None
        assert note.read_at is None
        task_id = note.task_id

    login(client, email=OLIVIA, password=SEED_PASSWORD)
    home = client.get("/", follow_redirects=True)
    assert home.status_code == 200
    assert "notif-dot" in home.text
    assert "vous a assigné" in home.text
    assert "Relire le SWOT" in home.text

    detail = client.get(f"/projects/{project_id}/tasks/{task_id}")
    assert detail.status_code == 200
    with app.state.session_factory() as session:
        note = session.scalar(
            select(Notification).where(
                Notification.user_id == olivia_id,
                Notification.title == "Relire le SWOT",
            )
        )
        assert note.read_at is not None


def test_self_assign_does_not_notify(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        nicolas = session.scalar(select(User).where(User.email == "leyssens.nicolas@gmail.com"))
        project_id, user_id = project.id, nicolas.id
        notes = session.scalars(select(Notification).where(Notification.user_id == user_id))
        before = len(list(notes))
    client.post(
        f"/projects/{project_id}/tasks",
        data={
            "title": "Ma propre note",
            "status": "todo",
            "assignee_id": str(user_id),
            "next": f"/projects/{project_id}/board",
        },
    )
    with app.state.session_factory() as session:
        notes = session.scalars(select(Notification).where(Notification.user_id == user_id))
        after = len(list(notes))
    assert after == before


def test_mark_all_notifications_read(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        olivia = session.scalar(select(User).where(User.email == OLIVIA))
        project_id, olivia_id = project.id, olivia.id
    client.post(
        f"/projects/{project_id}/tasks",
        data={
            "title": "Préparer l’ordre du jour",
            "status": "todo",
            "assignee_id": str(olivia_id),
            "next": f"/projects/{project_id}/board",
        },
    )
    login(client, email=OLIVIA, password=SEED_PASSWORD)
    response = client.post("/notifications/read-all", follow_redirects=True)
    assert response.status_code == 200
    assert "notif-dot" not in response.text
    with app.state.session_factory() as session:
        unread = list(
            session.scalars(
                select(Notification).where(
                    Notification.user_id == olivia_id,
                    Notification.read_at.is_(None),
                )
            )
        )
    assert unread == []


def test_assigned_open_tasks_listed_in_bell(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        nicolas = session.scalar(select(User).where(User.email == "leyssens.nicolas@gmail.com"))
        task = Task(
            project_id=project.id,
            title="Tâche cloche",
            description="",
            status="todo",
            assignee_id=nicolas.id,
            created_by_id=nicolas.id,
        )
        session.add(task)
        session.commit()
    home = client.get("/", follow_redirects=True)
    assert "Tâche cloche" in home.text
    assert "Mes tâches" in home.text
