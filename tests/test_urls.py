"""URL prefix used when Apache mounts the app at /office."""

from agora.web.urls import href


def test_href_without_prefix() -> None:
    assert href("", "/login") == "/login"
    assert href("", "/") == "/"


def test_href_with_office_prefix() -> None:
    assert href("/office", "/login") == "/office/login"
    assert href("/office", "/") == "/office/"
    assert href("/office", "/office/login") == "/office/login"
