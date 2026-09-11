# Development

## First-time setup

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
```

This creates `.venv`, installs the package plus test tools, copies `.env.example` to `.env`, runs migrations, and seeds the Leyssens project.

## Everyday commands

```bash
make test      # pytest
make lint      # ruff
make ci        # lint + tests (same as GitHub Actions)
make run       # uvicorn — Office Agora at http://127.0.0.1:8000
```

`make run` also migrates and seeds on startup if needed.

## Environment

Edit `.env`. Never commit it. The keys are defined in `.env.example`.

Important keys:

- `SECRET_KEY` — replace `change-me` before any real deployment
- `DATABASE_PATH` — SQLite file (default `data/agora.db`)
- `UPLOAD_DIR` — local attachments (default `uploads/`)
- `MAX_UPLOAD_BYTES` / `ALLOWED_UPLOAD_EXTENSIONS` — file limits
- `SEED_DEFAULT_PASSWORD` — invite-only accounts created by seed/invite

## Seed users

After bootstrap, sign in with any of:

- olivia.leyssens@gmail.com
- adrien.leyssens@live.be
- leyssens.nicolas@gmail.com
- laurentleyssens1@gmail.com

Password: the value of `SEED_DEFAULT_PASSWORD` (documented in `.env.example` only).

## CI on GitHub

Pushes to `main` and pull requests run `.github/workflows/ci.yml`.

To confirm it worked:

1. Open Actions
2. Open the **CI** workflow run
3. Open **Run test suite**
4. Find `test_ci_pipeline_runs_on_github_actions PASSED`

## CD

Push a version tag to build artifacts and create a GitHub Release:

```bash
git tag v0.1.0
git push origin v0.1.0
```
