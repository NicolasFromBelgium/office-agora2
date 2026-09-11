"""Local-disk attachments for projects and tasks."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from agora.constants import Action
from agora.models import FileAttachment, User
from agora.services.activity import log_activity
from agora.settings import Settings


class FileRejected(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp"})
PDF_EXTENSIONS = frozenset({"pdf"})
TEXT_EXTENSIONS = frozenset({"txt", "md", "csv"})
TEXT_PREVIEW_BYTES = 200_000


def extension_of(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def file_kind(filename: str, content_type: str = "") -> str:
    ext = extension_of(filename)
    ctype = (content_type or "").lower()
    if ext in IMAGE_EXTENSIONS or ctype.startswith("image/"):
        return "image"
    if ext in PDF_EXTENSIONS or ctype == "application/pdf":
        return "pdf"
    if ext in TEXT_EXTENSIONS or ctype.startswith("text/"):
        return "text"
    return "other"


def read_text_preview(path: Path) -> str:
    data = path.read_bytes()[:TEXT_PREVIEW_BYTES]
    return data.decode("utf-8", errors="replace")


def validate_upload(
    *,
    filename: str,
    size_bytes: int,
    settings: Settings,
) -> str:
    if size_bytes <= 0:
        raise FileRejected("empty", "Choisissez un fichier à envoyer.")
    if size_bytes > settings.max_upload_bytes:
        if settings.max_upload_bytes >= 1024 * 1024:
            limit = f"{settings.max_upload_bytes / (1024 * 1024):g} Mo"
        else:
            limit = f"{settings.max_upload_bytes} octets"
        raise FileRejected("too_large", f"Fichier trop volumineux (limite {limit}).")
    ext = extension_of(filename)
    if not ext or ext not in settings.allowed_upload_extensions:
        allowed = ", ".join(sorted(settings.allowed_upload_extensions))
        raise FileRejected(
            "type_not_allowed",
            f"Type de fichier non autorisé. Utilisez : {allowed}.",
        )
    return ext


def store_upload(
    session: Session,
    *,
    project_id: int,
    task_id: int | None,
    uploader: User,
    filename: str,
    content: bytes,
    content_type: str,
    settings: Settings,
) -> FileAttachment:
    ext = validate_upload(filename=filename, size_bytes=len(content), settings=settings)
    stored_name = f"{uuid4().hex}.{ext}"
    dest_dir = settings.upload_dir / str(project_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / stored_name
    dest.write_bytes(content)

    attachment = FileAttachment(
        project_id=project_id,
        task_id=task_id,
        uploader_id=uploader.id,
        original_filename=Path(filename).name,
        stored_name=stored_name,
        content_type=content_type or "application/octet-stream",
        size_bytes=len(content),
    )
    session.add(attachment)
    session.flush()
    from agora.services.thumbs import ensure_thumbnail

    ensure_thumbnail(settings, attachment)
    log_activity(
        session,
        project_id=project_id,
        actor=uploader,
        action=Action.FILE_UPLOADED,
        task_id=task_id,
        details={"filename": attachment.original_filename, "size_bytes": attachment.size_bytes},
    )
    return attachment


def disk_path(settings: Settings, attachment: FileAttachment) -> Path:
    return settings.upload_dir / str(attachment.project_id) / attachment.stored_name


def remove_attachment(
    session: Session,
    *,
    attachment: FileAttachment,
    actor: User,
    settings: Settings,
    write_activity: bool = True,
) -> None:
    path = disk_path(settings, attachment)
    if path.is_file():
        path.unlink()
    from agora.services.thumbs import remove_thumbnail

    remove_thumbnail(settings, attachment)
    filename = attachment.original_filename
    project_id = attachment.project_id
    task_id = attachment.task_id
    session.delete(attachment)
    if write_activity:
        log_activity(
            session,
            project_id=project_id,
            actor=actor,
            action=Action.FILE_DELETED,
            task_id=task_id,
            details={"filename": filename},
        )
    session.flush()
