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


def test_self_orientation_defines_reference_input_as_read_only() -> None:
    text = read_engine()
    orientation = section(
        text,
        "SELF-ORIENTATION",
        "ORCHESTRATOR DIRECTIVE",
    )

    assert "REFERENCE-INPUT" in orientation
    assert "TARGET vs REFERENCE dual-path" in orientation
    assert "reference repo/path" in orientation
    assert "read-only" in orientation
    assert "adapts FROM" in orientation
    assert "NEVER write" in orientation
    assert "TARGET" in orientation
    assert "open a PR against it" in orientation


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


def test_draft_both_and_gate_is_a_human_gated_decision_outcome() -> None:
    text = read_engine()
    gate = section(
        text,
        "COORDINATOR BEHAVIORS",
        "AUTONOMY ENFORCEMENT",
    )

    assert "draft-both-and-gate" in gate
    assert "draft both variants" in gate
    assert "DECISIONS.md" in gate
    assert "HALT for the human" in gate
    assert "third decision outcome beside proceed and defer" in gate
    assert "must not fabricate" in gate


def test_research_discipline_allows_throwaway_spike() -> None:
    text = read_engine()
    research = section(
        text,
        "RESEARCH DISCIPLINE",
        "MODEL & COST ROUTING",
    )

    assert "SPIKE" in research
    assert "load-bearing unknown" in research
    assert "ONE throwaway proof" in research
    assert "before the freeze" in research
    assert "record findings" in research
    assert "discard" in research
    assert "not documentation lookup" in research


def test_context_handoff_proactive_rollup_is_not_duplicated() -> None:
    text = read_engine()
    handoff = section(
        text,
        "CONTEXT HANDOFF",
        "PLAN/DAG VALIDATION GATE",
    )

    assert text.count("Carry forward the") == 1
    assert handoff.count("PROACTIVE (don't wait for the cliff)") == 1


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


def test_feature_fix_done_requires_regression_catching_test() -> None:
    text = read_engine()
    pipeline = section(
        text,
        "PR-PER-TASK PIPELINE",
        "TRUST BOUNDARIES",
    )
    pipeline_flat = squash(pipeline)

    assert "DONE CONDITION: regression-catching test" in pipeline
    assert "feature/fix task cannot set REVIEWED" in pipeline_flat
    assert "cannot be done" in pipeline_flat
    assert "regression-catching test" in pipeline
    assert "would FAIL if the repaired behavior broke again" in pipeline_flat
    assert "build-blind reviewer explicitly asserts" in pipeline_flat
    assert "not coverage padding" in pipeline_flat


def test_first_merge_spot_check_blocks_later_waves_on_fail() -> None:
    text = read_engine()
    pipeline = section(
        text,
        "PR-PER-TASK PIPELINE",
        "TRUST BOUNDARIES",
    )

    assert "FIRST-MERGE SPOT-CHECK" in pipeline
    assert "After the first task merges into BASE" in pipeline
    assert "preserved the branch commit count" in pipeline
    assert "authored by MAINTAINER" in pipeline
    assert "no commit message contains agent/tool trailers" in pipeline
    assert "PR branch is deleted" in pipeline
    assert "secret-scan ran" in pipeline
    assert "FIRST_MERGE_SPOT_CHECK=PASS or FAIL" in pipeline
    assert "block later waves" in pipeline


def test_secret_scrub_is_gated_on_human_confirmed_rotation() -> None:
    text = read_engine()
    hygiene = section(
        text,
        "ROTATE-BEFORE-SCRUB PRECONDITION",
        "COMMIT & AUTHORSHIP",
    )
    hygiene_flat = squash(hygiene)

    assert "ROTATE-BEFORE-SCRUB PRECONDITION" in hygiene
    assert "git-history purge" in hygiene
    assert "repository secret-scrub" in hygiene
    assert "file-tracked `ROTATION_CONFIRMED=yes`" in hygiene
    assert "set by a human" in hygiene
    assert "does not scrub history yet" in hygiene
    assert "false safety" in hygiene
    assert "already-committed secret is already compromised" in hygiene_flat
