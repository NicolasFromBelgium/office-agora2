"""Project and task file upload/download."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.models import FileAttachment, Task
from agora.services.files import (
    FileRejected,
    disk_path,
    file_kind,
    read_text_preview,
    remove_attachment,
    store_upload,
)
from agora.services.thumbs import ensure_thumbnail
from agora.web.deps import NotFound, get_db, require_project, shell_context
from agora.web.routes.tasks import _safe_next
from agora.web.templating import render, set_flash

router = APIRouter(tags=["files"])


@router.get("/projects/{project_id}/files")
def project_files(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    attachments = list(
        db.scalars(
            select(FileAttachment)
            .where(FileAttachment.project_id == project.id)
            .options(selectinload(FileAttachment.uploader), selectinload(FileAttachment.task))
            .order_by(FileAttachment.created_at.desc())
        )
    )
    return render(
        request,
        "projects/files.html",
        project=project,
        membership=membership,
        attachments=attachments,
        active_tab="files",
        **shell_context(request, db, user),
    )


def _store(
    request: Request,
    db: Session,
    project,
    user,
    upload: UploadFile,
    task_id: int | None,
    next_url: str,
):
    filename = upload.filename or "upload"
    content = upload.file.read()
    try:
        store_upload(
            db,
            project_id=project.id,
            task_id=task_id,
            uploader=user,
            filename=filename,
            content=content,
            content_type=upload.content_type or "application/octet-stream",
            settings=request.app.state.settings,
        )
        db.commit()
        set_flash(request, f"{filename} envoyé.", "info")
    except FileRejected as exc:
        db.rollback()
        set_flash(request, exc.message, "error")
    return RedirectResponse(next_url, status_code=303)


@router.post("/projects/{project_id}/files")
async def upload_project_file(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    file: UploadFile = File(...),
):
    project, _membership, user = loaded
    return _store(request, db, project, user, file, None, f"/projects/{project.id}/files")


@router.post("/projects/{project_id}/tasks/{task_id}/files")
async def upload_task_file(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    file: UploadFile = File(...),
):
    project, _membership, user = loaded
    task = db.get(Task, task_id)
    if task is None or task.project_id != project.id:
        raise NotFound("Tâche introuvable.")
    return _store(
        request,
        db,
        project,
        user,
        file,
        task.id,
        f"/projects/{project.id}/tasks/{task.id}",
    )


def _attachment_or_404(db: Session, project_id: int, file_id: int) -> FileAttachment:
    attachment = db.get(FileAttachment, file_id)
    if attachment is None or attachment.project_id != project_id:
        raise NotFound("Fichier introuvable.")
    return attachment


@router.get("/projects/{project_id}/files/{file_id}")
def view_file(
    request: Request,
    file_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    attachment = db.scalar(
        select(FileAttachment)
        .where(FileAttachment.id == file_id, FileAttachment.project_id == project.id)
        .options(selectinload(FileAttachment.uploader), selectinload(FileAttachment.task))
    )
    if attachment is None:
        raise NotFound("Fichier introuvable.")
    path = disk_path(request.app.state.settings, attachment)
    if not path.is_file():
        raise NotFound("Fichier introuvable.")
    kind = file_kind(attachment.original_filename, attachment.content_type)
    preview = read_text_preview(path) if kind == "text" else ""
    return render(
        request,
        "projects/file_view.html",
        project=project,
        membership=membership,
        attachment=attachment,
        kind=kind,
        preview=preview,
        active_tab="files",
        **shell_context(request, db, user),
    )


@router.get("/projects/{project_id}/files/{file_id}/thumb")
def file_thumbnail(
    request: Request,
    file_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, _membership, _user = loaded
    attachment = _attachment_or_404(db, project.id, file_id)
    path = ensure_thumbnail(request.app.state.settings, attachment)
    if not path.is_file():
        raise NotFound("Fichier introuvable.")
    return FileResponse(
        path,
        media_type="image/jpeg",
        content_disposition_type="inline",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/projects/{project_id}/files/{file_id}/raw")
def raw_file(
    request: Request,
    file_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, _membership, _user = loaded
    attachment = _attachment_or_404(db, project.id, file_id)
    path = disk_path(request.app.state.settings, attachment)
    if not path.is_file():
        raise NotFound("Fichier introuvable.")
    return FileResponse(
        path,
        filename=attachment.original_filename,
        media_type=attachment.content_type,
        content_disposition_type="inline",
    )


@router.get("/projects/{project_id}/files/{file_id}/download")
def download_file(
    request: Request,
    file_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, _membership, _user = loaded
    attachment = _attachment_or_404(db, project.id, file_id)
    path = disk_path(request.app.state.settings, attachment)
    if not path.is_file():
        raise NotFound("Fichier introuvable.")
    return FileResponse(
        path,
        filename=attachment.original_filename,
        media_type=attachment.content_type,
    )


@router.post("/projects/{project_id}/files/{file_id}/delete")
def delete_file(
    request: Request,
    file_id: int,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    next: str = Form(""),
):
    project, _membership, user = loaded
    attachment = db.get(FileAttachment, file_id)
    if attachment is None or attachment.project_id != project.id:
        raise NotFound("Fichier introuvable.")
    filename = attachment.original_filename
    fallback = f"/projects/{project.id}/files"
    if attachment.task_id:
        fallback = f"/projects/{project.id}/tasks/{attachment.task_id}"
    remove_attachment(
        db,
        attachment=attachment,
        actor=user,
        settings=request.app.state.settings,
    )
    db.commit()
    set_flash(request, f"{filename} a été supprimé.", "info")
    return RedirectResponse(_safe_next(project.id, next) if next else fallback, status_code=303)
