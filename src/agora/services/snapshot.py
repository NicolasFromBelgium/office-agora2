"""Capture the state of every project as JSON and Markdown.

This is the surface Grok (the agent and the in-app bot) reads.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.constants import TaskStatus, status_label
from agora.models import (
    ActivityLog,
    ChatMessage,
    FileAttachment,
    Project,
    ProjectMember,
    Task,
)
from agora.services.activity import describe_activity
from agora.settings import PROJECT_ROOT, Settings

STATE_PATH = PROJECT_ROOT / "data" / "project-state.md"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _gaps_for_project(project: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    titles = " ".join(t["title"].lower() for t in project["tasks"])
    files = " ".join(f["filename"].lower() for f in project["files"])
    if not project["files"]:
        gaps.append("Aucun fichier sur le projet.")
    if "swot" not in titles and "swot" not in files:
        gaps.append("Pas encore d’analyse SWOT (tâche ou document).")
    if "finance" not in titles and "budget" not in titles and "finance" not in files:
        gaps.append("Pas de point finance / budget visible.")
    kickoff = next((t for t in project["tasks"] if "kick-off" in t["title"].lower()), None)
    if kickoff and kickoff["file_count"] == 0:
        gaps.append("Le Kick-off n’a pas de notes ni de documents joints.")
    if not project["recent_chat"]:
        gaps.append("La discussion est vide — personne n’a encore écrit.")
    open_tasks = [t for t in project["tasks"] if t["status"] != TaskStatus.DONE.value]
    if not open_tasks:
        gaps.append("Aucune tâche ouverte.")
    return gaps


def _suggestions_for_project(project: dict[str, Any]) -> list[dict[str, str]]:
    suggestions = []
    titles = {t["title"].lower() for t in project["tasks"]}
    catalog = [
        (
            "Préparer 3 idées",
            "Chacun arrive au kick-off avec trois idées de projet ou d’amélioration.",
        ),
        (
            "Brouillon SWOT",
            "Forces, faiblesses, opportunités, menaces — une page suffit.",
        ),
        (
            "Point finance",
            "Budget, engagements, et questions à trancher aujourd’hui.",
        ),
        (
            "Sélection / affinage des projets",
            "Garder, fusionner ou écarter après le SWOT.",
        ),
    ]
    for title, description in catalog:
        if title.lower() not in titles:
            suggestions.append({"title": title, "description": description})
    return suggestions[:4]


def capture_state(session: Session) -> dict[str, Any]:
    projects = list(
        session.scalars(
            select(Project)
            .options(
                selectinload(Project.members).selectinload(ProjectMember.user),
                selectinload(Project.tasks).selectinload(Task.assignee),
                selectinload(Project.tasks).selectinload(Task.files),
                selectinload(Project.tasks).selectinload(Task.comments),
                selectinload(Project.files).selectinload(FileAttachment.uploader),
                selectinload(Project.messages).selectinload(ChatMessage.author),
                selectinload(Project.activity_logs).selectinload(ActivityLog.actor),
                selectinload(Project.events),
            )
            .order_by(Project.id)
        )
    )
    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "projects": [],
    }
    for project in projects:
        tasks = [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "status_label": status_label(task.status),
                "assignee": task.assignee.display_name if task.assignee else None,
                "due_at": _iso(task.due_at),
                "file_count": len(task.files),
                "comment_count": len(task.comments),
            }
            for task in sorted(project.tasks, key=lambda t: (t.status, t.position, t.id))
        ]
        files = [
            {
                "id": item.id,
                "filename": item.original_filename,
                "task_id": item.task_id,
                "uploader": item.uploader.display_name if item.uploader else None,
                "created_at": _iso(item.created_at),
            }
            for item in sorted(project.files, key=lambda f: f.id, reverse=True)[:30]
        ]
        events = [
            {
                "id": event.id,
                "title": event.title,
                "starts_at": _iso(event.starts_at),
                "ends_at": _iso(event.ends_at),
                "all_day": event.all_day,
            }
            for event in sorted(project.events, key=lambda e: (e.starts_at, e.id))
        ]
        chat = [
            {
                "author": msg.author.display_name if msg.author else "?",
                "is_bot": bool(msg.author and msg.author.is_bot),
                "body": msg.body,
                "created_at": _iso(msg.created_at),
            }
            for msg in sorted(project.messages, key=lambda m: m.id)[-40:]
        ]
        activity = [
            {
                "text": describe_activity(entry),
                "action": entry.action,
                "created_at": _iso(entry.created_at),
            }
            for entry in sorted(project.activity_logs, key=lambda a: a.id, reverse=True)[:30]
        ]
        block = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "members": [
                {
                    "email": m.user.email,
                    "name": m.user.display_name,
                    "role": m.role,
                    "is_bot": m.user.is_bot,
                }
                for m in project.members
                if m.user is not None
            ],
            "tasks": tasks,
            "events": events,
            "files": files,
            "recent_chat": chat,
            "recent_activity": activity,
        }
        block["gaps"] = _gaps_for_project(block)
        block["suggestions"] = _suggestions_for_project(block)
        payload["projects"].append(block)
    return payload


def render_markdown(state: dict[str, Any]) -> str:
    lines = [
        "# État Office Agora",
        "",
        f"Généré : {state.get('generated_at', '')}",
        "",
    ]
    if not state["projects"]:
        lines.append("Aucun projet.")
        return "\n".join(lines) + "\n"
    for project in state["projects"]:
        lines.append(f"## {project['name']}")
        if project.get("description"):
            lines.append(project["description"])
        lines.append("")
        humans = [m for m in project["members"] if not m.get("is_bot")]
        bots = [m for m in project["members"] if m.get("is_bot")]
        lines.append(
            "Membres : " + ", ".join(f"{m['name']} ({m['email']})" for m in humans)
        )
        if bots:
            lines.append("Assistants : " + ", ".join(m["name"] for m in bots))
        lines.append("")
        lines.append("### Tâches")
        if not project["tasks"]:
            lines.append("- (aucune)")
        for task in project["tasks"]:
            who = task["assignee"] or "non assigné"
            due = f" · {task['due_at']}" if task["due_at"] else ""
            lines.append(
                f"- [{task['status_label']}] {task['title']} — {who}{due} "
                f"({task['file_count']} fich., {task.get('comment_count', 0)} comm.)"
            )
        lines.append("")
        lines.append("### Agenda")
        if not project.get("events"):
            lines.append("- (aucun événement)")
        for event in project.get("events") or []:
            when = event["starts_at"] or ""
            day = "journée" if event.get("all_day") else when
            lines.append(f"- {event['title']} — {day}")
        lines.append("")
        lines.append("### Documents")
        if not project["files"]:
            lines.append("- (aucun)")
        for item in project["files"]:
            lines.append(f"- {item['filename']}")
        lines.append("")
        lines.append("### Manques")
        for gap in project["gaps"] or ["Rien de criant."]:
            lines.append(f"- {gap}")
        lines.append("")
        lines.append("### Activités proposées")
        for suggestion in project["suggestions"]:
            lines.append(f"- **{suggestion['title']}** — {suggestion['description']}")
        if not project["suggestions"]:
            lines.append("- (rien de plus)")
        lines.append("")
        lines.append("### Discussion récente")
        if not project["recent_chat"]:
            lines.append("- (vide)")
        for msg in project["recent_chat"][-12:]:
            tag = " (bot)" if msg.get("is_bot") else ""
            body = msg["body"].replace("\n", " ")
            if len(body) > 160:
                body = body[:157] + "…"
            lines.append(f"- {msg['author']}{tag}: {body}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_state_file(session: Session, settings: Settings | None = None) -> Path:
    state = capture_state(session)
    markdown = render_markdown(state)
    path = STATE_PATH
    if settings is not None:
        path = settings.database_path.parent / "project-state.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path
