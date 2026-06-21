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


def test_three_lane_remediation_section_has_all_lanes() -> None:
    text = read_skill()
    lanes = section(text, "THREE-LANE REMEDIATION", "ROLE PIPELINE")

    assert "Lane A IMPLEMENT+MERGE" in lanes
    assert "Lane B DRAFT BOTH + HUMAN GATE" in lanes
    assert "Lane 0 REFUSE + HUMAN ACTION" in lanes
    assert "editorial, brand, legal, disclosure" in lanes
    assert "Draft both concrete variants" in lanes
    assert "`docs/DECISIONS.md`" in lanes
    assert "HALT at a human decision gate" in lanes
    assert "never auto-merge" in lanes
    assert "`HUMAN_ACTION_REQUIRED:<finding-id>`" in lanes
    assert "`docs/arch-ops-actions.md`" in lanes
    assert "without executing it" in lanes


def test_evid_flag_is_ledger_and_fix_loop_gate() -> None:
    text = read_skill()
    ledger = section(text, "LEDGER", "TASK STRUCTURE")
    ledger_flat = squash(ledger)
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")

    assert "`CODED EVID PR_OPEN REVIEWED MERGED ACCEPT`" in ledger
    assert "`EVID` = the finding's own Evidence reproduction re-run and no longer reproduces" in ledger_flat
    assert "Before OPEN_PR" in tasks
    assert "EXACT reproduction from the" in tasks
    assert "finding's Evidence block" in tasks
    assert "sets `EVID`" in tasks
    assert "Reviewer independently" in tasks
    assert "re-runs the same Evidence reproduction" in tasks


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


def test_decision_defaults_exercise_fixes_like_production() -> None:
    text = read_skill()
    defaults = section(text, "DECISION DEFAULTS", None)

    assert "Fixes must be exercised the way production runs them, not just CI-green" in defaults
    assert "`docs/secure-ship-e2e.md`" in defaults
    assert "same invocation, wiring, and result path production uses" in defaults
