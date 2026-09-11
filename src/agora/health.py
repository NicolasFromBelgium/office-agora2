"""Runtime and CI health checks.

`status()` is the small, stable surface that tests and CI assert against.
"""

from agora import __version__


def status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "office-agora",
        "version": __version__,
    }


def is_healthy() -> bool:
    return status()["status"] == "ok"
