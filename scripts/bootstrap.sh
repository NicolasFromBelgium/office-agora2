#!/usr/bin/env bash
# Create a local virtualenv, install the project, migrate, and seed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

mkdir -p data uploads
python -m agora.seed

echo
echo "Environment is ready."
echo "  source .venv/bin/activate"
echo "  make run     # web app at http://127.0.0.1:8000"
echo "  make test"
echo
echo "Seed users sign in with SEED_DEFAULT_PASSWORD from .env.example"
echo "  (default: ChangeMe!OfficeAgora — change it after first login)."
