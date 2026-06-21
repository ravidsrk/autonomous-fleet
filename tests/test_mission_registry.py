"""Tests for lib.mission_registry path resolution (was 0% covered)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.mission_registry import progress_path, readiness_path  # noqa: E402


def test_known_mission_default_names():
    assert readiness_path("doc-sync") == "docs/doc-sync-readiness.md"
    assert progress_path("doc-sync") == "docs/doc-sync-progress.md"


def test_known_mission_remapped_names():
    # adversarial-review-and-fix writes the arch-build-* docs, not its own slug.
    assert readiness_path("adversarial-review-and-fix") == "docs/arch-build-readiness.md"
    assert progress_path("adversarial-review-and-fix") == "docs/arch-build-progress.md"


def test_unknown_mission_falls_back_to_slug():
    assert readiness_path("made-up-mission") == "docs/made-up-mission-readiness.md"
    assert progress_path("made-up-mission") == "docs/made-up-mission-progress.md"
