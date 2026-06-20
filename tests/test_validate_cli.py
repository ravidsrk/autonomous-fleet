"""Tests for validate_fleet_outcome.py CLI path collection."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_fleet_outcome import collect_readiness_paths  # noqa: E402


def test_collect_readiness_paths_returns_all_matches_sorted_and_unique(
    tmp_path: Path,
) -> None:
    """M3d: under a tmp root with MULTIPLE docs/*-readiness.md files,
    collect_readiness_paths must return ALL of them, SORTED ascending, with
    no duplicates. The previous version of this test only created one file and
    asserted ``paths.count(arch) == 1`` which is trivially true for any glob
    funneled through a set — it didn't actually constrain completeness or
    ordering. This rewrite pins both."""
    docs = tmp_path / "docs"
    docs.mkdir()
    # Create several readiness docs, deliberately written out-of-order on disk
    # so an unsorted return value would visibly differ from the expected list.
    expected_names = [
        "adversarial-readiness.md",
        "arch-build-readiness.md",
        "bug-batch-readiness.md",
        "cleanup-readiness.md",
        "doc-sync-readiness.md",
        "test-coverage-readiness.md",
    ]
    creation_order = [
        "doc-sync-readiness.md",
        "arch-build-readiness.md",
        "test-coverage-readiness.md",
        "adversarial-readiness.md",
        "cleanup-readiness.md",
        "bug-batch-readiness.md",
    ]
    for name in creation_order:
        (docs / name).write_text(f"---\nmission: {name}\nstatus: done\n---\n")
    # Decoys that must NOT be picked up: wrong suffix and wrong directory.
    (docs / "README.md").write_text("# decoy non-readiness\n")
    (docs / "readiness-notes.md").write_text("# decoy wrong suffix\n")
    other = tmp_path / "other"
    other.mkdir()
    (other / "doc-sync-readiness.md").write_text(
        "---\nmission: doc-sync\nstatus: done\n---\n"
    )

    paths = collect_readiness_paths(tmp_path)

    # Completeness: every readiness doc under docs/ is present.
    assert [p.name for p in paths] == expected_names, (
        f"expected all readiness docs in sorted order, got {[p.name for p in paths]}"
    )
    # All returned paths live under the docs/ directory of the tmp root.
    for p in paths:
        assert p.parent == docs, f"unexpected parent for {p}"
    # Uniqueness: no path appears twice.
    assert len(paths) == len(set(paths)) == len(expected_names)
    # Sorted ascending (pinning ordering, not just set membership).
    assert paths == sorted(paths)
    # The decoys outside docs/ or with wrong suffix must be absent.
    assert all(p.name != "README.md" for p in paths)
    assert all(p.name != "readiness-notes.md" for p in paths)
    assert all(p.parent != other for p in paths)