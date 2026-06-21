"""Structural tests for engine-level discipline rails."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "skills" / "autonomous-fleet-core" / "references" / "engine.md"


def read_engine() -> str:
    return ENGINE.read_text(encoding="utf-8")


def section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading)
    end = text.index(next_heading, start)
    return text[start:end]


def squash(text: str) -> str:
    return " ".join(text.split())


def test_result_state_gate_rejects_green_checkmark_inflation() -> None:
    text = read_engine()
    gate = section(
        text,
        "RESULT-STATE TERMINATION GATE",
        "SIGNAL RECONCILIATION",
    )

    assert "NECESSARY BUT NOT SUFFICIENT" in gate
    assert "NEVER terminate" in gate
    assert "`GOAL_COMPLETE` / `DONE`" in gate
    assert "query the actual result, not exit codes" in gate
    assert "e2e_verified" in gate
    assert "docs/secure-ship-e2e.md" in gate


def test_frozen_scope_boundary_caps_run_scope() -> None:
    text = read_engine()
    gate = section(
        text,
        "FROZEN SCOPE BOUNDARY",
        "WORKER PLACEMENT",
    )

    assert "caps the WHOLE run's" in gate
    assert "current build" in gate
    assert "DECISIONS.md" in gate
    assert "roadmap" in gate
    assert "Reviewers FAIL any PR adding out-of-boundary work" in gate


def test_wt_clean_is_tracked_across_pipeline_handoff_and_terminate() -> None:
    text = read_engine()
    autonomy = section(
        text,
        "AUTONOMY ENFORCEMENT",
        "RESULT-STATE TERMINATION GATE",
    )
    handoff = section(
        text,
        "CONTEXT HANDOFF",
        "PLAN/DAG VALIDATION GATE",
    )
    pipeline = section(
        text,
        "PR-PER-TASK PIPELINE",
        "TRUST BOUNDARIES",
    )
    pipeline_flat = squash(pipeline)

    assert "WT_CLEAN=true" in autonomy
    assert "merged but uncleaned task" in autonomy
    assert "NOT terminal" in autonomy

    assert "HANDOFF CARRIES" in handoff
    assert "WT path or environment id" in handoff
    assert "WT_CLEAN" in handoff

    assert "TASK ROW" in pipeline
    assert "WT_CLEAN" in pipeline
    assert "verify MERGED + branch-deleted FIRST" in pipeline
    assert "NEVER remove the active worktree" in pipeline_flat
    assert "NEVER remove a worktree whose branch is unmerged" in pipeline_flat
    assert "NEVER remove a worktree with uncommitted changes" in pipeline_flat
    assert "try X, fall back to Y" in pipeline
    assert "T_FINAL WORKTREE-ORPHAN SWEEP" in pipeline
    assert "orphan worktree" in pipeline
