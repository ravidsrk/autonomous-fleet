"""Bundled-substrate parity and standalone-execution guards (issue #80)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "sync_substrate_assets.py"
BUNDLE = ROOT / "skills" / "autonomous-fleet-core" / "assets" / "substrate"

sys.path.insert(0, str(ROOT / "scripts"))


def test_check_mode_green_on_committed_bundle() -> None:
    r = subprocess.run(
        [sys.executable, str(SYNC), "--check"], cwd=ROOT, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "in sync" in r.stdout


def test_bundle_contains_engine_referenced_validators() -> None:
    manifest = json.loads((BUNDLE / "substrate-manifest.json").read_text(encoding="utf-8"))
    files = set(manifest["files"])
    for name in (
        "validate_run_archive.py",
        "verify_findings.py",
        "stop_verify.py",
        "verify_blind_fix.py",
        "recovery_scan.py",
        "emit_trace.py",
        "validate_fleet_outcome.py",
        "verify_sha_pin.py",
        "requirements.txt",
    ):
        assert name in files, f"{name} missing from bundled substrate"
    assert any(f.startswith("lib/") for f in files), "lib/ modules missing from bundle"


def test_manifest_pins_core_version() -> None:
    manifest = json.loads((BUNDLE / "substrate-manifest.json").read_text(encoding="utf-8"))
    skill_md = (ROOT / "skills" / "autonomous-fleet-core" / "SKILL.md").read_text(encoding="utf-8")
    assert f'version: "{manifest["core_version"]}"' in skill_md


def test_bundled_cli_runs_standalone_outside_repo(tmp_path: Path) -> None:
    """The whole point of the bundle: CLIs must run from a foreign path with no
    framework clone around them (path-relative lib imports)."""
    dest = tmp_path / "substrate"
    shutil.copytree(BUNDLE, dest)
    for cli in ("validate_run_archive.py", "verify_findings.py", "stop_verify.py"):
        r = subprocess.run(
            [sys.executable, str(dest / cli), "--help"],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert r.returncode == 0, f"{cli}: {r.stderr}"


def test_bundled_validator_validates_a_real_archive(tmp_path: Path) -> None:
    """Behavioral: the traveling copy enforces, not just prints help."""
    dest = tmp_path / "substrate"
    shutil.copytree(BUNDLE, dest)
    archive = ROOT / ".fleet" / "runs" / "example-fixture"
    r = subprocess.run(
        [sys.executable, str(dest / "validate_run_archive.py"), str(archive)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_detects_drift(tmp_path: Path, monkeypatch) -> None:
    import sync_substrate_assets as ssa

    dest = tmp_path / "substrate"
    shutil.copytree(BUNDLE, dest)
    (dest / "verify_findings.py").write_text("# tampered\n", encoding="utf-8")
    monkeypatch.setattr(ssa, "DEST", dest)
    assert ssa.check() == 1


def test_check_detects_missing_manifest(tmp_path: Path, monkeypatch) -> None:
    import sync_substrate_assets as ssa

    dest = tmp_path / "substrate"
    shutil.copytree(BUNDLE, dest)
    (dest / "substrate-manifest.json").unlink()
    monkeypatch.setattr(ssa, "DEST", dest)
    assert ssa.check() == 1


# --- in-process coverage of sync()/main() and error branches ---------------


def test_sync_writes_bundle_and_manifest(tmp_path: Path, monkeypatch) -> None:
    import sync_substrate_assets as ssa

    dest = tmp_path / "bundle"
    monkeypatch.setattr(ssa, "DEST", dest)
    ssa.sync()
    manifest = json.loads((dest / "substrate-manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["validate_run_archive.py"]
    assert (dest / "lib" / "fleet_run.py").is_file()
    assert (dest / "requirements.txt").read_text(encoding="utf-8").startswith("PyYAML")
    # re-sync over an existing bundle exercises the rmtree branch
    ssa.sync()
    monkeypatch.setattr(ssa, "SCRIPTS", ssa.SCRIPTS)  # no-op; keep flake quiet
    assert ssa.check.__name__ == "check"


def test_sync_then_check_roundtrip_in_process(tmp_path: Path, monkeypatch) -> None:
    import sync_substrate_assets as ssa

    dest = tmp_path / "bundle"
    monkeypatch.setattr(ssa, "DEST", dest)
    ssa.sync()
    assert ssa.check() == 0


def test_check_flags_orphan_and_version_mismatch(tmp_path: Path, monkeypatch) -> None:
    import sync_substrate_assets as ssa

    dest = tmp_path / "bundle"
    monkeypatch.setattr(ssa, "DEST", dest)
    ssa.sync()
    manifest_path = dest / "substrate-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["orphan.py"] = "0" * 64
    manifest["core_version"] = "0.0.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert ssa.check() == 1


def test_check_flags_missing_bundled_file_and_bad_json(tmp_path: Path, monkeypatch) -> None:
    import sync_substrate_assets as ssa

    dest = tmp_path / "bundle"
    monkeypatch.setattr(ssa, "DEST", dest)
    ssa.sync()
    (dest / "stop_verify.py").unlink()
    assert ssa.check() == 1
    (dest / "substrate-manifest.json").write_text("{not json", encoding="utf-8")
    assert ssa.check() == 1


def test_bundle_sources_rejects_missing_allowlisted_cli(monkeypatch) -> None:
    import pytest
    import sync_substrate_assets as ssa

    monkeypatch.setattr(ssa, "CLI_ALLOWLIST", ("does_not_exist.py",))
    with pytest.raises(SystemExit):
        ssa._bundle_sources()


def test_core_version_falls_back_to_unknown(tmp_path: Path, monkeypatch) -> None:
    import sync_substrate_assets as ssa

    fake = tmp_path / "SKILL.md"
    fake.write_text("no frontmatter here\n", encoding="utf-8")
    monkeypatch.setattr(ssa, "CORE_SKILL_MD", fake)
    assert ssa._core_version() == "unknown"


def test_main_check_and_sync_modes(tmp_path: Path, monkeypatch) -> None:
    import sync_substrate_assets as ssa

    dest = tmp_path / "bundle"
    monkeypatch.setattr(ssa, "DEST", dest)
    monkeypatch.setattr(sys, "argv", ["sync_substrate_assets.py"])
    assert ssa.main() == 0
    monkeypatch.setattr(sys, "argv", ["sync_substrate_assets.py", "--check"])
    assert ssa.main() == 0
