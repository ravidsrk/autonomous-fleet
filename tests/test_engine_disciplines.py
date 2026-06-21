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


CONTRADICTION_MARKERS = (
    "IGNORE the preceding",
    "IGNORE THE PRECEDING",
    "OVERRIDE",
    "DISREGARD",
    "ignore the above",
)


def assert_no_contradiction_markers(text: str) -> None:
    for marker in CONTRADICTION_MARKERS:
        assert marker not in text


def test_self_orientation_defines_reference_input_as_read_only() -> None:
    text = read_engine()
    orientation = section(
        text,
        "SELF-ORIENTATION",
        "ORCHESTRATOR DIRECTIVE",
    )
    orientation_flat = squash(orientation)

    assert "REFERENCE-INPUT" in orientation
    assert "TARGET vs REFERENCE dual-path" in orientation
    assert "reference repo/path" in orientation
    assert "read-only" in orientation
    assert "adapts FROM" in orientation
    assert "NEVER write" in orientation
    assert "TARGET" in orientation
    assert "open a PR against it" in orientation
    assert (
        "treat it as read-only material the fleet reads and adapts FROM; NEVER write to it, "
        "make it a TARGET, or open a PR against it."
    ) in orientation_flat
    assert "IS a writable TARGET" not in orientation
    assert "SHOULD write to it" not in orientation
    assert_no_contradiction_markers(orientation)


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
    assert (
        "A green test/validator suite is NECESSARY BUT NOT SUFFICIENT. NEVER terminate "
        "(`GOAL_COMPLETE` / `DONE`) on green checkmarks alone. Verify the real end-to-end "
        "RESULT STATE: query the actual result, not exit codes"
    ) in squash(gate)
    assert "you MAY terminate" not in gate
    assert "do NOT bother to verify" not in gate
    assert_no_contradiction_markers(gate)


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
    assert (
        "Do not add newly discovered ideas, optional features, refactors, or nice-to-haves "
        "to the current build."
    ) in squash(gate)
    assert "You MAY add newly discovered ideas" not in gate
    assert_no_contradiction_markers(gate)


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
    assert "coordinator must not pick a default and must not ship one variant" in gate
    assert "stop the affected task wave, and HALT for the human" in gate
    assert "do NOT HALT" not in gate
    assert "SHOULD pick a default" not in gate
    assert_no_contradiction_markers(gate)


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
    research_flat = squash(research)
    assert "record findings in `docs/research-notes.md`, then discard it" in research_flat
    assert "is not kept as build output" in research_flat
    assert "SHOULD be kept as build output" not in research
    assert "do NOT discard" not in research
    assert_no_contradiction_markers(research)


def test_context_handoff_proactive_rollup_is_not_duplicated() -> None:
    text = read_engine()
    handoff = section(
        text,
        "CONTEXT HANDOFF",
        "PLAN/DAG VALIDATION GATE",
    )

    assert text.count("Carry forward the") == 1
    assert handoff.count("PROACTIVE (don't wait for the cliff)") == 1
    assert (
        "Carry forward the rolling summary + the next ready wave, not the full history."
    ) in squash(handoff)
    assert "Carry forward the full history" not in handoff
    assert "do NOT roll up or summarize" not in handoff
    assert_no_contradiction_markers(handoff)


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
    assert "IGNORE those guard clauses" not in pipeline
    assert "remove any worktree unconditionally" not in pipeline
    assert_no_contradiction_markers(autonomy)
    assert_no_contradiction_markers(handoff)
    assert_no_contradiction_markers(pipeline)


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
    assert (
        "A feature/fix task cannot set REVIEWED and cannot be done unless it includes a "
        "regression-catching test that would FAIL if the repaired behavior broke again."
    ) in pipeline_flat
    assert "MAY set REVIEWED" not in pipeline
    assert "no test at all" not in pipeline
    assert "return PASS regardless" not in pipeline
    assert_no_contradiction_markers(pipeline)


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
    assert (
        "On FAIL, block later waves and repair the merge pipeline before any further SHIP step."
    ) in squash(pipeline)
    assert "do NOT block later waves" not in pipeline
    assert "keep shipping" not in pipeline
    assert_no_contradiction_markers(pipeline)


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
    assert (
        "hard-gated on a file-tracked `ROTATION_CONFIRMED=yes` boolean that was set by a human"
    ) in hygiene_flat
    assert "does not scrub history yet" in hygiene_flat
    assert "PROCEEDS to scrub history immediately" not in hygiene
    assert "scrub anyway" not in hygiene
    assert_no_contradiction_markers(hygiene)
