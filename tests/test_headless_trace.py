"""Tests for headless dry-run trace emission (real entry-point path)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.emit_trace import PRIMITIVES, TraceEmitter, iter_trace_file, validate_event  # noqa: E402
from lib import fleet_run  # noqa: E402
from lib.headless_trace import (  # noqa: E402
    emit_headless_dryrun_archive,
    progress_excerpt_for_mission,
    record_headless_run,
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


def _cleanup_archive(arch: Path) -> None:
    if arch.is_dir():
        shutil.rmtree(arch)


def test_progress_excerpt_reads_doc_sync_progress() -> None:
    text = progress_excerpt_for_mission(REPO_ROOT, "doc-sync")
    assert "MISSION: doc-sync" in text
    assert "doc-sync-progress" not in text  # content, not path


def test_progress_excerpt_reads_arch_build_for_adversarial_mission() -> None:
    text = progress_excerpt_for_mission(REPO_ROOT, "adversarial-review-and-fix")
    assert "arch-build-progress" in text
    assert "mechanical validation" not in text


def test_progress_excerpt_fallback_for_unknown_mission(tmp_path: Path) -> None:
    text = progress_excerpt_for_mission(tmp_path, "no-such-mission")
    assert "no-such-mission" in text


def test_fleet_run_emit_dryrun_lifecycle_trace_eleven_primitives(tmp_path: Path) -> None:
    run_id = "20260626T120000Z-doc-sync-000099"
    arch = tmp_path / ".fleet" / "runs" / run_id
    arch.mkdir(parents=True)
    with TraceEmitter(arch, mission="doc-sync", run_id=run_id) as emitter:
        ids = fleet_run.emit_dryrun_lifecycle_trace(
            emitter, task_id="t1", runtime="grok", include_t_final=True, file_count=1
        )
    events = list(iter_trace_file(arch / "trace.jsonl"))
    assert len(ids) == 11
    assert len(events) == 11
    assert {e["primitive"] for e in events} == set(PRIMITIVES)


def test_emit_dryrun_lifecycle_derives_statuses_from_doc_sync_progress(
    tmp_path: Path,
) -> None:
    """Progress excerpt drives task_id and ledger-derived primitive statuses."""
    progress = progress_excerpt_for_mission(REPO_ROOT, "doc-sync")
    run_id = "20260626T120000Z-doc-sync-000099"
    arch = tmp_path / ".fleet" / "runs" / run_id
    arch.mkdir(parents=True)
    with TraceEmitter(arch, mission="doc-sync", run_id=run_id) as emitter:
        fleet_run.emit_dryrun_lifecycle_trace(
            emitter,
            mission="doc-sync",
            progress_excerpt=progress,
            runtime="grok",
            include_t_final=True,
            file_count=1,
        )
    events = list(iter_trace_file(arch / "trace.jsonl"))
    task_events = [e for e in events if e.get("task_id")]
    assert task_events
    assert all(e["task_id"] == "doc-sync-readme" for e in task_events)
    inspect = next(e for e in events if e["primitive"] == "INSPECT")
    assert inspect["status"] == "succeeded"
    merge = next(e for e in events if e["primitive"] == "MERGE")
    assert merge["status"] == "started"
    goal = next(e for e in events if e["primitive"] == "GOAL_BLOCKED")
    assert goal["status"] == "skipped"
    assert "MISSION:doc-sync" in goal["details"]["reason"]


def test_emit_headless_dryrun_archive_all_eleven_primitives(tmp_path: Path) -> None:
    arch, run_id, primitives = emit_headless_dryrun_archive(
        tmp_path,
        mission="doc-sync",
        runtime="grok",
        fleet_root=REPO_ROOT,
    )
    try:
        assert arch == tmp_path / ".fleet" / "runs" / run_id
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
        assert not (REPO_ROOT / ".fleet" / "runs" / run_id).exists()
    finally:
        _cleanup_archive(arch)


def test_external_repo_writes_archive_under_repo_not_fleet_root(tmp_path: Path) -> None:
    """--repo external: archive under target checkout; excerpt from fleet_root."""
    external = tmp_path / "external-gemoji"
    external.mkdir()
    arch, run_id, primitives = fleet_run.write_headless_dryrun_archive(
        external,
        mission="doc-sync",
        runtime="grok",
        progress_source_root=REPO_ROOT,
    )
    try:
        assert arch == external / ".fleet" / "runs" / run_id
        assert len(primitives) == 11
        assert "MISSION: doc-sync" in (arch / "headless-dryrun-progress.md").read_text()
        assert not (REPO_ROOT / ".fleet" / "runs" / run_id).exists()
    finally:
        _cleanup_archive(arch)


def test_write_manifest_emits_t_final_via_emitter(tmp_path: Path) -> None:
    arch, _run_id, _prims = emit_headless_dryrun_archive(
        tmp_path,
        mission="test-coverage",
        runtime="codex",
        fleet_root=REPO_ROOT,
    )
    try:
        events = list(iter_trace_file(arch / "trace.jsonl"))
        assert events[-1]["primitive"] == "T-FINAL"
    finally:
        _cleanup_archive(arch)


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


def test_run_mission_headless_external_repo_cleans_up_under_repo(tmp_path: Path) -> None:
    external = tmp_path / "target-repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)
    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--dry-run",
            "--repo",
            str(external),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "primitives (11):" in r.stdout
    leftover = list((external / ".fleet" / "runs").glob("*")) if (external / ".fleet" / "runs").is_dir() else []
    assert leftover == [], f"expected cleanup under external repo, found {leftover}"


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
    runs = list((tmp_path / ".fleet" / "runs").glob("*")) if (tmp_path / ".fleet" / "runs").is_dir() else []
    for d in runs:
        shutil.rmtree(d)


def test_headless_cli_fleet_program_maps_to_doc_sync(tmp_path: Path) -> None:
    cli = _load_headless_cli()
    try:
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
    finally:
        runs = list((tmp_path / ".fleet" / "runs").glob("*")) if (tmp_path / ".fleet" / "runs").is_dir() else []
        for d in runs:
            shutil.rmtree(d)


def test_emit_headless_default_fleet_root(tmp_path: Path) -> None:
    arch, run_id, primitives = emit_headless_dryrun_archive(
        tmp_path,
        mission="doc-sync",
        runtime="grok",
        fleet_root=None,
    )
    try:
        assert arch == tmp_path / ".fleet" / "runs" / run_id
        assert len(primitives) == 11
        assert "-doc-sync-" in run_id
    finally:
        _cleanup_archive(arch)


def test_headless_trace_record_headless_run_wrapper(tmp_path: Path) -> None:
    arch, run_id, primitives = record_headless_run(
        tmp_path,
        mission="doc-sync",
        runtime="grok",
        fleet_root=REPO_ROOT,
    )
    try:
        assert arch == tmp_path / ".fleet" / "runs" / run_id
        assert len(primitives) == 11
    finally:
        _cleanup_archive(arch)


def test_record_headless_run_alias(tmp_path: Path) -> None:
    arch, run_id, primitives = fleet_run.record_headless_run(
        tmp_path,
        mission="doc-sync",
        runtime="grok",
        progress_source_root=REPO_ROOT,
    )
    try:
        assert arch == tmp_path / ".fleet" / "runs" / run_id
        assert len(primitives) == 11
        _payload, errs = fleet_run.load_and_validate_manifest(arch)
        assert errs == []
    finally:
        _cleanup_archive(arch)


def test_external_git_repo_emit_twice_creates_two_archives(tmp_path: Path) -> None:
    """Simulate pre-DONE re-runs: two distinct archives under external --repo."""
    external = tmp_path / "external"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init", "-q"],
        cwd=external,
        check=True,
    )
    cli = _load_headless_cli()
    try:
        assert (
            cli.main(
                [
                    "--mission",
                    "doc-sync",
                    "--repo",
                    str(external),
                    "--fleet-root",
                    str(REPO_ROOT),
                ]
            )
            == 0
        )
        assert (
            cli.main(
                [
                    "--mission",
                    "doc-sync",
                    "--repo",
                    str(external),
                    "--fleet-root",
                    str(REPO_ROOT),
                ]
            )
            == 0
        )
        runs = sorted((external / ".fleet" / "runs").iterdir())
        assert len(runs) == 2
        assert runs[0].name != runs[1].name
        for run_dir in runs:
            assert (run_dir / "manifest.json").is_file()
            assert (run_dir / "trace.jsonl").is_file()
            vr = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "validate_run_archive.py"),
                    str(run_dir),
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO_ROOT,
            )
            assert vr.returncode == 0, vr.stderr
            vt = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "emit_trace.py"),
                    "validate",
                    str(run_dir / "trace.jsonl"),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO_ROOT,
            )
            assert vt.returncode == 0, vt.stderr
    finally:
        if (external / ".fleet" / "runs").is_dir():
            shutil.rmtree(external / ".fleet" / "runs")


def test_write_headless_archive_includes_runtime_response_json(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    capture.write_text('{"stopReason":"EndTurn","text":"ok"}', encoding="utf-8")
    external = tmp_path / "repo"
    external.mkdir()
    arch, _run_id, _prims = fleet_run.write_headless_dryrun_archive(
        external,
        mission="doc-sync",
        runtime="grok",
        progress_source_root=REPO_ROOT,
        runtime_response_path=capture,
    )
    try:
        response_path = arch / "headless-runtime-response.json"
        assert response_path.is_file()
        assert "EndTurn" in response_path.read_text(encoding="utf-8")
        payload, errs = fleet_run.load_and_validate_manifest(arch)
        assert errs == []
        kinds = {e["kind"] for e in payload["files"]}
        assert "response" in kinds
    finally:
        _cleanup_archive(arch)


def test_runtime_response_archive_name_plain_text(tmp_path: Path) -> None:
    capture = tmp_path / "out.txt"
    capture.write_text("plain runtime log\n", encoding="utf-8")
    assert fleet_run._runtime_response_archive_name(capture) == "headless-runtime-response.txt"


def test_runtime_response_archive_name_missing_file(tmp_path: Path) -> None:
    assert (
        fleet_run._runtime_response_archive_name(tmp_path / "missing-capture")
        == "headless-runtime-response.txt"
    )


def test_runtime_response_archive_name_empty_file(tmp_path: Path) -> None:
    capture = tmp_path / "empty"
    capture.write_bytes(b"")
    assert fleet_run._runtime_response_archive_name(capture) == "headless-runtime-response.txt"
    assert fleet_run._runtime_response_has_content(capture) is False


def test_runtime_response_has_content_stat_failure(tmp_path: Path) -> None:
    from unittest.mock import patch

    capture = tmp_path / "f"
    capture.write_bytes(b"x")
    with patch.object(Path, "stat", side_effect=OSError("simulated stat failure")):
        assert fleet_run._runtime_response_has_content(capture) is False


def test_write_headless_archive_skips_empty_runtime_response(tmp_path: Path) -> None:
    capture = tmp_path / "empty-capture"
    capture.write_bytes(b"")
    external = tmp_path / "repo"
    external.mkdir()
    arch, _run_id, _prims = fleet_run.write_headless_dryrun_archive(
        external,
        mission="doc-sync",
        runtime="grok",
        progress_source_root=REPO_ROOT,
        runtime_response_path=capture,
    )
    try:
        assert not (arch / "headless-runtime-response.json").exists()
        assert not (arch / "headless-runtime-response.txt").exists()
        payload, errs = fleet_run.load_and_validate_manifest(arch)
        assert errs == []
        kinds = {e["kind"] for e in payload["files"]}
        assert "response" not in kinds
    finally:
        _cleanup_archive(arch)


def test_run_mission_headless_merges_stderr_into_archive(tmp_path: Path) -> None:
    """Runtime stderr is captured in the merged transcript (intentional for archive)."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_grok = fake_bin / "grok"
    fake_grok.write_text('#!/bin/sh\necho \'{"error":"stderr-only"}\' >&2\nexit 1\n')
    fake_grok.chmod(0o755)

    external = tmp_path / "repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--repo",
            str(external),
            "--max-turns",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    assert r.returncode == 1
    assert '{"error":"stderr-only"}' in r.stdout
    runs = list((external / ".fleet" / "runs").glob("*"))
    assert len(runs) == 1
    assert (runs[0] / "headless-runtime-response.json").is_file()


