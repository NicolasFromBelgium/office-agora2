"""Profile photos are stored outside project files and cropped to an 80px circle."""

from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from tests.conftest import login

from agora.models import FileAttachment, Project, User
from agora.seed import SEED_PROJECT_NAME
from agora.services.avatars import AVATAR_FOLDER, AVATAR_SIZE, avatar_thumb_path
from agora.services.thumbs import write_circle_png

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def test_home_redirects_to_last_project_board(client) -> None:
    landed = login(client)
    assert "/board" in landed.headers["location"]
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert "/board" in response.headers["location"]


def test_project_name_links_to_board(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    files_page = client.get(f"/projects/{project_id}/files")
    assert files_page.status_code == 200
    assert f">{SEED_PROJECT_NAME}</a>" in files_page.text


def test_upload_avatar_creates_thumb_outside_project_files(client, app) -> None:
    login(client)
    response = client.post(
        "/me/avatar",
        files={"file": ("moi.png", PNG, "image/png")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Photo de profil" in response.text
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.email == "leyssens.nicolas@gmail.com"))
        assert user.avatar_name
        user_id = user.id
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
        leaked = list(
            session.scalars(
                select(FileAttachment).where(FileAttachment.original_filename == "moi.png")
            )
        )
        assert leaked == []
    thumb = client.get(f"/avatars/{user_id}/thumb")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"].startswith("image/png")
    with Image.open(BytesIO(thumb.content)) as image:
        assert image.size == (AVATAR_SIZE, AVATAR_SIZE)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        assert image.getpixel((AVATAR_SIZE - 1, 0))[3] == 0
        assert image.getpixel((AVATAR_SIZE // 2, AVATAR_SIZE // 2))[3] > 200
    path = avatar_thumb_path(app.state.settings, user_id)
    assert path.is_file()
    assert path.name == "thumb.png"
    assert AVATAR_FOLDER in str(path)
    assert str(project_id) not in path.parts
    files_page = client.get(f"/projects/{project_id}/files")
    assert "moi.png" not in files_page.text
    header = client.get(f"/projects/{project_id}/board")
    assert f"/avatars/{user_id}/thumb" in header.text
    assert 'class="avatar avatar-profile"' in header.text
    assert 'width="80"' in header.text


def test_avatar_circle_center_crops_wide_photos(tmp_path) -> None:
    source = Image.new("RGB", (200, 80), (220, 38, 38))
    for x in range(80, 120):
        for y in range(80):
            source.putpixel((x, y), (37, 99, 235))
    raw = BytesIO()
    source.save(raw, "PNG")
    dest = tmp_path / "thumb.png"
    write_circle_png(raw.getvalue(), dest, size=AVATAR_SIZE)
    with Image.open(dest) as image:
        assert image.size == (80, 80)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        center = image.getpixel((40, 40))
        assert center[2] > center[0]
        assert center[3] > 200


def test_profile_avatar_css_is_an_80px_circle() -> None:
    css = (Path(__file__).resolve().parents[1] / "src" / "agora" / "static" / "app.css").read_text(
        encoding="utf-8"
    )
    assert ".avatar-profile" in css
    assert "width: 80px" in css
    assert "height: 80px" in css
    assert "border-radius: 50%" in css


def test_avatar_rejects_non_image(client) -> None:
    login(client)
    response = client.post(
        "/me/avatar",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Photo" in response.text or "image" in response.text.lower()
