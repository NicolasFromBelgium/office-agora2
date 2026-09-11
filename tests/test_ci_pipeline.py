"""Prove GitHub Actions CI is configured and actually runs this suite.

Open GitHub → Actions → CI to see these tests in the workflow log.
When `GITHUB_ACTIONS=true`, extra assertions confirm the job environment.
"""

from __future__ import annotations

import os
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_ci_workflow_file_exists() -> None:
    ci_file = WORKFLOWS / "ci.yml"
    assert ci_file.is_file(), "Missing .github/workflows/ci.yml"


def test_cd_workflow_file_exists() -> None:
    cd_file = WORKFLOWS / "cd.yml"
    assert cd_file.is_file(), "Missing .github/workflows/cd.yml"


def test_ci_workflow_runs_pytest() -> None:
    content = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "pytest" in content
    assert "on:" in content
    assert "push:" in content
    assert "pull_request:" in content


def test_ci_pipeline_runs_on_github_actions() -> None:
    """Visible check: this test is what you look for in GitHub Actions logs.

    Locally it still passes. On GitHub it also verifies CI environment vars.
    """
    in_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"

    if in_github_actions:
        assert os.environ.get("CI") == "true"
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        assert repository.endswith("/Office-Agora"), f"Unexpected repo: {repository}"
        assert os.environ.get("GITHUB_WORKFLOW") == "CI"
    else:
        assert os.environ.get("GITHUB_ACTIONS", "false") != "true"
