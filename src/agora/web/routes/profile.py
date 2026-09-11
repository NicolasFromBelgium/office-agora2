"""Profile photo upload, outside project file attachments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from agora.models import User
from agora.services.avatars import delete_avatar, ensure_avatar_thumb, save_avatar
from agora.services.files import FileRejected
from agora.web.deps import NotFound, get_db, require_user
from agora.web.templating import set_flash

router = APIRouter(tags=["profile"])


@router.post("/me/avatar")
def upload_avatar(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    file: UploadFile = File(...),
):
    content = file.file.read()
    try:
        save_avatar(
            request.app.state.settings,
            user,
            filename=file.filename or "photo.jpg",
            content=content,
        )
        db.commit()
        set_flash(request, "Photo de profil mise à jour.", "info")
    except FileRejected as exc:
        db.rollback()
        set_flash(request, exc.message, "error")
    referer = request.headers.get("referer")
    if referer:
        return RedirectResponse(referer, status_code=303)
    return RedirectResponse("/", status_code=303)


@router.post("/me/avatar/delete")
def remove_avatar(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    delete_avatar(request.app.state.settings, user)
    db.commit()
    set_flash(request, "Photo de profil retirée.", "info")
    referer = request.headers.get("referer")
    if referer:
        return RedirectResponse(referer, status_code=303)
    return RedirectResponse("/", status_code=303)


@router.get("/avatars/{user_id}/thumb")
def avatar_thumb(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_user),
):
    person = db.get(User, user_id)
    if person is None or not person.avatar_name:
        raise NotFound("Photo introuvable.")
    path = ensure_avatar_thumb(request.app.state.settings, person)
    if path is None or not path.is_file():
        raise NotFound("Photo introuvable.")
    return FileResponse(
        path,
        media_type="image/png",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )
