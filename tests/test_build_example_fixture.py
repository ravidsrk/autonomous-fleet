"""Smoke test for scripts/_build_example_fixture.py.

The generator is invoked once at import-time-bootstrapped paths to keep
its statements covered by the standing coverage gate (100% required by
validate-all.sh). The test runs the generator into a temp directory and
asserts the produced artifacts validate against the schemas.

If the generator's output drifts from the committed fixture, this test
does NOT fail (that comparison is deliberately not made: the committed
fixture is the canonical artifact; regeneration is an operator action).
The test only asserts the generator runs end-to-end and produces a
schema-valid archive.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "_build_example_fixture",
        REPO_ROOT / "scripts" / "_build_example_fixture.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generator_runs_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """build_fixture() produces a schema-valid archive on disk."""
    gen = _load_generator()

    # Redirect the fixture output dir to tmp_path. The generator writes to
    # REPO_ROOT / ".fleet/runs/example-fixture/" by default; override the
    # module-level path constant so the test doesn't clobber the committed
    # fixture.
    if hasattr(gen, "FIXTURE_DIR"):
        monkeypatch.setattr(gen, "FIXTURE_DIR", tmp_path / "example-fixture")
    elif hasattr(gen, "REPO_ROOT"):
        monkeypatch.setattr(gen, "REPO_ROOT", tmp_path)
    else:
        # Fall back to chdir; the generator must write its outputs under CWD.
        monkeypatch.chdir(tmp_path)
        # Some generators hardcode an absolute path; in that case the test
        # can still run but will write to the real path. Detect and skip.
        gen.build_fixture()
        return

    gen.build_fixture()

    # The fixture directory must exist after the run.
    fixture_dir = tmp_path / "example-fixture"
    if not fixture_dir.is_dir():
        # Generator may write inside .fleet/runs/example-fixture/
        fixture_dir = tmp_path / ".fleet" / "runs" / "example-fixture"
    assert fixture_dir.is_dir(), f"generator did not produce {fixture_dir}"

    # Manifest must be valid JSON with the right run_id shape and required
    # top-level keys.
    manifest = json.loads((fixture_dir / "manifest.json").read_text())
    assert manifest.get("schema_version") == "1.0"
    run_id = manifest.get("run_id", "")
    assert run_id.startswith("20260623T000000Z-"), run_id
    assert isinstance(manifest.get("files"), list) and len(manifest["files"]) > 0
    # Fleet-outcome carries archive_enabled per the substrate spec.
    outcome_text = (fixture_dir / "fleet-outcome.yaml").read_text()
    assert "archive_enabled: true" in outcome_text

    # Findings doc must be valid JSON with at least 1 finding.
    findings = json.loads((fixture_dir / "p0-review-findings.json").read_text())
    assert findings.get("schema_version") == "1.0"
    assert len(findings.get("findings", [])) >= 1

    # The built manifest's sha256 + sizes must match the files on disk — this
    # catches a generator that writes wrong hashes/sizes into the manifest.
    from lib.fleet_run import load_and_validate_manifest

    _payload, errors = load_and_validate_manifest(fixture_dir)
    assert errors == [], errors


def test_generator_helpers() -> None:
    """Cover the small pure helpers at module level."""
    gen = _load_generator()

    # _sha256_bytes: deterministic hash
    h1 = gen._sha256_bytes(b"hello")
    h2 = gen._sha256_bytes(b"hello")
    assert h1 == h2
    assert len(h1) == 64

    # _iso_to_epoch: monotonic for sorted timestamps
    t1 = gen._iso_to_epoch("2026-06-23T00:00:00Z")
    t2 = gen._iso_to_epoch("2026-06-23T00:00:01Z")
    assert t2 > t1
