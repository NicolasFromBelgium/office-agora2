"""Project- and task-level activity log."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from agora.constants import Action, status_label
from agora.models import ActivityLog, User


def log_activity(
    session: Session,
    *,
    project_id: int,
    actor: User,
    action: str,
    task_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        project_id=project_id,
        task_id=task_id,
        actor_id=actor.id,
        action=action,
        details=details,
    )
    session.add(entry)
    session.flush()
    return entry


def describe_activity(entry: ActivityLog) -> str:
    actor = entry.actor.display_name if entry.actor else "Quelqu’un"
    details = entry.details or {}
    title = details.get("title") or details.get("filename") or details.get("email") or ""

    if entry.action == Action.PROJECT_CREATED:
        return f"{actor} a créé le projet"
    if entry.action == Action.MEMBER_ADDED:
        return f"{actor} a ajouté {details.get('name') or details.get('email') or 'un membre'}"
    if entry.action == Action.TASK_CREATED:
        return f"{actor} a créé la tâche « {title} »"
    if entry.action == Action.TASK_STATUS_CHANGED:
        old = status_label(str(details.get("from", "?")))
        new = status_label(str(details.get("to", "?")))
        return f"{actor} a déplacé « {title} » de {old} vers {new}"
    if entry.action == Action.TASK_ASSIGNED:
        assignee = details.get("assignee") or "non assigné"
        return f"{actor} a assigné « {title} » à {assignee}"
    if entry.action == Action.FILE_UPLOADED:
        return f"{actor} a envoyé {title or 'un fichier'}"
    if entry.action == Action.TASK_COMMENTED:
        snippet = str(details.get("body") or "").replace("\n", " ").strip()
        if len(snippet) > 80:
            snippet = snippet[:77] + "…"
        if snippet:
            return f"{actor} a commenté « {title} » : {snippet}"
        return f"{actor} a commenté « {title} »"
    if entry.action == Action.TASK_DELETED:
        return f"{actor} a supprimé la tâche « {title} »"
    if entry.action == Action.COMMENT_DELETED:
        return f"{actor} a supprimé un commentaire sur « {title} »"
    if entry.action == Action.FILE_DELETED:
        return f"{actor} a supprimé {title or 'un fichier'}"
    if entry.action == Action.EVENT_CREATED:
        return f"{actor} a créé l’événement « {title} »"
    if entry.action == Action.EVENT_UPDATED:
        return f"{actor} a modifié l’événement « {title} »"
    if entry.action == Action.EVENT_DELETED:
        return f"{actor} a supprimé l’événement « {title} »"
    return f"{actor} {entry.action}"
