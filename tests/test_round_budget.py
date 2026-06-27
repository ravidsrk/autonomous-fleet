"""Tests for the review round-budget circuit-breaker verifier."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.verify_round_budget import MAX_ROUNDS, verify_round_budget  # noqa: E402


def _event(
    task_id: str | None = "T1",
    *,
    primitive: str = "INSPECT",
    role: str = "REVIEWER",
    status: str = "failed",
) -> dict[str, str]:
    event = {
        "schema_version": "1.0",
        "ts": "2026-06-24T00:00:00Z",
        "run_id": "20260624T000000Z-doc-sync-abcdef",
        "mission": "doc-sync",
        "primitive": primitive,
        "role": role,
        "status": status,
    }
    if task_id is not None:
        event["task_id"] = task_id
    return event


def _failed_review_rounds(task_id: str, count: int) -> list[dict[str, str]]:
    return [_event(task_id) for _ in range(count)]


def _write_trace(run_dir: Path, events: list[dict[str, str]]) -> Path:
    run_dir.mkdir()
    trace_path = run_dir / "trace.jsonl"
    trace_path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    return trace_path


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "verify_round_budget_cli",
        REPO_ROOT / "scripts" / "verify_round_budget.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*argv: str) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    sys.argv = ["verify_round_budget.py", *argv]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main()
    finally:
        sys.argv = old_argv
    return rc, out.getvalue(), err.getvalue()


def test_two_failed_review_rounds_then_merge_succeeded_passes() -> None:
    events = [
        _event(None, role="COORDINATOR", status="succeeded"),
        *_failed_review_rounds("T1", 2),
        _event("T1", primitive="MERGE", role="INTEGRATOR", status="succeeded"),
    ]

    summary = verify_round_budget(events)

    assert summary["ok"] is True
    assert summary["max_rounds"] == MAX_ROUNDS
    assert summary["checked_tasks"] == 1
    assert summary["tasks"]["T1"]["failed_rounds"] == 2
    assert summary["tasks"]["T1"]["merge_succeeded"] is True
    assert summary["violations"] == []


def test_four_failed_review_rounds_then_merge_without_blocked_fails() -> None:
    events = [
        *_failed_review_rounds("T-critical", 4),
        _event("T-critical", primitive="MERGE", role="INTEGRATOR", status="succeeded"),
    ]

    summary = verify_round_budget(events)

    assert summary["ok"] is False
    assert summary["violations"] == [
        {
            "task_id": "T-critical",
            "rounds": 4,
            "message": "T-critical ran 4 review rounds then MERGED without BLOCKED",
        }
    ]


def test_four_failed_review_rounds_then_goal_blocked_terminal_passes() -> None:
    events = [
        *_failed_review_rounds("T-blocked", 4),
        _event("T-blocked", primitive="GOAL_BLOCKED", role="COORDINATOR", status="blocked"),
    ]

    summary = verify_round_budget(events)

    assert summary["ok"] is True
    assert summary["tasks"]["T-blocked"]["terminal"] == ("GOAL_BLOCKED", "blocked")


def test_over_budget_without_terminal_blocked_fails() -> None:
    summary = verify_round_budget(_failed_review_rounds("T-stuck", 4))

    assert summary["ok"] is False
    assert summary["violations"][0]["message"] == (
        "T-stuck ran 4 review rounds without terminal BLOCKED"
    )


def test_cli_passes_for_valid_trace(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_trace(
        run_dir,
        [
            *_failed_review_rounds("T1", 4),
            _event("T1", primitive="GOAL_BLOCKED", role="COORDINATOR", status="blocked"),
        ],
    )

    rc, out, err = _run_cli(str(run_dir))

    assert rc == 0
    assert out == "verify-round-budget: 1 tasks checked; 0 violations\n"
    assert err == ""


def test_cli_fails_for_violating_trace(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_trace(
        run_dir,
        [
            *_failed_review_rounds("T9", 4),
            _event("T9", primitive="MERGE", role="INTEGRATOR", status="succeeded"),
        ],
    )

    rc, out, err = _run_cli(str(run_dir))

    assert rc == 1
    assert out == "verify-round-budget: 1 tasks checked; 1 violations\n"
    assert "T9 ran 4 review rounds then MERGED without BLOCKED" in err


def test_cli_rejects_missing_inputs(tmp_path: Path) -> None:
    rc_missing_dir, _, err_missing_dir = _run_cli(str(tmp_path / "missing"))
    assert rc_missing_dir == 1
    assert "not a directory" in err_missing_dir

    empty_run = tmp_path / "empty-run"
    empty_run.mkdir()
    rc_missing_trace, _, err_missing_trace = _run_cli(str(empty_run))
    assert rc_missing_trace == 1
    assert "trace file not found" in err_missing_trace


def test_cli_kill_switch_short_circuits_before_argparse(monkeypatch) -> None:
    monkeypatch.setenv("FLEET_DISABLE_ROUND_BUDGET", "1")

    rc, out, err = _run_cli("--not-a-real-arg")

    assert rc == 0
    assert out == ""
    assert "verify-round-budget: DISABLED via FLEET_DISABLE_ROUND_BUDGET=1" in err


def test_event_without_task_id_is_ignored():
    # Covers the guard that skips events lacking a valid task_id: the verifier
    # only tracks named tasks, so an event with no task_id registers no state
    # and the summary must equal that of an empty event stream.
    assert verify_round_budget([_event(None)]) == verify_round_budget([])
