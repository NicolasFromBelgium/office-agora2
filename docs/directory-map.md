# Directory map

Names are stable so humans and agents can find the same things.

| Path | What lives here |
| --- | --- |
| `README.md` | Project intro: what Office Agora is, how to run it. |
| `AGENTS.md` | Rules for coding agents working in this repo. |
| `CONTRIBUTING.md` | How to change the project and open a PR. |
| `.env.example` | Documented environment variables. Copy to `.env`. |
| `.gitignore` | Secrets, virtualenv, caches, uploads, SQLite files. |
| `pyproject.toml` | Package metadata, pytest, ruff, coverage. |
| `Makefile` | Shortcuts: `bootstrap`, `test`, `lint`, `ci`, `run`. |
| `src/agora/` | Application package (models, services, FastAPI app, templates). |
| `alembic/` | SQLAlchemy migrations. |
| `uploads/` | Local file attachments (gitignored contents). |
| `data/` | SQLite database file (gitignored). |
| `tests/` | Automated tests. `test_ci_pipeline.py` is the CI smoke check. |
| `scripts/` | Shell entrypoints for setup and local CI. |
| `config/` | Config file examples. Do not commit real `app.toml`. |
| `docs/` | Human- and agent-readable documentation. |
| `.github/workflows/ci.yml` | Continuous integration: lint + test on push/PR. |
| `.github/workflows/cd.yml` | Continuous delivery: build and GitHub Release on `v*` tags. |
| `deploy/apache/` | Apache snippet for `dogscout.be/office`. |
| `deploy/systemd/` | `office-agora.service` (uvicorn on 127.0.0.1:8088). |
