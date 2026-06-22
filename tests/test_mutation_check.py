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


def test_restore_all_rewrites_active_files(tmp_path):
    f = tmp_path / "probe.txt"
    f.write_text("ORIGINAL", encoding="utf-8")
    mc._ACTIVE[f] = "ORIGINAL"
    f.write_text("MUTATED", encoding="utf-8")
    mc._restore_all()
    assert f.read_text(encoding="utf-8") == "ORIGINAL"
    assert not mc._ACTIVE


def test_restore_all_swallows_unwritable_path(tmp_path):
    # a path that can't be written (a directory) must not raise out of the emergency restore
    mc._ACTIVE[tmp_path] = "x"
    mc._restore_all()  # OSError swallowed
    assert not mc._ACTIVE


def test_no_mutations_selected_returns_2(capsys):
    rc = mc.run(ROOT / "tests" / "mutations.yaml", {"no-such-id"}, quiet=True)
    assert rc == 2
    assert "no mutations selected" in capsys.readouterr().err


def test_refuses_to_run_on_dirty_target(tmp_path, capsys):
    _require_clean("README.md")
    readme = ROOT / "README.md"
    original = readme.read_text(encoding="utf-8")
    manifest = _manifest(
        tmp_path,
        [
            {
                "id": "dirty-probe",
                "file": "README.md",
                "find": "autonomous-fleet",
                "replace": "x",
                "guards": ["tests/test_license.py"],
            }
        ],
    )
    try:
        readme.write_text(original + "\n<!-- dirty -->\n", encoding="utf-8")
        rc = mc.run(manifest, None, quiet=True)
    finally:
        readme.write_text(original, encoding="utf-8")
    assert rc == 2
    assert "uncommitted changes" in capsys.readouterr().err


def test_main_entry_point_runs_gate(monkeypatch):
    _require_clean("scripts/lib/fleet_outcome.py")
    monkeypatch.setattr(sys, "argv", ["mutation_check", "--id", "e2e-gate-inert"])
    assert mc.main() == 0  # main() + non-quiet caught print + the restore finally
