"""Tests for the anti-inflation e2e completion gate."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.fleet_outcome import validate_outcome  # noqa: E402


COMPLETION_OUTCOME = {
    "mission": "take-product-to-completion",
    "status": "done",
    "repo": "/tmp/repo",
    "base_branch": "fleet/base",
    "prs_merged": 1,
    "metrics": {
        "in_items_open": 0,
        "roadmap_count": 0,
        "stubs_remaining": 0,
        "e2e_verified": True,
    },
    "deferred_missions": [],
}


DOC_SYNC_OUTCOME = {
    "mission": "doc-sync",
    "status": "done",
    "repo": "/tmp/repo",
    "base_branch": "fleet/base",
    "prs_merged": 1,
    "metrics": {"drift_open": 0, "code_bug_findings": 0},
    "deferred_missions": [],
}


def test_completion_done_rejects_false_e2e_verified():
    outcome = {
        **COMPLETION_OUTCOME,
        "metrics": {**COMPLETION_OUTCOME["metrics"], "e2e_verified": False},
    }

    errors = validate_outcome(outcome)

    assert any("cannot be done without end-to-end verification" in e for e in errors)


def test_completion_done_rejects_absent_e2e_verified():
    metrics = {
        k: v for k, v in COMPLETION_OUTCOME["metrics"].items() if k != "e2e_verified"
    }
    outcome = {**COMPLETION_OUTCOME, "metrics": metrics}

    errors = validate_outcome(outcome)

    assert any("cannot be done without end-to-end verification" in e for e in errors)


def test_completion_done_accepts_true_e2e_verified():
    assert validate_outcome(COMPLETION_OUTCOME) == []


def test_non_completion_done_has_no_e2e_requirement():
    assert validate_outcome(DOC_SYNC_OUTCOME) == []


def test_degraded_no_scm_auth_incompatible_with_done() -> None:
    """Issue #97: an unauthenticated-gh run (local-merge detour) must not
    report an undifferentiated done."""
    outcome = {**DOC_SYNC_OUTCOME, "degraded_mode": "no_scm_auth", "status": "done"}
    errors = validate_outcome(outcome)
    assert any("no_scm_auth" in e for e in errors)

    outcome = {**DOC_SYNC_OUTCOME, "degraded_mode": "no_scm_auth", "status": "partial"}
    assert not any("no_scm_auth" in e for e in validate_outcome(outcome))


def test_degraded_mode_must_be_string() -> None:
    outcome = {**DOC_SYNC_OUTCOME, "degraded_mode": 7}
    assert any("degraded_mode must be a string" in e for e in validate_outcome(outcome))


def test_unknown_degraded_mode_rejected() -> None:
    """Closed enum (codex on #119): a typo'd mode must not slip past the gate."""
    outcome = {**DOC_SYNC_OUTCOME, "degraded_mode": "no_scm_authh", "status": "done"}
    errors = validate_outcome(outcome)
    assert any("unknown degraded_mode" in e for e in errors)
