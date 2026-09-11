"""Square JPEG thumbnails for file lists. Generated at upload and on demand."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from agora.models import FileAttachment
from agora.services.files import disk_path, extension_of, file_kind
from agora.settings import Settings

THUMB_SIZE = 128
THUMB_QUALITY = 82
PAPER = (243, 240, 255)
INK = (109, 40, 217)


def thumb_path(settings: Settings, attachment: FileAttachment) -> Path:
    stem = Path(attachment.stored_name).stem
    return settings.upload_dir / str(attachment.project_id) / ".thumbs" / f"{stem}.jpg"


def remove_thumbnail(settings: Settings, attachment: FileAttachment) -> None:
    path = thumb_path(settings, attachment)
    if path.is_file():
        path.unlink()


def ensure_thumbnail(settings: Settings, attachment: FileAttachment) -> Path:
    dest = thumb_path(settings, attachment)
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = disk_path(settings, attachment)
    kind = file_kind(attachment.original_filename, attachment.content_type)
    if kind == "image" and src.is_file():
        try:
            _write_image_thumb(src.read_bytes(), dest)
            return dest
        except Exception:
            pass
    _write_badge_thumb(extension_of(attachment.original_filename), dest)
    return dest


def backfill_thumbnails(session: Session, settings: Settings) -> int:
    created = 0
    rows = list(session.scalars(select(FileAttachment)))
    for attachment in rows:
        dest = thumb_path(settings, attachment)
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        try:
            ensure_thumbnail(settings, attachment)
            created += 1
        except Exception:
            continue
    return created


def _to_rgb(image):
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(image) or image
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, PAPER)
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def write_square_jpeg(content: bytes, dest: Path, size: int = THUMB_SIZE) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _write_image_thumb(content, dest, size=size)


def write_circle_png(content: bytes, dest: Path, size: int) -> None:
    """Center-crop to a square, then mask to an antialiased circle."""
    from PIL import Image, ImageDraw, ImageOps

    dest.parent.mkdir(parents=True, exist_ok=True)
    oversample = 4
    big = size * oversample
    with Image.open(BytesIO(content)) as image:
        try:
            image.seek(0)
        except EOFError:
            pass
        rgb = _to_rgb(image)
        fitted = ImageOps.fit(rgb, (big, big), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        rgba = fitted.convert("RGBA")
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
        rgba.putalpha(mask)
        circle = rgba.resize((size, size), Image.Resampling.LANCZOS)
        circle.save(dest, "PNG", optimize=True)


def _write_image_thumb(content: bytes, dest: Path, size: int = THUMB_SIZE) -> None:
    from PIL import Image, ImageOps

    with Image.open(BytesIO(content)) as image:
        try:
            image.seek(0)
        except EOFError:
            pass
        rgb = _to_rgb(image)
        fitted = ImageOps.fit(rgb, (size, size), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        fitted.save(dest, "JPEG", quality=THUMB_QUALITY, optimize=True)


def _write_badge_thumb(ext: str, dest: Path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), PAPER)
    draw = ImageDraw.Draw(image)
    label = (ext or "file")[:4].upper()
    font = _badge_font()
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (THUMB_SIZE - text_w) / 2 - bbox[0]
    y = (THUMB_SIZE - text_h) / 2 - bbox[1]
    draw.text((x, y), label, fill=INK, font=font)
    image.save(dest, "JPEG", quality=THUMB_QUALITY, optimize=True)


def _badge_font():
    from PIL import ImageFont

    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, 26)
        except OSError:
            continue
    return ImageFont.load_default()
