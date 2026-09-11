"""Shared enumerations and activity action names."""

from __future__ import annotations

from enum import StrEnum


class TaskStatus(StrEnum):
    BACKLOG = "backlog"
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


class MemberRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


TASK_STATUSES: tuple[TaskStatus, ...] = (
    TaskStatus.BACKLOG,
    TaskStatus.TODO,
    TaskStatus.DOING,
    TaskStatus.DONE,
)

STATUS_LABELS = {
    TaskStatus.BACKLOG: "À planifier",
    TaskStatus.TODO: "À faire",
    TaskStatus.DOING: "En cours",
    TaskStatus.DONE: "Terminé",
}


def status_label(value: str) -> str:
    try:
        return STATUS_LABELS[TaskStatus(value)]
    except ValueError:
        return value


class Action:
    PROJECT_CREATED = "project.created"
    MEMBER_ADDED = "member.added"
    TASK_CREATED = "task.created"
    TASK_STATUS_CHANGED = "task.status_changed"
    TASK_ASSIGNED = "task.assigned"
    FILE_UPLOADED = "file.uploaded"
    FILE_DELETED = "file.deleted"
    TASK_COMMENTED = "task.commented"
    TASK_DELETED = "task.deleted"
    COMMENT_DELETED = "comment.deleted"
    EVENT_CREATED = "event.created"
    EVENT_UPDATED = "event.updated"
    EVENT_DELETED = "event.deleted"
