"""Live coordinator trace emission (emit_trace.py emit subcommand)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
EMIT = ROOT / "scripts" / "emit_trace.py"


def test_emit_cli_appends_event_with_manifest_context(tmp_path: Path) -> None:
    run_dir = tmp_path / "20260627T120000Z-doc-sync-abc123"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "20260627T120000Z-doc-sync-abc123",
                "mission": "doc-sync",
            }
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            sys.executable,
            str(EMIT),
            "emit",
            str(run_dir),
            "--primitive",
            "DISPATCH",
            "--role",
            "COORDINATOR",
            "--status",
            "started",
            "--task-id",
            "D1",
            "--id-only",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    event_id = r.stdout.strip()
    assert event_id
    trace = run_dir / "trace.jsonl"
    assert trace.is_file()
    event = json.loads(trace.read_text(encoding="utf-8").strip())
    assert event["primitive"] == "DISPATCH"
    assert event["mission"] == "doc-sync"
    assert event["id"] == event_id


def test_resolve_run_context_from_run_id_dirname(tmp_path: Path) -> None:
    from lib.coordinator_trace import resolve_run_context

    run_dir = tmp_path / "20260627T120000Z-test-coverage-deadbe"
    run_dir.mkdir()
    mission, run_id = resolve_run_context(run_dir)
    assert mission == "test-coverage"
    assert run_id == "20260627T120000Z-test-coverage-deadbe"


def test_emit_requires_mission_when_unresolvable(tmp_path: Path) -> None:
    run_dir = tmp_path / "scratch"
    run_dir.mkdir()
    from lib.coordinator_trace import emit_coordinator_event

    with pytest.raises(ValueError, match="--mission"):
        emit_coordinator_event(
            run_dir,
            primitive="WAIT",
            role="COORDINATOR",
            status="started",
        )


def test_resolve_run_context_explicit_override() -> None:
    from lib.coordinator_trace import resolve_run_context

    mission, run_id = resolve_run_context(
        Path("/tmp/ignored"),
        mission="doc-sync",
        run_id="20260627T120000Z-doc-sync-abc123",
    )
    assert mission == "doc-sync"
    assert run_id == "20260627T120000Z-doc-sync-abc123"


def test_resolve_run_context_bad_manifest(tmp_path: Path) -> None:
    from lib.coordinator_trace import resolve_run_context

    run_dir = tmp_path / "20260627T120000Z-doc-sync-abc123"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot read manifest"):
        resolve_run_context(run_dir)


def test_emit_coordinator_event_with_details(tmp_path: Path) -> None:
    from lib.coordinator_trace import emit_coordinator_event

    run_dir = tmp_path / "20260627T120000Z-doc-sync-abc123"
    run_dir.mkdir()
    event_id = emit_coordinator_event(
        run_dir,
        primitive="INSPECT",
        role="REVIEWER",
        status="succeeded",
        mission="doc-sync",
        run_id="20260627T120000Z-doc-sync-abc123",
        details={"note": "ok"},
    )
    assert event_id