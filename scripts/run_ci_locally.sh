#!/usr/bin/env bash
# Same checks GitHub Actions CI runs: lint + tests.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

"$PYTHON" -m ruff check src tests
"$PYTHON" -m pytest --cov=agora --cov-report=term-missing
echo "Local CI checks passed."
