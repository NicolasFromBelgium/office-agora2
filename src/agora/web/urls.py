"""Path prefix helper for reverse-proxy mounts such as /office."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse


def href(root_path: str, path: str) -> str:
    prefix = (root_path or "").rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    if not prefix:
        return path
    if path == prefix or path.startswith(prefix + "/"):
        return path
    return prefix + path


def request_href(request: Request, path: str) -> str:
    return href(request.app.state.settings.root_path, path)


def redirect(request: Request, path: str, status_code: int = 303) -> RedirectResponse:
    location = request_href(request, path)
    headers = {}
    if request.headers.get("HX-Request"):
        headers["HX-Redirect"] = location
    return RedirectResponse(location, status_code=status_code, headers=headers)
