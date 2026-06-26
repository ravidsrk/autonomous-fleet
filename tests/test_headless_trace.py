"""Tests for headless dry-run trace emission (real entry-point path)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.emit_trace import PRIMITIVES, iter_trace_file, validate_event  # noqa: E402
from lib import fleet_run  # noqa: E402
from lib.headless_trace import (  # noqa: E402
    emit_headless_dryrun_archive,
    progress_excerpt_for_mission,
)


def _load_headless_cli():
    spec = importlib.util.spec_from_file_location(
        "emit_headless_dryrun_trace",
        REPO_ROOT / "scripts" / "emit_headless_dryrun_trace.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_progress_excerpt_reads_doc_sync_progress() -> None:
    text = progress_excerpt_for_mission(REPO_ROOT, "doc-sync")
    assert "MISSION: doc-sync" in text
    assert "doc-sync-progress" not in text  # content, not path


def test_progress_excerpt_fallback_for_unknown_mission(tmp_path: Path) -> None:
    text = progress_excerpt_for_mission(tmp_path, "no-such-mission")
    assert "no-such-mission" in text


def test_emit_headless_dryrun_archive_all_eleven_primitives(tmp_path: Path) -> None:
    fleet = REPO_ROOT
    arch, run_id, primitives = emit_headless_dryrun_archive(
        tmp_path,
        mission="doc-sync",
        runtime="grok",
        fleet_root=fleet,
    )
    assert arch.is_dir()
    assert "-doc-sync-" in run_id
    assert set(primitives) == set(PRIMITIVES)
    events = list(iter_trace_file(arch / "trace.jsonl"))
    assert len(events) == 11
    assert all(validate_event(e) == [] for e in events)
    assert (arch / "headless-dryrun-progress.md").is_file()
    assert "MISSION: doc-sync" in (arch / "headless-dryrun-progress.md").read_text()
    _payload, errs = fleet_run.load_and_validate_manifest(arch)
    assert errs == []
    t_final = [e for e in events if e["primitive"] == "T-FINAL"]
    assert len(t_final) == 1


def test_write_manifest_emits_t_final_via_emitter(tmp_path: Path) -> None:
    """T-FINAL must come from write_manifest when include_t_final=False in trace helper."""
    arch, _run_id, _prims = emit_headless_dryrun_archive(
        tmp_path,
        mission="test-coverage",
        runtime="codex",
        fleet_root=REPO_ROOT,
    )
    events = list(iter_trace_file(arch / "trace.jsonl"))
    assert events[-1]["primitive"] == "T-FINAL"


def test_run_mission_headless_dry_run_emits_trace() -> None:
    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--dry-run",
            "--repo",
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "primitives (11):" in r.stdout
    assert "SPAWN_WORKER" in r.stdout or "DISPATCH" in r.stdout
    assert "grok not invoked" in r.stdout


def test_headless_cli_unknown_mission(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _load_headless_cli()
    assert cli.main(["--mission", "not-a-mission", "--repo", str(REPO_ROOT)]) == 2
    assert "unknown mission" in capsys.readouterr().err


def test_headless_cli_missing_repo(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _load_headless_cli()
    assert (
        cli.main(["--mission", "doc-sync", "--repo", "/nonexistent/path/xyz"])
        == 2
    )
    assert "repo not found" in capsys.readouterr().err


def test_headless_cli_main_entrypoint(tmp_path: Path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "emit_headless_dryrun_trace.py"),
            "--mission",
            "doc-sync",
            "--repo",
            str(tmp_path),
            "--fleet-root",
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "primitives (11):" in r.stdout


def test_headless_cli_fleet_program_maps_to_doc_sync(tmp_path: Path) -> None:
    cli = _load_headless_cli()
    assert (
        cli.main(
            [
                "--mission",
                "fleet-program",
                "--repo",
                str(tmp_path),
                "--fleet-root",
                str(REPO_ROOT),
            ]
        )
        == 0
    )


def test_emit_headless_default_fleet_root(tmp_path: Path) -> None:
    """fleet_root=None uses repo_root (covers default branch)."""
    arch, run_id, primitives = emit_headless_dryrun_archive(
        tmp_path,
        mission="doc-sync",
        runtime="grok",
        fleet_root=None,
    )
    assert arch.is_dir()
    assert len(primitives) == 11
    assert "-doc-sync-" in run_id