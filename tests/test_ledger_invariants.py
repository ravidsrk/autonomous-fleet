"""Tests for optional fleet-outcome task ledger invariants."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.fleet_outcome import validate_outcome  # noqa: E402


BASE_OUTCOME = {
    "mission": "doc-sync",
    "status": "done",
    "repo": "/tmp/repo",
    "base_branch": "fleet/base",
    "prs_merged": 1,
    "metrics": {"drift_open": 0, "code_bug_findings": 0},
    "deferred_missions": [],
}


def _errors_for_task(task: dict[str, object]) -> list[str]:
    return validate_outcome({**BASE_OUTCOME, "tasks": [task]})


def test_merged_task_must_have_built() -> None:
    errors = _errors_for_task(
        {
            "id": "t1",
            "built": False,
            "pr_open": True,
            "reviewed": True,
            "merged": True,
            "wt_clean": True,
        }
    )

    assert any("t1" in error and "never built" in error for error in errors), errors


def test_merged_task_requires_clean_worktree() -> None:
    errors = _errors_for_task(
        {
            "id": "t2",
            "built": True,
            "pr_open": True,
            "reviewed": True,
            "merged": True,
            "wt_clean": False,
        }
    )

    assert any("worktree not clean" in error for error in errors), errors


def test_reviewed_task_requires_open_pr() -> None:
    errors = _errors_for_task(
        {
            "id": "t3",
            "built": True,
            "pr_open": False,
            "reviewed": True,
            "merged": False,
            "wt_clean": True,
        }
    )

    assert any("reviewed before PR" in error for error in errors), errors


def test_consistent_task_row_has_no_contradiction_errors() -> None:
    errors = _errors_for_task(
        {
            "id": "t4",
            "built": True,
            "pr_open": True,
            "reviewed": True,
            "merged": True,
            "wt_clean": True,
        }
    )

    assert errors == []


def test_missing_tasks_key_preserves_existing_outcome_behavior() -> None:
    assert validate_outcome(BASE_OUTCOME) == []
