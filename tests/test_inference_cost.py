"""Tests for the inference-cost mission fleet-outcome registration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.fleet_outcome import MISSION_METRICS, validate_outcome  # noqa: E402
from lib.mission_registry import progress_path, readiness_path  # noqa: E402


INFERENCE_COST_OUTCOME = {
    "mission": "inference-cost",
    "status": "done",
    "repo": "/tmp/repo",
    "base_branch": "fleet/base",
    "prs_merged": 2,
    "metrics": {
        "cost_regressed": False,
        "quality_regressed": False,
        "levers_open": 0,
    },
    "deferred_missions": [],
}


def test_inference_cost_outcome_validates_with_registered_metrics():
    assert MISSION_METRICS["inference-cost"] == frozenset(
        {"cost_regressed", "quality_regressed", "levers_open"}
    )
    assert readiness_path("inference-cost") == "docs/inference-cost-readiness.md"
    assert progress_path("inference-cost") == "docs/inference-cost-progress.md"
    assert validate_outcome(INFERENCE_COST_OUTCOME) == []


def test_inference_cost_rejects_bad_metric_type():
    outcome = {
        **INFERENCE_COST_OUTCOME,
        "metrics": {
            **INFERENCE_COST_OUTCOME["metrics"],
            "quality_regressed": "false",
        },
    }

    errors = validate_outcome(outcome)

    assert not any("unknown mission" in error for error in errors)
    assert any(
        "metric 'quality_regressed' must be numeric or bool" in error
        for error in errors
    )
