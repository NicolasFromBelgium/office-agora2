"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agora.db import make_engine, make_session_factory, run_migrations
from agora.health import status as health_status
from agora.seed import seed_database
from agora.settings import Settings, load_settings
from agora.web.deps import NotAuthenticated, NotFound, login_redirect
from agora.web.routes import (
    agenda,
    assistant,
    auth,
    chat,
    comments,
    dashboard,
    files,
    likes,
    notifications,
    presence,
    profile,
    projects,
    state,
    tasks,
)
from agora.web.templating import render, set_flash
from agora.web.urls import redirect

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class PrefixLocationMiddleware:
    """Prefix absolute Location headers when mounted behind Apache at /office."""

    def __init__(self, app: ASGIApp, root_path: str) -> None:
        self.app = app
        self.root = (root_path or "").rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.root or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = []
                prefix = self.root.encode()
                for key, value in message.get("headers", []):
                    if (
                        key == b"location"
                        and value.startswith(b"/")
                        and not value.startswith(prefix)
                    ):
                        value = prefix + value
                    headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        run_migrations(settings.database_url)
        with session_factory() as session:
            seed_database(session, settings)
            from agora.services.thumbs import backfill_thumbnails

            backfill_thumbnails(session, settings)
        yield

    app = FastAPI(
        title="Office Agora",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        root_path=settings.root_path or "",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie_name,
        same_site="lax",
        https_only=settings.app_env == "production",
        max_age=14 * 24 * 3600,
        path=settings.root_path or "/",
    )
    if settings.root_path:
        app.add_middleware(PrefixLocationMiddleware, root_path=settings.root_path)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(projects.router)
    app.include_router(tasks.router)
    app.include_router(agenda.router)
    app.include_router(comments.router)
    app.include_router(likes.router)
    app.include_router(files.router)
    app.include_router(chat.router)
    app.include_router(assistant.router)
    app.include_router(state.router)
    app.include_router(notifications.router)
    app.include_router(profile.router)
    app.include_router(presence.router)

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse(health_status())

    @app.exception_handler(NotAuthenticated)
    async def _(request: Request, exc: NotAuthenticated):
        return login_redirect(request, str(exc) if str(exc) else None)

    @app.exception_handler(NotFound)
    async def not_found_handler(request: Request, exc: NotFound):
        return render(request, "404.html", status_code=404, message=str(exc) or "Page introuvable.")

    @app.exception_handler(404)
    async def http_404(request: Request, _exc):
        return render(request, "404.html", status_code=404, message="Page introuvable.")

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        if not _missing_upload_file(exc):
            return JSONResponse(status_code=422, content={"detail": exc.errors()})
        set_flash(
            request,
            "Le fichier n’a pas été reçu. Réessayez, ou choisissez un document plus petit.",
            "error",
        )
        referer = request.headers.get("referer")
        if referer:
            return RedirectResponse(referer, status_code=303)
        path = request.url.path
        if path.endswith("/files") and "/tasks/" in path:
            path = path[: -len("/files")]
        return redirect(request, path or "/")

    return app


def _missing_upload_file(exc: RequestValidationError) -> bool:
    return any(
        err.get("type") == "missing" and "file" in (err.get("loc") or ())
        for err in exc.errors()
    )


_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """Lazy ASGI app so importing create_app in tests does not open the default DB."""
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)
