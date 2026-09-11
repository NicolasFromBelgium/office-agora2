"""Profile photos, stored outside project file attachments."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from agora.models import User
from agora.services.files import IMAGE_EXTENSIONS, FileRejected, extension_of
from agora.services.thumbs import write_circle_png
from agora.settings import Settings

AVATAR_FOLDER = "avatars"
AVATAR_SIZE = 80
AVATAR_THUMB_NAME = "thumb.png"


def avatar_dir(settings: Settings, user_id: int) -> Path:
    return settings.upload_dir / AVATAR_FOLDER / str(user_id)


def avatar_original_path(settings: Settings, user: User) -> Path | None:
    if not user.avatar_name:
        return None
    return avatar_dir(settings, user.id) / user.avatar_name


def avatar_thumb_path(settings: Settings, user_id: int) -> Path:
    return avatar_dir(settings, user_id) / AVATAR_THUMB_NAME


def save_avatar(settings: Settings, user: User, *, filename: str, content: bytes) -> None:
    ext = extension_of(filename)
    if ext not in IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(IMAGE_EXTENSIONS))
        raise FileRejected(
            "type_not_allowed",
            f"Photo : utilisez {allowed}.",
        )
    if len(content) <= 0:
        raise FileRejected("empty", "Choisissez une image.")
    if len(content) > settings.max_upload_bytes:
        raise FileRejected("too_large", "Image trop volumineuse.")
    folder = avatar_dir(settings, user.id)
    if folder.is_dir():
        for old in folder.iterdir():
            if old.is_file():
                old.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid4().hex}.{ext}"
    (folder / stored).write_bytes(content)
    try:
        write_circle_png(content, folder / AVATAR_THUMB_NAME, size=AVATAR_SIZE)
    except Exception as exc:
        for leftover in folder.iterdir():
            leftover.unlink()
        raise FileRejected("type_not_allowed", "Image illisible.") from exc
    user.avatar_name = stored


def delete_avatar(settings: Settings, user: User) -> None:
    folder = avatar_dir(settings, user.id)
    if folder.is_dir():
        for old in folder.iterdir():
            if old.is_file():
                old.unlink()
    user.avatar_name = None


def _is_avatar_thumb(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    try:
        from PIL import Image

        with Image.open(path) as image:
            if image.size != (AVATAR_SIZE, AVATAR_SIZE):
                return False
            if image.mode not in {"RGBA", "LA"}:
                return False
            corner = image.getpixel((0, 0))
            return corner[-1] == 0
    except Exception:
        return False


def ensure_avatar_thumb(settings: Settings, user: User) -> Path | None:
    thumb = avatar_thumb_path(settings, user.id)
    if _is_avatar_thumb(thumb):
        return thumb
    original = avatar_original_path(settings, user)
    source = original.read_bytes() if original is not None and original.is_file() else None
    if source is None:
        legacy = avatar_dir(settings, user.id) / "thumb.jpg"
        if legacy.is_file():
            source = legacy.read_bytes()
        elif thumb.is_file():
            source = thumb.read_bytes()
    if not source:
        return None
    try:
        write_circle_png(source, thumb, size=AVATAR_SIZE)
        legacy = avatar_dir(settings, user.id) / "thumb.jpg"
        if legacy.is_file():
            legacy.unlink()
        return thumb
    except Exception:
        return None
