"""Weekly élan: a light score so the team wants to move work forward."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agora.constants import Action, TaskStatus
from agora.models import ActivityLog, ChatMessage, ProjectMember, Task, User
from agora.services.presence import is_online

POINTS_CREATED = 3
POINTS_MOVED = 1
POINTS_DONE = 5
POINTS_FILE = 2
POINTS_CHAT = 1


@dataclass
class MemberScore:
    user: User
    points: int = 0
    created: int = 0
    completed: int = 0
    messages: int = 0
    online: bool = False
    doing_titles: list[str] = field(default_factory=list)

    @property
    def initial(self) -> str:
        return self.user.initial


def _week_start(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now - timedelta(days=7)


def member_scores(
    session: Session,
    *,
    project_id: int,
    timeout_seconds: int,
    now: datetime | None = None,
) -> list[MemberScore]:
    members = list(
        session.scalars(
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .options(selectinload(ProjectMember.user))
        )
    )
    by_id: dict[int, MemberScore] = {
        m.user_id: MemberScore(user=m.user, online=is_online(m.user, timeout_seconds))
        for m in members
        if m.user is not None and not m.user.is_bot
    }
    if not by_id:
        return []

    since = _week_start(now or datetime.now(UTC))
    logs = list(
        session.scalars(
            select(ActivityLog).where(
                ActivityLog.project_id == project_id,
                ActivityLog.created_at >= since,
            )
        )
    )
    for entry in logs:
        score = by_id.get(entry.actor_id)
        if score is None:
            continue
        if entry.action == Action.TASK_CREATED:
            score.created += 1
            score.points += POINTS_CREATED
        elif entry.action == Action.TASK_STATUS_CHANGED:
            details = entry.details or {}
            if details.get("to") == TaskStatus.DONE.value:
                score.completed += 1
                score.points += POINTS_DONE
            else:
                score.points += POINTS_MOVED
        elif entry.action == Action.FILE_UPLOADED:
            score.points += POINTS_FILE

    chats = session.scalars(
        select(ChatMessage.author_id).where(
            ChatMessage.project_id == project_id,
            ChatMessage.created_at >= since,
        )
    )
    for author_id in chats:
        score = by_id.get(author_id)
        if score is None:
            continue
        score.messages += 1
        score.points += POINTS_CHAT

    doing = session.scalars(
        select(Task).where(
            Task.project_id == project_id,
            Task.status == TaskStatus.DOING.value,
            Task.assignee_id.is_not(None),
        )
    )
    for task in doing:
        score = by_id.get(task.assignee_id)  # type: ignore[arg-type]
        if score is not None:
            score.doing_titles.append(task.title)

    ranked = sorted(by_id.values(), key=lambda item: (-item.points, item.user.display_name))
    return ranked


def nudge(scores: list[MemberScore], current_user: User) -> str:
    if not scores:
        return "Créez une tâche pour lancer l’élan de l’équipe."
    leader = scores[0]
    mine = next((item for item in scores if item.user.id == current_user.id), None)
    if mine is None:
        return "Rejoignez le mouvement : une tâche, un message, un fichier."
    if leader.user.id == current_user.id:
        if leader.points == 0:
            return "Personne n’a encore marqué d’élan. Créez ou terminez une tâche."
        return "Vous menez l’élan cette semaine. Gardez le rythme."
    return (
        f"{leader.user.display_name.split()[0]} mène avec {leader.points} élan. "
        "Créez ou terminez une tâche pour rattraper."
    )
