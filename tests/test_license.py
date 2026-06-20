"""Tests for LICENSE canonical MIT grant clause (H1 regression)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_license_has_canonical_mit_grant_clause() -> None:
    """H1: LICENSE must contain the canonical MIT permission grant verbs."""
    license_text = (ROOT / "LICENSE").read_text()
    # Collapse line wraps so the canonical sentence matches regardless of
    # where MIT's 80-column wrap breaks "sell / copies".
    flattened = " ".join(license_text.split())
    assert (
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software"
        in flattened
    )


def test_license_does_not_contain_migrate() -> None:
    """H1: the non-canonical word 'migrate' must not appear in LICENSE."""
    license_text = (ROOT / "LICENSE").read_text()
    assert "migrate" not in license_text.lower()
