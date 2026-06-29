"""Doc-test: no adapter SKILL.md may still use a bare (un-namespaced) worktree/branch.

Wave 3 hash-namespacing requires every isolated branch/worktree to carry the run's
-<run_short> suffix. This greps the shipped adapters for the old un-suffixed literal,
which must be gone everywhere.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BARE_WORKTREE = "add ../<repo>-<slug> -b <BRANCH_PREFIX><slug> BASE"


def test_no_adapter_uses_bare_unnamespaced_worktree() -> None:
    offenders = []
    for skill in (ROOT / "skills").glob("autonomous-fleet-adapter-*/SKILL.md"):
        if BARE_WORKTREE in skill.read_text(encoding="utf-8"):
            offenders.append(skill.parent.name)
    assert not offenders, f"adapters still using a bare slug: {offenders}"


def test_adapters_document_run_short_namespacing() -> None:
    for skill in (ROOT / "skills").glob("autonomous-fleet-adapter-*/SKILL.md"):
        assert "run_short" in skill.read_text(encoding="utf-8"), skill.parent.name


def test_adapters_document_wt_clean_cleanup_guard_clauses() -> None:
    """Each shipped adapter must echo the engine WT_CLEAN gate in CLEANUP — not bare remove."""
    required = (
        "WT_CLEAN",
        "NEVER remove the active",
        "unmerged",
        "dirty",
    )
    for skill in sorted((ROOT / "skills").glob("autonomous-fleet-adapter-*/SKILL.md")):
        if skill.parent.name == "autonomous-fleet-adapter-template":
            continue
        text = skill.read_text(encoding="utf-8")
        for phrase in required:
            assert phrase in text, f"{skill.parent.name} missing {phrase!r} in CLEANUP docs"
