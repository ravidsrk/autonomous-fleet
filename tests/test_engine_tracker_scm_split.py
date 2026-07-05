"""Structural test for the TRACKER vs SCM binding split in the engine contract.

The engine must name TRACKER and SCM as distinct bindings and state that gh is the
DEFAULT, not the contract, so a non-GitHub tracker (Linear) is expressible. The test
asserts the abstraction boundary phrasing, not the mere presence of the word 'gh'
(an inert grep for 'gh' would not catch the contract being re-tightened to REQUIRED).

Since the engine.md core split (0.3.0), the binding DETAIL lives in the
trigger-loaded engine-workers.md while the always-read core keeps the index
entry — so the contract surface here is core + workers, and the index
assertion is pinned to the core alone.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "skills" / "autonomous-fleet-core" / "references"
ENGINE_CORE = REFS / "engine.md"
ENGINE_WORKERS = REFS / "engine-workers.md"


def _core() -> str:
    return " ".join(ENGINE_CORE.read_text(encoding="utf-8").split())


def _engine() -> str:
    surface = ENGINE_CORE.read_text(encoding="utf-8") + "\n" + ENGINE_WORKERS.read_text(
        encoding="utf-8"
    )
    return " ".join(surface.split())


def test_tracker_and_scm_are_distinct_bindings() -> None:
    # The always-read core must still INDEX the split; the detail may live in
    # the trigger-loaded workers reference.
    assert "TRACKER vs SCM bindings" in _core()
    engine = _engine()
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
