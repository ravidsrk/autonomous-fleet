"""Tests for stacked-PR status aggregation (AO status.go port)."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import stacked_pr_status as sp  # noqa: E402


def _pr(**kwargs):
    base = {
        "url": "https://github.com/o/r/pull/1",
        "source_branch": "fleet/a",
        "target_branch": "main",
        "merged": False,
        "closed": False,
    }
    base.update(kwargs)
    return base


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "verify_stacked_pr_cli",
        REPO_ROOT / "scripts/verify_stacked_pr.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_env = sys.argv, os.environ.copy()
    sys.argv = ["verify_stacked_pr.py", *argv]
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


def test_build_stacks_marks_blocked_child() -> None:
    prs = [
        _pr(url="p1", source_branch="fleet/parent", target_branch="main"),
        _pr(url="p2", source_branch="fleet/child", target_branch="fleet/parent"),
    ]
    stacks = sp.build_stacks(prs)
    assert stacks["p2"]["blocked"] is True
    assert stacks["p1"]["bottom_of_stack"] is True


def test_aggregate_suppresses_child_mergeable() -> None:
    prs = [
        _pr(
            url="p1",
            source_branch="fleet/parent",
            target_branch="main",
            mergeability="mergeable",
            review="approved",
        ),
        _pr(
            url="p2",
            source_branch="fleet/child",
            target_branch="fleet/parent",
            mergeability="mergeable",
            review="approved",
        ),
    ]
    assert sp.aggregate_pr_status(prs) == "mergeable"

    # Discriminating case: the child carries a WORSE but non-actionable status
    # (review_pending, severity 3 < mergeable 6). With suppression on, the
    # parent's "mergeable" wins; if suppression is disabled, worst-wins would
    # surface "review_pending" — so this pins the suppression branch itself
    # (mutation guard: stacked-pr-child-suppression-off).
    prs_worse_child = [
        _pr(
            url="p1",
            source_branch="fleet/parent",
            target_branch="main",
            mergeability="mergeable",
            review="approved",
        ),
        _pr(
            url="p2",
            source_branch="fleet/child",
            target_branch="fleet/parent",
            review="required",
        ),
    ]
    assert sp.aggregate_pr_status(prs_worse_child) == "mergeable"


def test_aggregate_suppresses_child_worse_nonactionable_status() -> None:
    # Child's review_pending outranks parent's mergeable in worst-wins, so the
    # aggregate only stays "mergeable" if the blocked child is suppressed.
    prs = [
        _pr(
            url="p1",
            source_branch="fleet/parent",
            target_branch="main",
            mergeability="mergeable",
            review="approved",
        ),
        _pr(
            url="p2",
            source_branch="fleet/child",
            target_branch="fleet/parent",
            review="required",
        ),
    ]
    assert sp.aggregate_pr_status(prs) == "mergeable"


def test_child_ci_failure_still_surfaces() -> None:
    prs = [
        _pr(url="p1", source_branch="fleet/parent", target_branch="main", mergeability="mergeable"),
        _pr(
            url="p2",
            source_branch="fleet/child",
            target_branch="fleet/parent",
            ci="failing",
            mergeability="mergeable",
        ),
    ]
    assert sp.aggregate_pr_status(prs) == "ci_failed"


def test_verify_requires_explicit_conflict_nudge() -> None:
    prs = [
        _pr(
            url="p1",
            source_branch="fleet/a",
            target_branch="main",
            mergeability="conflicting",
        ),
    ]
    errors = sp.verify_stacked_pr_consistency(prs)
    assert errors
    assert "nudge_merge_conflict=true" in errors[0]


def test_verify_flags_blocked_child_driving_status() -> None:
    prs = [
        _pr(url="p1", source_branch="fleet/parent", target_branch="main", mergeability="mergeable"),
        _pr(
            url="p2",
            source_branch="fleet/child",
            target_branch="fleet/parent",
            mergeability="mergeable",
            reported_session_status="mergeable",
        ),
    ]
    errors = sp.verify_stacked_pr_consistency(prs)
    assert errors
    assert "blocked stacked child" in errors[0]


def test_cli_rejects_missing_target(tmp_path: Path) -> None:
    rc, out, err = _run_cli(str(tmp_path / "missing"))
    assert rc == 1
    assert "target not found" in err


def test_cli_invalid_json_fails(tmp_path: Path) -> None:
    path = tmp_path / "pr-snapshot.json"
    path.write_text("{bad", encoding="utf-8")
    rc, out, err = _run_cli(str(path))
    assert rc == 1
    assert "cannot read" in err


def test_cli_no_records_is_pass(tmp_path: Path) -> None:
    rc, out, err = _run_cli(str(tmp_path))
    assert rc == 0
    assert "no pr-snapshot.json records found" in out


def test_cli_passes_example_fixture() -> None:
    fixture = REPO_ROOT / ".fleet/runs/example-fixture"
    rc, out, err = _run_cli(str(fixture))
    assert rc == 0
    assert "1 record(s) checked" in out
    assert err == ""


def test_cli_writes_summary_out(tmp_path: Path) -> None:
    import json

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "pr-snapshot.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "prs": [
                    {
                        "url": "https://github.com/o/r/pull/1",
                        "source_branch": "a",
                        "target_branch": "main",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"
    rc, _, _ = _run_cli(str(run_dir), "--summary-out", str(summary))
    assert rc == 0
    assert json.loads(summary.read_text())["ok"] is True


def test_cli_disable_short_circuits() -> None:
    rc, _, err = _run_cli(env={"FLEET_DISABLE_STACKED_PR": "1"})
    assert rc == 0
    assert "DISABLED via FLEET_DISABLE_STACKED_PR" in err