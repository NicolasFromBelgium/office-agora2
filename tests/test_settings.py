"""Settings load from environment and .env files."""

from pathlib import Path

from agora.settings import load_settings


def test_load_settings_from_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment should be ignored",
                "",
                "not-a-valid-line",
                "APP_ENV=test",
                "APP_DEBUG=true",
                "LOG_LEVEL=debug",
                "SECRET_KEY=unit-test-secret",
                "DATABASE_PATH=data/custom.db",
                "SEED_DEFAULT_PASSWORD=ChangeMe!OfficeAgora",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "APP_ENV",
        "APP_DEBUG",
        "LOG_LEVEL",
        "SECRET_KEY",
        "DATABASE_PATH",
        "SEED_DEFAULT_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = load_settings(env_file)

    assert settings.app_env == "test"
    assert settings.debug is True
    assert settings.log_level == "debug"
    assert settings.secret_key == "unit-test-secret"
    assert settings.database_path.name == "custom.db"
    assert settings.seed_default_password == "ChangeMe!OfficeAgora"


def test_load_settings_when_env_file_missing(tmp_path: Path, monkeypatch) -> None:
    for key in ("APP_ENV", "APP_DEBUG", "LOG_LEVEL", "SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)

    settings = load_settings(tmp_path / "missing.env")

    assert settings.app_env == "development"
    assert settings.debug is False
    assert settings.log_level == "info"
    assert settings.secret_key == "change-me"


def test_env_example_documents_required_keys(project_root: Path) -> None:
    example = (project_root / ".env.example").read_text(encoding="utf-8")
    for key in (
        "APP_ENV",
        "APP_DEBUG",
        "LOG_LEVEL",
        "SECRET_KEY",
        "DATABASE_PATH",
        "UPLOAD_DIR",
        "MAX_UPLOAD_BYTES",
        "ALLOWED_UPLOAD_EXTENSIONS",
        "SEED_DEFAULT_PASSWORD",
        "XAI_API_KEY",
    ):
        assert key in example
    assert "ChangeMe!OfficeAgora" in example
