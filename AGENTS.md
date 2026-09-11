# Agent instructions

This repository is **Office Agora**, a lean internal project workspace.

## Before changing code

1. Read `docs/directory-map.md` and `docs/architecture.md`. Put files in those folders; do not invent parallel trees.
2. Keep secrets out of git. Use `.env.example` as the contract; put real values only in `.env`.
3. Run `make ci` before you finish. CI on GitHub runs the same checks.

## Where to edit

- Application behavior: `src/agora/`
- Tests: `tests/` (keep `tests/test_ci_pipeline.py` as the pipeline smoke test)
- GitHub Actions: `.github/workflows/`
- Human docs: `README.md` and `docs/`

## Conventions

- Python 3.11+, package layout under `src/agora`
- No extra runtime services (no Redis, Postgres, or Docker for local run)
- Test names should say what they prove
- Prefer small, named modules over a single large file
- Server-rendered pages first (Jinja2 + HTMX). Keep custom JS small.
- UI strings live in templates so a later FR translation pass can wrap them.
