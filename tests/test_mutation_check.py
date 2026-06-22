"""The mutation gate must not be inert: prove it reports SURVIVED / STALE and restores files.

This is the anti-inflation check applied to the gate itself. A gate that always returns 0 would be
the exact failure shape it exists to catch, so these tests force a weak-guard and a stale entry and
assert the gate FAILS, and assert a known-good real mutation is caught.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mutation_check as mc  # noqa: E402


def _manifest(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump({"mutations": entries}), encoding="utf-8")
    return p


def _require_clean(rel: str) -> None:
    # The gate refuses to mutate a dirty file; skip rather than fail if a probe target is dirty.
    r = subprocess.run(
        ["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True
    )
    if r.stdout.strip():
        pytest.skip(f"{rel} has uncommitted changes; gate self-test needs it clean")


def test_gate_reports_survivor_when_guard_is_weak(tmp_path, capsys):
    # Mutate a real, tracked-clean file harmlessly; guard is a test that passes regardless of it.
    # The mutation therefore SURVIVES and the gate must fail (rc 1) and name it.
    _require_clean("README.md")
    manifest = _manifest(
        tmp_path,
        [
            {
                "id": "weak-guard",
                "file": "README.md",
                "find": "autonomous-fleet",
                "replace": "autonomous-fleet-MUTATED",
                "guards": ["tests/test_license.py"],
            }
        ],
    )
    rc = mc.run(manifest, None, quiet=False)
    out = capsys.readouterr().out
    assert rc == 1
    assert "SURVIVED" in out and "weak-guard" in out
    # and the file was restored
    assert "autonomous-fleet-MUTATED" not in (ROOT / "README.md").read_text(encoding="utf-8")


def test_gate_reports_stale_when_find_absent(tmp_path, capsys):
    _require_clean("README.md")
    manifest = _manifest(
        tmp_path,
        [
            {
                "id": "stale-entry",
                "file": "README.md",
                "find": "ZZ_STRING_NOT_IN_README_ZZ",
                "replace": "x",
                "guards": ["tests/test_license.py"],
            }
        ],
    )
    rc = mc.run(manifest, None, quiet=False)
    out = capsys.readouterr().out
    assert rc == 1
    assert "STALE" in out and "stale-entry" in out


def test_gate_catches_a_known_real_mutation(tmp_path):
    # The positive path: a real manifest entry whose guard genuinely catches it returns 0.
    _require_clean("scripts/lib/fleet_outcome.py")
    rc = mc.run(ROOT / "tests" / "mutations.yaml", {"e2e-gate-inert"}, quiet=True)
    assert rc == 0
    # restored
    assert "is not True" in (ROOT / "scripts" / "lib" / "fleet_outcome.py").read_text(
        encoding="utf-8"
    )
