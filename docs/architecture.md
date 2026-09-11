# Office Agora — module map and data model

Internal project workspace. Server-rendered FastAPI, SQLite, no extra services.

UI strings live in Jinja templates (and a few flash messages in routes) so a later FR pass can wrap them with gettext without moving structure.

## Package

Application code is the `agora` package under `src/agora/` (forked from the template's `src/app`).

```
src/agora/
  __init__.py          version
  __main__.py          `python -m agora` → uvicorn
  health.py            stable CI/health surface
  settings.py          env + .env
  db.py                engine, sessions, migrations
  models.py            SQLAlchemy models
  seed.py              Leyssens users, project, sample tasks
  constants.py         statuses, roles, activity actions
  services/            domain operations (no HTTP)
    passwords.py
    activity.py
    files.py
    comments.py
    notifications.py
    likes.py
    thumbs.py
    avatars.py
    dates.py         Brussels due dates / event spans
    events.py        calendar events
    agenda.py        month grid + day items
    projects.py
    tasks.py
    presence.py
  web/
    app.py             FastAPI factory + lifespan (migrate + seed)
    deps.py            auth, membership, db session
    templating.py      Jinja2 + render helper
    routes/
      auth.py          login / logout
      dashboard.py     / lands on last board; /home account
      profile.py       avatar upload / thumb
      projects.py      create, board, list, activity, invite
      tasks.py         create, status, assign, due date, detail
      agenda.py        month agenda, event CRUD
      comments.py      task comments
      notifications.py assignment bell
      likes.py         task and comment likes
      files.py         upload / download / delete
      chat.py          messages + compose
      presence.py      heartbeat + online partial
  templates/           Jinja2 (base shell, dashboard, project tabs)
  static/app.css       kanban equal-height columns, focus
```

Alembic lives at repo root (`alembic/`, `alembic.ini`). Uploads go to `uploads/` (gitignored). SQLite file path comes from `DATABASE_PATH`.

## Request flow

1. Unauthenticated users only see `/login` and `/health`.
2. Session cookie (`agora_session`) after POST `/login`.
3. `/` is the dashboard (current user, online, continue last project, project list, create).
4. Opening a project records `User.last_project_id` and shows Board | List | Agenda | Files | Chat | Activity.
5. Task status changes (drag or click) POST to `/projects/{id}/tasks/{tid}/status` and write an `activity_logs` row.
6. Presence: authenticated pages POST `/presence/heartbeat` on an interval; online = `last_seen_at` within `PRESENCE_TIMEOUT_SECONDS`. Chat refreshes by short polling.

## Data model

```
users
  id, email (unique), display_name, password_hash, is_active
  avatar_name (profile photo filename, nullable)
  last_seen_at, last_project_id → projects.id (SET NULL)
  created_at

projects
  id, name, description, owner_id → users.id
  created_at, updated_at

project_members
  id, project_id → projects.id, user_id → users.id
  role: owner | member
  unique (project_id, user_id)
  created_at

tasks
  id, project_id → projects.id
  title, description
  status: backlog | todo | doing | done
  assignee_id → users.id (nullable)
  position (order inside a column)
  created_by_id → users.id
  due_at (nullable, Europe/Brussels)
  created_at, updated_at

calendar_events
  id, project_id → projects.id
  title, description
  starts_at, ends_at
  all_day
  created_by_id → users.id
  created_at, updated_at

task_comments
  id, task_id → tasks.id
  author_id → users.id
  body
  created_at

activity_logs
  id, project_id → projects.id
  task_id → tasks.id (nullable, for task-level history)
  actor_id → users.id
  action (e.g. task.status_changed)
  details (JSON)
  created_at

chat_messages
  id, project_id → projects.id
  author_id → users.id
  body
  created_at

file_attachments
  id, project_id → projects.id
  task_id → tasks.id (nullable)
  uploader_id → users.id
  original_filename, stored_name, content_type, size_bytes
  created_at

notifications
  id, user_id → users.id, actor_id → users.id
  project_id → projects.id, task_id → tasks.id (SET NULL)
  kind (e.g. task.assigned), title, read_at, created_at

likes
  id, user_id → users.id
  task_id → tasks.id (nullable) OR comment_id → task_comments.id (nullable)
  unique (user_id, task_id), unique (user_id, comment_id)
  created_at
```

Disk path for a file: `{UPLOAD_DIR}/{project_id}/{stored_name}`.
Thumbnail (128×128 JPEG): `{UPLOAD_DIR}/{project_id}/.thumbs/{stem}.jpg`.
Profile photo: `{UPLOAD_DIR}/avatars/{user_id}/{stored_name}` plus `thumb.jpg`.

## AuthZ (v1)

- Invite-only: no public registration. Owners add members by email (creates a user with `SEED_DEFAULT_PASSWORD` if missing).
- Project pages require membership. Owner vs member: only owners invite.
- All members may create tasks and events, set due dates, change status, comment, chat, upload, and delete tasks, comments, files, and events.
- Assigning a task to someone else creates a notification. A header bell shows a red dot while unread.
- Members may like a task or a comment (toggle). Likes are silent: no activity row, no bell.

## Seed (idempotent)

Project **Leyssens Immo SRL**, members:

| Email | Display name |
| --- | --- |
| olivia.leyssens@gmail.com | Olivia Leyssens |
| adrien.leyssens@live.be | Adrien Leyssens |
| leyssens.nicolas@gmail.com | Nicolas Leyssens |
| laurentleyssens1@gmail.com | Laurent Leyssens |

Default password is only documented in `.env.example`. Seeded work: Kick-off meeting today at 13:00 (idées, finance, SWOT, projets). The UI is French by default.
