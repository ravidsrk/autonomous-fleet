"""The mutation gate must not be inert: prove it reports SURVIVED / STALE and restores files.

This is the anti-inflation check applied to the gate itself. A gate that always returns 0 would be
the exact failure shape it exists to catch, so these tests force a weak-guard and a stale entry and
assert the gate FAILS, and assert a known-good real mutation is caught.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mutation_check as mc  # noqa: E402


def _manifest(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump({"mutations": entries}), encoding="utf-8")
    return p


def test_gate_reports_survivor_when_guard_is_weak(tmp_path, capsys):
    # Mutate a real, tracked-clean file harmlessly; guard is a test that passes regardless of it.
    # The mutation therefore SURVIVES and the gate must fail (rc 1) and name it.
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
    rc = mc.run(ROOT / "tests" / "mutations.yaml", {"e2e-gate-inert"}, quiet=True)
    assert rc == 0
    # restored
    assert "is not True" in (ROOT / "scripts" / "lib" / "fleet_outcome.py").read_text(
        encoding="utf-8"
    )


def test_invalidate_pycache_skips_non_python(tmp_path) -> None:
    mc._invalidate_pycache(tmp_path / "readme.md")
    mc._invalidate_pycache(tmp_path / "module.py")  # no __pycache__ yet


def test_invalidate_pycache_removes_matching_bytecode(tmp_path) -> None:
    mod = tmp_path / "mod.py"
    mod.write_text("x = 1\n", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    pyc = cache / "mod.cpython-312.pyc"
    pyc.write_bytes(b"fake")
    mc._invalidate_pycache(mod)
    assert not pyc.exists()


def test_invalidate_pycache_swallows_unlink_oserror(tmp_path, monkeypatch) -> None:
    mod = tmp_path / "mod.py"
    mod.write_text("x = 1\n", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    pyc = cache / "mod.cpython-312.pyc"
    pyc.write_bytes(b"fake")

    def _boom(self):  # noqa: ANN001
        raise OSError("simulated")

    monkeypatch.setattr(type(pyc), "unlink", _boom)
    mc._invalidate_pycache(mod)  # must not raise


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


def test_dirty_target_is_restored_to_dirty_pre_run_content(tmp_path, monkeypatch):
    readme = ROOT / "README.md"
    original = readme.read_text(encoding="utf-8")
    dirty = original + "\n<!-- dirty before mutation gate -->\n"
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
    monkeypatch.setattr(mc, "_run_guards", lambda _guards: True)
    try:
        readme.write_text(dirty, encoding="utf-8")
        rc = mc.run(manifest, None, quiet=True)
        assert rc == 0
        assert readme.read_text(encoding="utf-8") == dirty
    finally:
        readme.write_text(original, encoding="utf-8")


def test_main_entry_point_runs_gate(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["mutation_check", "--id", "e2e-gate-inert"])
    assert mc.main() == 0  # main() + non-quiet caught print + the restore finally
