"""Structural rails for adversarial-review-and-fix remediation lanes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "adversarial-review-and-fix" / "SKILL.md"


def read_skill() -> str:
    return SKILL.read_text(encoding="utf-8")


def section(text: str, heading: str, next_heading: str | None = None) -> str:
    start = text.index(heading)
    if next_heading is None:
        return text[start:]
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


def test_three_lane_remediation_section_has_all_lanes() -> None:
    text = read_skill()
    lanes = section(text, "THREE-LANE REMEDIATION", "ROLE PIPELINE")
    lanes_flat = squash(lanes)

    # Engine reference present — LANE PATTERN now lives in engine.md.
    assert "engine.md" in lanes
    assert "LANE PATTERN" in lanes
    # Mission-specific ledger flags still recorded per lane.
    assert "Lane A" in lanes
    assert "Lane B" in lanes
    assert "Lane 0" in lanes
    assert "`MERGED=true`" in lanes
    assert "`HUMAN_GATED=true`" in lanes
    assert "`CODE_CLOSED=true, OPS_QUEUED=true`" in lanes
    assert "`DECISIONS.md`" in lanes
    assert "Never auto-merge" in lanes
    assert "`HUMAN_ACTION_REQUIRED:<finding-id>`" in lanes
    assert "`docs/arch-ops-actions.md`" in lanes
    assert "`lane: A|B|0`" in lanes
    assert "auto-merge it without a human gate" not in lanes
    assert "SHOULD execute the human-only action itself" not in lanes
    assert "without waiting" not in lanes
    assert_no_contradiction_markers(lanes)


def test_evid_flag_is_ledger_and_fix_loop_gate() -> None:
    text = read_skill()
    ledger = section(text, "LEDGER", "TASK STRUCTURE")
    ledger_flat = squash(ledger)
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")

    # Engine reference for EVID definition.
    assert "engine.md" in ledger
    assert "FROZEN-ARTIFACT CLOSE TEST" in ledger
    # Mission-specific ledger flags still present.
    assert "`CODED EVID PR_OPEN REVIEWED MERGED ACCEPT`" in ledger
    # Mission-specific EVID repro example carried in the ledger section.
    assert "EVID=true" in ledger_flat
    assert "only when it no longer reproduces" in ledger_flat
    # The fix-loop section still wires EVID as the gate before OPEN_PR.
    assert "Before OPEN_PR" in tasks
    assert "EXACT reproduction from the" in tasks
    assert "finding's Evidence block" in tasks
    assert "sets `EVID`" in tasks
    assert "Reviewer independently" in tasks
    assert "re-runs the same Evidence reproduction" in tasks
    assert "sets `EVID` only when it no longer reproduces" in squash(tasks)
    assert "set `EVID` immediately without re-running" not in tasks
    assert "even when the finding still reproduces" not in tasks
    assert_no_contradiction_markers(ledger)
    assert_no_contradiction_markers(tasks)


def test_root_cause_clusters_have_foundation_independent_schema() -> None:
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")
    defaults = section(text, "DECISION DEFAULTS", None)

    assert "root-cause CLUSTERS" in tasks
    assert "`FOUNDATION|INDEPENDENT`" in tasks
    assert "`touches:` file-list" in tasks
    assert "`CLOSES=[ids]`" in tasks
    assert "Finalize root-cause CLUSTERS" in tasks
    assert "FOUNDATION cluster's root cause once" in tasks
    assert "dependent findings" in tasks
    assert "inherit" in tasks
    assert "Fixing a FOUNDATION cluster's root cause once closes its dependent findings" in defaults
    assert "`CLOSED via PR#n`" in defaults
    assert (
        "Fixing a FOUNDATION cluster's root cause once closes its dependent findings only when "
        "the shared PR satisfies every dependent finding's Evidence and acceptance gates"
    ) in squash(defaults)
    assert "auto-closes ALL dependents unconditionally" not in defaults
    assert "skip each dependent" not in defaults
    assert_no_contradiction_markers(tasks)
    assert_no_contradiction_markers(defaults)


def test_decision_defaults_exercise_fixes_like_production() -> None:
    text = read_skill()
    defaults = section(text, "DECISION DEFAULTS", None)

    assert "Fixes must be exercised the way production runs them, not just CI-green" in defaults
    assert "`docs/secure-ship-e2e.md`" in defaults
    assert "same invocation, wiring, and result path production uses" in defaults
    assert (
        "validation is not terminal evidence unless it traverses the same invocation, wiring, "
        "and result path production uses."
    ) in squash(defaults)
    assert "CI-green IS sufficient terminal evidence" not in defaults
    assert "skip the production invocation" not in defaults
    assert_no_contradiction_markers(defaults)
