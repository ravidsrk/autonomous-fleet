"""Tests for hook-signal / no_signal grace (AO port)."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import hook_signal as hs  # noqa: E402

TS0 = "2026-06-28T10:00:00Z"
TS1 = "2026-06-28T10:02:00Z"


def _event(ts: str, primitive: str, **details) -> dict:
    return {
        "schema_version": "1.0",
        "ts": ts,
        "run_id": "run-1",
        "mission": "test",
        "primitive": primitive,
        "role": "COORDINATOR",
        "status": "succeeded",
        "details": details,
    }


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "verify_hook_signal_cli",
        REPO_ROOT / "scripts/verify_hook_signal.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_env = sys.argv, os.environ.copy()
    sys.argv = ["verify_hook_signal.py", *argv]
    if env:
        os.environ.update(env)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main()
    finally:
        sys.argv = old_argv
        os.environ.clear()
        os.environ.update(old_env)
    return rc, out.getvalue(), err.getvalue()


def test_no_signal_after_grace_without_callback() -> None:
    spawn = datetime(2026, 6, 28, 10, 0, 0, tzinfo=timezone.utc)
    now = spawn + timedelta(seconds=hs.HOOK_SIGNAL_GRACE_SECONDS + 1)
    assert (
        hs.derive_signal_status(
            spawn_at=spawn,
            now=now,
            first_signal_at=None,
            hook_capable=True,
        )
        == "no_signal"
    )


def test_verify_flags_idle_inspect_past_grace() -> None:
    events = [
        _event(TS0, "SPAWN_WORKER", task_id="T1"),
        _event(TS1, "INSPECT", task_id="T1", signal_state="idle"),
    ]
    errors = hs.verify_hook_signal_trace(events, hook_capable=True)
    assert errors
    assert "T1" in errors[0]
    assert "no_signal" in errors[0]


def test_hook_callback_clears_no_signal() -> None:
    events = [
        _event(TS0, "SPAWN_WORKER", task_id="T1"),
        _event("2026-06-28T10:01:00Z", "INSPECT", task_id="T1", hook_callback=True),
        _event(TS1, "INSPECT", task_id="T1", signal_state="idle"),
    ]
    assert hs.verify_hook_signal_trace(events, hook_capable=True) == []


def test_spawn_started_and_top_level_task_id() -> None:
    """TraceEmitter uses top-level task_id and SPAWN_WORKER status started."""
    events = [
        {
            "schema_version": "1.0",
            "ts": TS0,
            "run_id": "run-1",
            "mission": "test",
            "primitive": "SPAWN_WORKER",
            "role": "COORDINATOR",
            "status": "started",
            "task_id": "T1",
        },
        {
            "schema_version": "1.0",
            "ts": TS1,
            "run_id": "run-1",
            "mission": "test",
            "primitive": "INSPECT",
            "role": "COORDINATOR",
            "status": "succeeded",
            "task_id": "T1",
            "details": {"signal_state": "idle"},
        },
    ]
    errors = hs.verify_hook_signal_trace(events, hook_capable=True)
    assert errors
    assert "T1" in errors[0]


def test_future_callback_does_not_clear_past_inspect() -> None:
    events = [
        _event(TS0, "SPAWN_WORKER", task_id="T1"),
        _event(TS1, "INSPECT", task_id="T1", signal_state="idle"),
        _event("2026-06-28T10:05:00Z", "INSPECT", task_id="T1", hook_callback=True),
    ]
    errors = hs.verify_hook_signal_trace(events, hook_capable=True)
    assert errors
    assert "2026-06-28T10:02:00Z" in errors[0]


def test_cli_rejects_missing_target(tmp_path: Path) -> None:
    rc, out, err = _run_cli(str(tmp_path / "missing"))
    assert rc == 1
    assert "target not found" in err


def test_cli_no_trace_is_pass(tmp_path: Path) -> None:
    rc, out, err = _run_cli(str(tmp_path))
    assert rc == 0
    assert "no trace.jsonl records found" in out


def test_cli_fails_on_bad_inspect(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        "\n".join(
            [
                json.dumps(_event(TS0, "SPAWN_WORKER", task_id="T1")),
                json.dumps(_event(TS1, "INSPECT", task_id="T1", signal_state="idle")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rc, out, err = _run_cli(str(trace))
    assert rc == 1
    assert "FAIL" in err


def test_cli_disable_short_circuits() -> None:
    rc, _, err = _run_cli(env={"FLEET_DISABLE_HOOK_SIGNAL": "1"})
    assert rc == 0
    assert "DISABLED via FLEET_DISABLE_HOOK_SIGNAL" in err


def test_cli_passes_example_fixture_trace() -> None:
    fixture = REPO_ROOT / ".fleet/runs/example-fixture"
    rc, out, err = _run_cli(str(fixture))
    assert rc == 0
    assert "1 trace file(s) checked" in out
    assert err == ""


def test_cli_writes_summary_out(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        json.dumps(_event(TS0, "SPAWN_WORKER", task_id="T1", hook_callback=True)) + "\n",
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"
    rc, _, _ = _run_cli(str(trace), "--summary-out", str(summary))
    assert rc == 0
    assert json.loads(summary.read_text())["ok"] is True


def test_cli_no_hooks_skips() -> None:
    fixture = REPO_ROOT / ".fleet/runs/example-fixture"
    rc, out, err = _run_cli(str(fixture), "--no-hooks")
    assert rc == 0
    assert "skipped" in out