def test_run_mission_headless_emits_archive_on_runtime_failure(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_grok = fake_bin / "grok"
    fake_grok.write_text('#!/bin/sh\necho \'{"error":"boom"}\' >&2\nexit 1\n')
    fake_grok.chmod(0o755)

    external = tmp_path / "repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--repo",
            str(external),
            "--max-turns",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    assert r.returncode == 1, r.stderr + r.stdout
    assert "archive emitted for --repo:" in r.stdout
    runs = list((external / ".fleet" / "runs").glob("*"))
    assert len(runs) == 1
    assert (runs[0] / "headless-runtime-response.json").is_file()


def _fake_grok_on_path(tmp_path: Path) -> dict[str, str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_grok = fake_bin / "grok"
    fake_grok.write_text('#!/bin/sh\necho \'{"stopReason":"EndTurn","text":"ok"}\'\n')
    fake_grok.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    return env


def _git_porcelain(repo: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_external_repo_comes_back_clean_after_real_run(tmp_path: Path) -> None:
    """Finding 55: a real run writes .fleet/runs/<id> INTO --repo. The driver must
    exclude it via .git/info/exclude (untracked) so the operator's tree stays clean
    AND no tracked .gitignore is touched."""
    external = tmp_path / "target-repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.co"], cwd=external, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=external, check=True)
    (external / "README.md").write_text("# x\n")
    subprocess.run(["git", "add", "-A"], cwd=external, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=external, check=True)

    env = _fake_grok_on_path(tmp_path)
    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--repo",
            str(external),
            "--max-turns",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "excluded .fleet/runs/ via" in r.stdout
    # The archive is kept (audit trail) but the working tree is CLEAN.
    runs = list((external / ".fleet" / "runs").glob("*"))
    assert len(runs) == 1
    assert _git_porcelain(external) == "", "external repo must come back clean"
    # Exclude went into the UNTRACKED per-clone exclude, not a tracked .gitignore.
    assert not (external / ".gitignore").exists()
    exclude = external / ".git" / "info" / "exclude"
    assert "/.fleet/runs/" in exclude.read_text()


def test_external_repo_exclude_is_idempotent(tmp_path: Path) -> None:
    """Two real runs must not append duplicate exclude lines, and the second run
    must short-circuit (no repeated 'excluded' note since it is already ignored)."""
    external = tmp_path / "target-repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.co"], cwd=external, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=external, check=True)

    env = _fake_grok_on_path(tmp_path)
    args = [
        str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
        "grok",
        "doc-sync",
        "--repo",
        str(external),
        "--max-turns",
        "1",
    ]
    r1 = subprocess.run(args, capture_output=True, text=True, check=False, cwd=REPO_ROOT, env=env)
    assert r1.returncode == 0, r1.stderr
    assert "excluded .fleet/runs/ via" in r1.stdout
    r2 = subprocess.run(args, capture_output=True, text=True, check=False, cwd=REPO_ROOT, env=env)
    assert r2.returncode == 0, r2.stderr
    # Already ignored -> the guard returns early, no second "excluded" note.
    assert "excluded .fleet/runs/ via" not in r2.stdout
    exclude = external / ".git" / "info" / "exclude"
    assert exclude.read_text().count("/.fleet/runs/") == 1


