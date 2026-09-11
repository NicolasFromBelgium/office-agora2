"""Login is required; there is no public registration."""

from tests.conftest import SEED_PASSWORD, login


def test_dashboard_requires_login(client) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


def test_project_board_requires_login(client) -> None:
    response = client.get("/projects/1/board", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


def test_login_rejects_bad_password(client) -> None:
    response = client.post(
        "/login",
        data={"email": "leyssens.nicolas@gmail.com", "password": "wrong", "next": "/"},
    )
    assert response.status_code == 401
    assert b"incorrect" in response.content


def test_login_then_dashboard(client) -> None:
    login(client)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert "/board" in response.headers["location"]
    board = client.get(response.headers["location"])
    assert board.status_code == 200
    assert b"Office Agora" in board.content
    assert b"Nicolas Leyssens" in board.content
    assert b"Leyssens" in board.content


def test_logout_clears_session(client) -> None:
    login(client)
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    again = client.get("/", follow_redirects=False)
    assert again.status_code == 303


def test_no_public_registration_route(client) -> None:
    response = client.get("/register")
    assert response.status_code == 404


def test_login_page_available(client) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Connexion" in response.content
    assert SEED_PASSWORD.encode() not in response.content
