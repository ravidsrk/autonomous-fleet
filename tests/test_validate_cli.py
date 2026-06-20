"""Tests for validate_fleet_outcome.py CLI path collection."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_fleet_outcome import collect_readiness_paths  # noqa: E402


def test_arch_build_readiness_collected_once(tmp_path: Path) -> None:
    """DUP-10: arch-build-readiness.md must appear at most once in default paths."""
    docs = tmp_path / "docs"
    docs.mkdir()
    arch = docs / "arch-build-readiness.md"
    arch.write_text("---\nmission: arch-build\nstatus: done\n---\n")
    other = docs / "doc-sync-readiness.md"
    other.write_text("---\nmission: doc-sync\nstatus: done\n---\n")

    paths = collect_readiness_paths(tmp_path)

    assert paths.count(arch) == 1
    assert len(paths) == 2