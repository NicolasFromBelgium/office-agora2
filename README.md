# Office Agora

Lean internal workspace for a small team. Projects, a Kanban board, files, chat, and a quiet activity log. Not a SaaS. Not Jira.

After sign-in you land on a dashboard — there is no marketing homepage behind auth.

[![CI](https://github.com/NicolasFromBelgium/Office-Agora/actions/workflows/ci.yml/badge.svg)](https://github.com/NicolasFromBelgium/Office-Agora/actions/workflows/ci.yml)

## What it is

- Invite-only accounts (no public registration)
- Projects with members (owner vs member)
- Tasks on a board and a list: backlog, todo, doing, done
- Status changes are logged (who, what, when)
- Project chat and presence (short polling / heartbeat)
- Files attached to a project or a task, stored on local disk under `uploads/`

Folder names are listed in [docs/directory-map.md](docs/directory-map.md). Data model and module map: [docs/architecture.md](docs/architecture.md).

## Quick start

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
make run
```

Open **http://127.0.0.1:8000** and sign in.

`make bootstrap` is the same as `./scripts/bootstrap.sh`. The first `make run` also migrates and seeds if the database is empty.

## Seed users

Bootstrap (or first run) creates the **Leyssens Immo SRL** project and these accounts:

| Email | Name |
| --- | --- |
| olivia.leyssens@gmail.com | Olivia Leyssens |
| adrien.leyssens@live.be | Adrien Leyssens |
| leyssens.nicolas@gmail.com | Nicolas Leyssens |
| laurentleyssens1@gmail.com | Laurent Leyssens |

Default password is documented only in `.env.example` as `SEED_DEFAULT_PASSWORD` (example: `ChangeMe!OfficeAgora`). Do not commit a real secret. Change it after first login.

The Leyssens Immo SRL board is seeded with a **Kick-off** meeting today at 13:00 (ideas, finance, SWOT, project selection).

## Environment

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development`, `test`, or `production` |
| `APP_DEBUG` | `true` / `false` |
| `LOG_LEVEL` | `debug`, `info`, `warning`, `error` |
| `SECRET_KEY` | required for any real deployment |
| `DATABASE_PATH` | SQLite file (default `data/agora.db`) |
| `UPLOAD_DIR` | local attachments (default `uploads/`) |
| `MAX_UPLOAD_BYTES` | upload size limit |
| `ALLOWED_UPLOAD_EXTENSIONS` | comma-separated extensions |
| `SEED_DEFAULT_PASSWORD` | password for seeded and invited accounts |
| `HOST` / `PORT` | bind address for `make run` |

`.env` is gitignored. Never commit secrets.

## On the family server

```bash
./scripts/setup-apache-office.sh
```

That starts uvicorn on `127.0.0.1:8088` and proxies **http://dogscout.be/office**.

A PHP reverse proxy is already in `/var/www/dogscout/office/` so the path works without extra Apache modules. The `office-agora` user systemd service keeps the app running.

## Tests

```bash
make test
make ci
```

`make ci` is ruff + pytest with coverage, the same checks GitHub Actions runs.

## License

MIT. See [LICENSE](LICENSE).
