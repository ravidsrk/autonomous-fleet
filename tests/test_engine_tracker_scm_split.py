"""Structural test for the TRACKER vs SCM binding split in the engine contract.

The engine must name TRACKER and SCM as distinct bindings and state that gh is the
DEFAULT, not the contract, so a non-GitHub tracker (Linear) is expressible. The test
asserts the abstraction boundary phrasing, not the mere presence of the word 'gh'
(an inert grep for 'gh' would not catch the contract being re-tightened to REQUIRED).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "skills" / "autonomous-fleet-core" / "references" / "engine.md"


def _engine() -> str:
    return " ".join(ENGINE.read_text(encoding="utf-8").split())


def test_tracker_and_scm_are_distinct_bindings() -> None:
    engine = _engine()
    assert "TRACKER vs SCM bindings" in engine
    assert "TRACKER binding" in engine
    assert "SCM binding" in engine


def test_gh_is_default_not_the_contract() -> None:
    engine = _engine()
    # The load-bearing phrasing: gh is DEFAULT, not REQUIRED. The mutation flips this.
    assert "DEFAULT binding for both, NOT the contract" in engine
    assert "REQUIRED binding for both" not in engine


def test_split_does_not_weaken_ship_disciplines() -> None:
    engine = _engine()
    # The abstraction explicitly preserves the merge/SHA-pin rules.
    assert "does NOT relax the conflict-aware, never-squash, or SHA-PIN rules" in engine
