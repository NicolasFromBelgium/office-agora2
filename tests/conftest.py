"""Shared pytest fixtures."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agora.db import run_migrations
from agora.seed import seed_database
from agora.settings import Settings
from agora.web.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SEED_PASSWORD = "ChangeMe!OfficeAgora"
NICOLAS_EMAIL = "leyssens.nicolas@gmail.com"


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        debug=False,
        log_level="warning",
        secret_key="test-secret",
        database_path=tmp_path / "test.db",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
        allowed_upload_extensions=frozenset({"pdf", "png", "txt", "md"}),
        seed_default_password=SEED_PASSWORD,
        host="127.0.0.1",
        port=8000,
        presence_timeout_seconds=45,
        session_cookie_name="agora_session_test",
        root_path="",
        xai_api_key="",
        xai_model="grok-4.6",
        crawl_db_path=tmp_path / "crawl.db",
        crawl_state_path=tmp_path / "bot-state.json",
    )


@pytest.fixture
def app(settings: Settings):
    application = create_app(settings)
    run_migrations(settings.database_url)
    with application.state.session_factory() as session:
        seed_database(session, settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def login(
    client: TestClient,
    email: str = NICOLAS_EMAIL,
    password: str = SEED_PASSWORD,
):
    response = client.post(
        "/login",
        data={"email": email, "password": password, "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return response
