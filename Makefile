.PHONY: bootstrap test lint ci run brief clean

VENV_PYTHON := $(wildcard .venv/bin/python)
PYTHON ?= $(if $(VENV_PYTHON),$(VENV_PYTHON),python3)

bootstrap:
	./scripts/bootstrap.sh

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

ci:
	./scripts/run_ci_locally.sh

run:
	$(PYTHON) -m agora

brief:
	$(PYTHON) -m agora.brief

clean:
	rm -rf .venv dist build .pytest_cache .ruff_cache .coverage htmlcov reports
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
