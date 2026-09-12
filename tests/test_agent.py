"""AGENT tab is reachable on the Leyssens 2026 project."""

from tests.conftest import login

from agora.seed import SEED_PROJECT_NAME


def _project_id(app) -> int:
    from sqlalchemy import select

    from agora.models import Project

    with app.state.session_factory() as session:
        project = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME))
        assert project is not None
        return project.id


def test_agent_tab_on_seed_project(client, app) -> None:
    login(client)
    pid = _project_id(app)
    home = client.get(f"/projects/{pid}/agent", follow_redirects=False)
    assert home.status_code == 303
    assert home.headers["location"].endswith("/agent/brut")

    raw = client.get(f"/projects/{pid}/agent/brut")
    assert raw.status_code == 200
    assert "Données brutes" in raw.text
    assert "AGENT" in raw.text
    assert "arrêté" in raw.text or "en cours" in raw.text

    analyse = client.get(f"/projects/{pid}/agent/analyse")
    assert analyse.status_code == 200
    assert "mathématiques" in analyse.text
    assert "Qwen" in analyse.text

    tasks = client.get(f"/projects/{pid}/agent/taches")
    assert tasks.status_code == 200
    assert "heuristiques" in tasks.text
    assert "Qwen" in tasks.text
