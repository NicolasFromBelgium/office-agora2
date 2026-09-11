"""Grok bot user, briefing snapshot, and chat assistant."""

from sqlalchemy import select
from tests.conftest import login

from agora.models import ChatMessage, Project, User
from agora.seed import SEED_PROJECT_NAME
from agora.services.assistant import BOT_EMAIL, heuristic_reply
from agora.services.snapshot import capture_state, render_markdown, write_state_file


def test_grok_bot_is_seeded_member(app) -> None:
    with app.state.session_factory() as session:
        bot = session.scalar(select(User).where(User.email == BOT_EMAIL))
        assert bot is not None
        assert bot.is_bot is True
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        assert any(m.user_id == bot.id for m in project.members)


def test_bot_cannot_login(client) -> None:
    response = client.post(
        "/login",
        data={"email": BOT_EMAIL, "password": "ChangeMe!OfficeAgora", "next": "/"},
    )
    assert response.status_code == 401


def test_snapshot_lists_kickoff_and_gaps(app) -> None:
    with app.state.session_factory() as session:
        state = capture_state(session)
    assert state["projects"]
    leyssens = next(p for p in state["projects"] if p["name"] == SEED_PROJECT_NAME)
    titles = [t["title"] for t in leyssens["tasks"]]
    assert "Kick-off" in titles
    assert leyssens["gaps"]
    markdown = render_markdown(state)
    assert "Kick-off" in markdown
    assert "SWOT" in markdown


def test_heuristic_reply_mentions_documents() -> None:
    state = {
        "projects": [
            {
                "name": "Leyssens",
                "tasks": [{"title": "Kick-off", "status": "todo"}],
                "files": [],
                "recent_chat": [],
                "gaps": ["Aucun fichier sur le projet."],
                "suggestions": [{"title": "Brouillon SWOT", "description": "Une page."}],
            }
        ]
    }
    text = heuristic_reply(state, "")
    assert "SWOT" in text
    assert "finance" in text.lower()


def test_ask_grok_posts_bot_message(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    response = client.post(
        f"/projects/{project_id}/assistant",
        data={"body": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.state.session_factory() as session:
        bot = session.scalar(select(User).where(User.email == BOT_EMAIL))
        messages = list(
            session.scalars(
                select(ChatMessage).where(
                    ChatMessage.project_id == project_id,
                    ChatMessage.author_id == bot.id,
                )
            )
        )
        assert messages
        assert "SWOT" in messages[-1].body or "kick-off" in messages[-1].body.lower()


def test_state_api_requires_login(client) -> None:
    response = client.get("/api/state.json", follow_redirects=False)
    assert response.status_code == 303


def test_write_state_file_and_brief_cli(app, capsys, monkeypatch) -> None:
    with app.state.session_factory() as session:
        path = write_state_file(session, app.state.settings)
    assert path.is_file()
    assert "Kick-off" in path.read_text(encoding="utf-8")
    monkeypatch.setattr("agora.brief.load_settings", lambda: app.state.settings)
    from agora.brief import main

    main()
    out = capsys.readouterr().out
    assert "Kick-off" in out
    assert "Leyssens" in out


def test_state_api_returns_json(client) -> None:
    login(client)
    response = client.get("/api/state.json")
    assert response.status_code == 200
    body = response.json()
    assert body["projects"]
    assert body["projects"][0]["name"] == SEED_PROJECT_NAME
    md = client.get("/api/state.md")
    assert md.status_code == 200
    assert b"Kick-off" in md.content
