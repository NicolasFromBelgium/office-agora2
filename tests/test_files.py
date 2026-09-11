"""File uploads are stored locally and rejected when too large."""

import shutil
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from tests.conftest import login

from agora.models import FileAttachment, Project, User
from agora.seed import SEED_PROJECT_NAME
from agora.services.files import FileRejected, disk_path, file_kind, validate_upload
from agora.services.thumbs import THUMB_SIZE, ensure_thumbnail, thumb_path

PROXY_PHP = Path(__file__).resolve().parents[1] / "deploy" / "apache" / "proxy.php"


def test_file_upload_rejected_if_too_large(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    too_big = b"%PDF" + b"x" * (app.state.settings.max_upload_bytes + 10)
    response = client.post(
        f"/projects/{project_id}/files",
        files={"file": ("big.pdf", too_big, "application/pdf")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"trop volumineux" in response.content.lower()
    with app.state.session_factory() as session:
        stmt = select(FileAttachment).where(FileAttachment.project_id == project_id)
        count = len(list(session.scalars(stmt)))
    assert count == 0


def test_file_upload_rejected_for_type(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    response = client.post(
        f"/projects/{project_id}/files",
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"non autoris" in response.content.lower()


def test_file_upload_and_download(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    response = client.post(
        f"/projects/{project_id}/files",
        files={"file": ("notes.txt", b"hello agora", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with app.state.session_factory() as session:
        attachment = session.scalar(
            select(FileAttachment).where(FileAttachment.project_id == project_id)
        )
        assert attachment is not None
        file_id = attachment.id
    downloaded = client.get(f"/projects/{project_id}/files/{file_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"hello agora"
    viewer = client.get(f"/projects/{project_id}/files/{file_id}")
    assert viewer.status_code == 200
    assert "hello agora" in viewer.text
    assert "file-viewer-text" in viewer.text
    raw = client.get(f"/projects/{project_id}/files/{file_id}/raw")
    assert raw.status_code == 200
    assert raw.content == b"hello agora"


def test_image_thumbnail_on_files_page(client, app) -> None:
    login(client)
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    client.post(
        f"/projects/{project_id}/files",
        files={"file": ("logo.png", png, "image/png")},
    )
    page = client.get(f"/projects/{project_id}/files")
    assert page.status_code == 200
    assert "file-thumb" in page.text
    assert "/thumb" in page.text
    assert "Ouvrir" in page.text
    with app.state.session_factory() as session:
        attachment = session.scalar(
            select(FileAttachment).where(FileAttachment.original_filename == "logo.png")
        )
        assert attachment is not None
        file_id = attachment.id
        thumb_file = thumb_path(app.state.settings, attachment)
        assert thumb_file.is_file()
        view = client.get(f"/projects/{project_id}/files/{file_id}")
    assert view.status_code == 200
    assert "file-viewer-image" in view.text
    thumb = client.get(f"/projects/{project_id}/files/{file_id}/thumb")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"].startswith("image/jpeg")
    with Image.open(BytesIO(thumb.content)) as image:
        assert image.size == (THUMB_SIZE, THUMB_SIZE)


def test_backfill_builds_thumbs_for_existing_files(app) -> None:
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
        uploader_id = session.scalar(select(User.id))
        attachment = FileAttachment(
            project_id=project_id,
            task_id=None,
            uploader_id=uploader_id,
            original_filename="ancien.png",
            stored_name="legacy.png",
            content_type="image/png",
            size_bytes=len(png),
        )
        session.add(attachment)
        session.commit()
        dest = disk_path(app.state.settings, attachment)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(png)
        thumb = thumb_path(app.state.settings, attachment)
        if thumb.is_file():
            thumb.unlink()
        ensure_thumbnail(app.state.settings, attachment)
        assert thumb.is_file()
        with Image.open(thumb) as image:
            assert image.size == (THUMB_SIZE, THUMB_SIZE)


def test_file_kind_detects_images_and_pdfs() -> None:
    assert file_kind("a.PNG", "application/octet-stream") == "image"
    assert file_kind("doc.pdf", "application/pdf") == "pdf"
    assert file_kind("notes.txt", "text/plain") == "text"
    assert file_kind("pack.zip", "application/zip") == "other"


def test_validate_upload_empty(settings) -> None:
    try:
        validate_upload(filename="a.txt", size_bytes=0, settings=settings)
        raise AssertionError("expected rejection")
    except FileRejected as exc:
        assert exc.reason == "empty"


def test_file_upload_without_file_shows_flash_not_json(client, app) -> None:
    login(client)
    with app.state.session_factory() as session:
        project_id = session.scalar(select(Project).where(Project.name == SEED_PROJECT_NAME)).id
    response = client.post(f"/projects/{project_id}/files", data={}, follow_redirects=True)
    assert response.status_code == 200
    assert b"application/json" not in response.headers.get("content-type", "").encode()
    assert "n’a pas été reçu" in response.text or "n'a pas été reçu" in response.text


def test_php_proxy_rebuilds_multipart_with_file_field(tmp_path: Path) -> None:
    source = PROXY_PHP.read_text(encoding="utf-8")
    assert "agora_proxy_build_multipart" in source
    assert "$_FILES" in source
    php = shutil.which("php")
    if php is None:
        return
    payload = tmp_path / "doc.pdf"
    payload.write_bytes(b"%PDF-1.4 hello agora")
    script = (
        "define('AGORA_PROXY_LIB', true);\n"
        f"require {str(PROXY_PHP)!r};\n"
        "echo agora_proxy_build_multipart([], [\n"
        "  'file' => [\n"
        "    'name' => 'notes.pdf',\n"
        "    'type' => 'application/pdf',\n"
        f"    'tmp_name' => {str(payload)!r},\n"
        "    'error' => UPLOAD_ERR_OK,\n"
        f"    'size' => {payload.stat().st_size},\n"
        "  ],\n"
        "], 'TestBoundary');\n"
    )
    result = subprocess.run([php, "-r", script], check=True, capture_output=True, text=True)
    assert 'name="file"' in result.stdout
    assert 'filename="notes.pdf"' in result.stdout
    assert "%PDF-1.4 hello agora" in result.stdout
