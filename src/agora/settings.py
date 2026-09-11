"""Load settings from environment variables.

Reads `.env` from the project root when present (local development).
In CI and production, values come from the real environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRUE_VALUES = {"1", "true", "yes", "on"}

DEFAULT_UPLOAD_EXTENSIONS = frozenset(
    {"pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "md", "csv", "docx", "xlsx", "zip"}
)


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _as_bool(value: str) -> bool:
    return value.strip().lower() in TRUE_VALUES


def _as_path(value: str, default: Path) -> Path:
    raw = value.strip()
    if not raw:
        return default
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _as_extensions(value: str) -> frozenset[str]:
    parts = {item.strip().lower().lstrip(".") for item in value.split(",") if item.strip()}
    return frozenset(parts) if parts else DEFAULT_UPLOAD_EXTENSIONS


@dataclass(frozen=True)
class Settings:
    app_env: str
    debug: bool
    log_level: str
    secret_key: str
    database_path: Path
    upload_dir: Path
    max_upload_bytes: int
    allowed_upload_extensions: frozenset[str]
    seed_default_password: str
    host: str
    port: int
    presence_timeout_seconds: int
    session_cookie_name: str
    root_path: str
    xai_api_key: str
    xai_model: str

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    @property
    def bcrypt_rounds(self) -> int:
        return 4 if self.app_env == "test" else 12


def load_settings(env_file: Path | None = None) -> Settings:
    _load_dotenv(env_file or PROJECT_ROOT / ".env")
    return Settings(
        app_env=os.environ.get("APP_ENV", "development"),
        debug=_as_bool(os.environ.get("APP_DEBUG", "false")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        secret_key=os.environ.get("SECRET_KEY", "change-me"),
        database_path=_as_path(
            os.environ.get("DATABASE_PATH", ""), PROJECT_ROOT / "data" / "agora.db"
        ),
        upload_dir=_as_path(os.environ.get("UPLOAD_DIR", ""), PROJECT_ROOT / "uploads"),
        max_upload_bytes=int(os.environ.get("MAX_UPLOAD_BYTES", "10485760")),
        allowed_upload_extensions=_as_extensions(
            os.environ.get("ALLOWED_UPLOAD_EXTENSIONS", "")
        ),
        seed_default_password=os.environ.get("SEED_DEFAULT_PASSWORD", "ChangeMe!OfficeAgora"),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        presence_timeout_seconds=int(os.environ.get("PRESENCE_TIMEOUT_SECONDS", "45")),
        session_cookie_name=os.environ.get("SESSION_COOKIE_NAME", "agora_session"),
        root_path=os.environ.get("ROOT_PATH", "").rstrip("/"),
        xai_api_key=os.environ.get("XAI_API_KEY", ""),
        xai_model=os.environ.get("XAI_MODEL", "grok-4.6"),
    )
