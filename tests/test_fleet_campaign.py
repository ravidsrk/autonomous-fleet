"""Tests for fleet-outcome parsing and campaign edge evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.fleet_outcome import (  # noqa: E402
    eval_edge,
    parse_readiness,
    pick_next_node,
    validate_outcome,
)


DOC_SYNC_OUTCOME = {
    "mission": "doc-sync",
    "status": "done",
    "repo": "/tmp/repo",
    "base_branch": "fleet/base",
    "prs_merged": 1,
    "metrics": {"drift_open": 0, "code_bug_findings": 0},
    "deferred_missions": [],
}


def test_eval_always():
    assert eval_edge("always", DOC_SYNC_OUTCOME) is True


def test_eval_code_bug_branch_skip():
    assert eval_edge("code_bug_findings > 0", DOC_SYNC_OUTCOME) is False
    assert eval_edge("code_bug_findings == 0", DOC_SYNC_OUTCOME) is True


def test_eval_deferred_contains():
    outcome = {
        **DOC_SYNC_OUTCOME,
        "deferred_missions": [{"id": "bug-batch", "reason": "x", "blocker": None}],
    }
    assert eval_edge("deferred_missions contains bug-batch", outcome) is True
    assert eval_edge("deferred_missions contains test-coverage", outcome) is False


def test_pick_next_docs_if_bugs_skips_bug_batch():
    campaign = {
        "edges": {
            "docs": [
                {"to": "bugs", "if": "code_bug_findings > 0"},
                {"to": "tests", "if": "always"},
            ],
            "bugs": [{"to": "tests", "if": "always"}],
            "tests": [],
        }
    }
    assert pick_next_node(campaign, "docs", DOC_SYNC_OUTCOME) == "tests"


def test_pick_next_docs_if_bugs_includes_bug_batch():
    outcome = {
        **DOC_SYNC_OUTCOME,
        "metrics": {"drift_open": 0, "code_bug_findings": 2},
    }
    campaign = {
        "edges": {
            "docs": [
                {"to": "bugs", "if": "code_bug_findings > 0"},
                {"to": "tests", "if": "always"},
            ],
        }
    }
    assert pick_next_node(campaign, "docs", outcome) == "bugs"


def test_validate_outcome_requires_metrics():
    errors = validate_outcome({"mission": "doc-sync", "status": "done"})
    assert any("metrics" in e for e in errors)


def test_parse_fixture_readiness(tmp_path: Path):
    doc = tmp_path / "doc-sync-readiness.md"
    doc.write_text(
        """---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: /x
  base_branch: fleet/b
  prs_merged: 0
  metrics:
    drift_open: 0
    code_bug_findings: 0
  deferred_missions: []
---
# body
""",
        encoding="utf-8",
    )
    outcome = parse_readiness(doc)
    assert outcome["mission"] == "doc-sync"
    assert validate_outcome(outcome, doc) == []