def test_external_repo_with_existing_gitignore_not_touched(tmp_path: Path) -> None:
    """If the target repo already gitignores .fleet/runs/ via a tracked .gitignore,
    the guard must do nothing (no exclude write, no note) — check-ignore short-circuits."""
    external = tmp_path / "target-repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.co"], cwd=external, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=external, check=True)
    (external / ".gitignore").write_text(".fleet/runs/\n")
    subprocess.run(["git", "add", "-A"], cwd=external, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=external, check=True)

    env = _fake_grok_on_path(tmp_path)
    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--repo",
            str(external),
            "--max-turns",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "excluded .fleet/runs/ via" not in r.stdout
    # Untracked exclude must NOT have been written (tracked .gitignore already covers it).
    exclude_text = (external / ".git" / "info" / "exclude").read_text()
    assert "/.fleet/runs/" not in exclude_text
    assert _git_porcelain(external) == "", "tree stays clean (archive already ignored)"


def test_self_repo_exclude_untouched(tmp_path: Path) -> None:
    """When --repo IS the autonomous-fleet clone (REPO_ROOT == ROOT), the guard must
    short-circuit and never modify the fleet clone's own .git/info/exclude."""
    exclude_path = Path(
        subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    if not exclude_path.is_absolute():
        exclude_path = REPO_ROOT / exclude_path
    before = exclude_path.read_text() if exclude_path.exists() else None

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
    assert "excluded .fleet/runs/ via" not in r.stdout
    after = exclude_path.read_text() if exclude_path.exists() else None
    assert before == after, "self-repo exclude must be unchanged"


def test_run_mission_headless_keeps_archive_after_runtime(tmp_path: Path) -> None:
    """Real run-mission-headless.sh path: fake grok on PATH, archive kept under --repo."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_grok = fake_bin / "grok"
    fake_grok.write_text('#!/bin/sh\necho \'{"stopReason":"EndTurn","text":"ok"}\'\n')
    fake_grok.chmod(0o755)

    external = tmp_path / "repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--repo",
            str(external),
            "--max-turns",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "archive emitted for --repo:" in r.stdout
    assert "kept:" in r.stdout
    runs = list((external / ".fleet" / "runs").glob("*"))
    assert len(runs) == 1
    assert (runs[0] / "manifest.json").is_file()
    assert (runs[0] / "trace.jsonl").is_file()
    assert (runs[0] / "headless-runtime-response.json").is_file()


def test_run_mission_headless_emit_failure_fatal_on_real_run(tmp_path: Path) -> None:
    """OPS-001 / HEADLESS-03: successful runtime + failed archive emit => non-zero exit."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_grok = fake_bin / "grok"
    fake_grok.write_text('#!/bin/sh\necho \'{"stopReason":"EndTurn","text":"ok"}\'\n')
    fake_grok.chmod(0o755)

    external = tmp_path / "repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)
    fleet = external / ".fleet"
    fleet.mkdir()
    (fleet / "runs").write_text("not-a-directory\n", encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--repo",
            str(external),
            "--max-turns",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    assert r.returncode != 0, r.stderr + r.stdout
    assert "emit_headless_dryrun_trace failed" in (r.stderr + r.stdout)
    assert "non-fatal" not in (r.stderr + r.stdout)
    assert "archive emitted for --repo:" not in r.stdout


def test_run_mission_headless_dry_run_emit_failure_non_fatal(tmp_path: Path) -> None:
    """Dry-run cleanup path: emit failure warns but still exits 0."""
    external = tmp_path / "repo"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)
    fleet = external / ".fleet"
    fleet.mkdir()
    (fleet / "runs").write_text("not-a-directory\n", encoding="utf-8")

    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            "grok",
            "doc-sync",
            "--repo",
            str(external),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "emit_headless_dryrun_trace failed (non-fatal)" in (r.stderr + r.stdout)
