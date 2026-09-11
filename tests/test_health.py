"""Application health checks used by local tests and CI."""

from agora import __version__
from agora.health import is_healthy, status


def test_health_status_is_ok() -> None:
    info = status()
    assert info["status"] == "ok"
    assert info["service"] == "office-agora"
    assert info["version"] == __version__


def test_is_healthy() -> None:
    assert is_healthy() is True


def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "office-agora"


def test_main_starts_web_server(monkeypatch) -> None:
    called: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        called["app"] = app
        called["kwargs"] = kwargs

    monkeypatch.setattr("agora.__main__.uvicorn.run", fake_run)
    from agora.__main__ import main

    main()
    assert called["app"] == "agora.web.app:app"
