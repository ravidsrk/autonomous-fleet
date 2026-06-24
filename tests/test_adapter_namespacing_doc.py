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
