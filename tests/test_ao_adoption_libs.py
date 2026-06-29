"""Branch-coverage tests for AO mechanism port libraries."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import hook_signal as hs  # noqa: E402
from lib import nudge_dedup as nd  # noqa: E402
from lib import stacked_pr_status as sp  # noqa: E402
from lib import verify_sha_pin as vsp  # noqa: E402

SHA = "a" * 40


def test_nudge_state_schema_branches() -> None:
    assert "top-level must be an object" in nd.validate_nudge_state([])[0]
    bad = {
        "schema_version": "9",
        "pr_url": "  ",
        "entries": "nope",
        "extra": True,
    }
    joined = "\n".join(nd.validate_nudge_state(bad))
    assert "schema_version must be" in joined
    assert "pr_url must be" in joined
    assert "entries must be an array" in joined
    assert "additional property" in joined

    entry_errors = nd.validate_nudge_state(
        {
            "schema_version": "1.0",
            "pr_url": "https://x/pull/1",
            "entries": [
                "bad",
                {"kind": "nope", "signature": "", "attempts": -1, "commit_sha": "x", "junk": 1},
            ],
        }
    )
    joined = "\n".join(entry_errors)
    assert "must be an object" in joined
    assert "missing required field" in joined
    assert "kind must be one of" in joined
    assert "signature must be" in joined
    assert "attempts must be" in joined
    assert "commit_sha must be" in joined
    assert "additional property" in joined


def test_should_send_ci_has_no_cap() -> None:
    state = nd.record_nudge(
        {"schema_version": "1.0", "pr_url": "u", "entries": []},
        key="ci:x",
        kind="ci",
        signature="a",
    )
    assert nd.should_send_nudge(state, key="ci:x", signature="b", kind="ci")


def test_record_nudge_updates_existing_key() -> None:
    state = {
        "schema_version": "1.0",
        "pr_url": "u",
        "entries": [{"key": "k", "kind": "ci", "signature": "a", "attempts": 1}],
    }
    updated = nd.record_nudge(
        state, key="k", kind="review", signature="b", commit_sha=SHA, max_attempts=3
    )
    entry = updated["entries"][0]
    assert entry["kind"] == "review"
    assert entry["attempts"] == 2
    assert entry["commit_sha"] == SHA


def test_stacked_pr_pipeline_and_aggregate_branches() -> None:
    assert sp.pr_pipeline_status({"draft": True}) == "draft"
    assert sp.pr_pipeline_status({"review_comments": True}) == "changes_requested"
    assert sp.pr_pipeline_status({"review": "approved"}) == "approved"
    assert sp.pr_pipeline_status({"review": "required"}) == "review_pending"
    assert sp.pr_pipeline_status({}) == "pr_open"
    assert sp.aggregate_pr_status([{"merged": True, "url": "u", "source_branch": "a", "target_branch": "main"}]) == "merged"
    assert sp.aggregate_pr_status([]) == "idle"
    assert sp.is_actionable_child_signal("mergeable") is False

    prs = [
        {
            "url": "p1",
            "source_branch": "fleet/p",
            "target_branch": "main",
            "review": "required",
        },
        {
            "url": "p2",
            "source_branch": "fleet/c",
            "target_branch": "fleet/p",
            "mergeability": "mergeable",
        },
    ]
    assert sp.aggregate_pr_status(prs) == "review_pending"


def test_stacked_pr_snapshot_validation_and_conflict_nudge() -> None:
    assert sp.validate_pr_snapshot("x")[0].endswith("must be an array")
    assert any("must be an object" in e for e in sp.validate_pr_snapshot([1]))
    assert any("missing required field" in e for e in sp.validate_pr_snapshot([{}]))
    assert any("url must be" in e for e in sp.validate_pr_snapshot([{"url": " ", "source_branch": "a", "target_branch": "b"}]))

    pr = {
        "url": "u",
        "source_branch": "a",
        "target_branch": "main",
        "mergeability": "conflicting",
        "nudge_merge_conflict": False,
    }
    errors = sp.verify_stacked_pr_consistency([pr])
    assert any("nudge_merge_conflict=true" in e for e in errors)


def test_hook_signal_branches() -> None:
    assert hs.first_hook_signal_at([{"ts": "2026-01-01T00:00:00Z", "details": {"activity_state": "active"}}])
    assert hs.spawn_or_restore_at([], "T") is None
    spawn = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert hs.derive_signal_status(
        spawn_at=spawn,
        now=spawn + timedelta(seconds=10),
        first_signal_at=None,
        hook_capable=False,
    ) == "idle"
    events = [
        {
            "schema_version": "1.0",
            "ts": "2026-01-01T00:00:00Z",
            "primitive": "SPAWN_WORKER",
            "status": "succeeded",
            "details": {"task_id": "T2"},
        }
    ]
    assert hs.verify_hook_signal_trace(events, hook_capable=False) == []


def test_sha_pin_supersede_schema_fields() -> None:
    errors = vsp.validate_sha_pin_record(
        {
            "schema_version": "1.0",
            "review_id": "r",
            "reviewed_sha": SHA,
            "branch": "fleet/x",
            "verdict": "approve",
            "superseded": "yes",
            "supersedes_review_id": "bad id",
        }
    )
    assert any("superseded must be boolean" in e for e in errors)
    assert any("supersedes_review_id must match" in e for e in errors)


def test_remaining_nudge_dedup_branches() -> None:
    assert any("missing required field" in e for e in nd.validate_nudge_state({}))
    assert any("max_attempts must be" in e for e in nd.validate_nudge_state(
        {
            "schema_version": "1.0",
            "pr_url": "u",
            "entries": [{"key": "k", "kind": "ci", "signature": "s", "attempts": 1, "max_attempts": -1}],
        }
    ))
    state = {
        "schema_version": "1.0",
        "pr_url": "u",
        "entries": [{"key": "review:x", "kind": "review", "signature": "a", "attempts": 3}],
    }
    assert nd.should_send_nudge(state, key="review:x", signature="b", kind="review") is False
    other_key = {
        "schema_version": "1.0",
        "pr_url": "u",
        "entries": [{"key": "other", "kind": "ci", "signature": "a", "attempts": 1}],
    }
    assert nd.should_send_nudge(other_key, key="review:x", signature="b", kind="review") is True
    fresh = nd.record_nudge(
        {"schema_version": "1.0", "pr_url": "u", "entries": []},
        key="new",
        kind="merge_conflict",
        signature="sig",
    )
    assert fresh["entries"][0]["key"] == "new"
    assert nd.verify_nudge_state_invariants({"bad": True})


def test_record_nudge_skips_non_matching_entry() -> None:
    state = {
        "schema_version": "1.0",
        "pr_url": "u",
        "entries": [
            {"key": "keep", "kind": "ci", "signature": "a", "attempts": 1},
            {"key": "target", "kind": "ci", "signature": "b", "attempts": 2},
        ],
    }
    updated = nd.record_nudge(state, key="target", kind="review", signature="c")
    assert updated["entries"][0]["signature"] == "a"
    assert updated["entries"][1]["attempts"] == 3


def test_record_nudge_new_entry_with_commit_sha_only() -> None:
    updated = nd.record_nudge(
        {"schema_version": "1.0", "pr_url": "u", "entries": []},
        key="k",
        kind="ci",
        signature="sig",
        commit_sha=SHA,
    )
    assert updated["entries"][0]["commit_sha"] == SHA


def test_aggregate_fallback_when_all_suppressed() -> None:
    prs = [
        {"url": "p1", "source_branch": "a", "target_branch": "main"},
        {"url": "p2", "source_branch": "b", "target_branch": "a"},
    ]
    stacks = {
        "p1": {"blocked": True, "bottom_of_stack": False},
        "p2": {"blocked": True, "bottom_of_stack": False},
    }
    with patch.object(sp, "build_stacks", return_value=stacks):
        with patch.object(sp, "pr_pipeline_status", return_value="mergeable"):
            assert sp.aggregate_pr_status(prs) == "mergeable"


def test_remaining_stacked_pr_branches() -> None:
    prs = [
        {"url": "p1", "source_branch": "fleet/p", "target_branch": "main", "mergeability": "mergeable"},
        {"url": "p2", "source_branch": "fleet/c", "target_branch": "fleet/p", "mergeability": "mergeable"},
    ]
    assert sp.aggregate_pr_status(prs) == "mergeable"
    assert sp.should_nudge_merge_conflict({"url": "u", "mergeability": "ok"}, {}) is False
    child = {
        "url": "p2",
        "source_branch": "fleet/c",
        "target_branch": "fleet/p",
        "mergeability": "conflicting",
    }
    assert sp.verify_stacked_pr_consistency([child, {"url": "p1", "source_branch": "fleet/p", "target_branch": "main"}]) == []
    assert sp.verify_stacked_pr_consistency("bad")  # schema early return


def test_remaining_hook_signal_branches() -> None:
    events = [
        {
            "ts": "2026-01-01T00:00:00Z",
            "primitive": "CONTINUE_WORKER",
            "status": "succeeded",
            "details": {"task_id": "T"},
        },
        {
            "ts": "2026-01-01T00:01:00Z",
            "primitive": "SPAWN_WORKER",
            "status": "succeeded",
            "details": {"task_id": "OTHER"},
        },
        {
            "ts": "2026-01-01T00:02:00Z",
            "primitive": "WAIT",
            "status": "succeeded",
            "details": {"task_id": "T"},
        },
    ]
    assert hs.spawn_or_restore_at(events, "T") is not None
    spawn = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert hs.derive_signal_status(
        spawn_at=spawn,
        now=spawn + timedelta(seconds=30),
        first_signal_at=spawn + timedelta(seconds=5),
        hook_capable=True,
    ) == "idle"
    assert hs.derive_signal_status(
        spawn_at=spawn,
        now=spawn + timedelta(seconds=10),
        first_signal_at=None,
        hook_capable=True,
    ) == "idle"
    trace = [
        {
            "schema_version": "1.0",
            "ts": "2026-01-01T00:00:00Z",
            "primitive": "SPAWN_WORKER",
            "status": "succeeded",
            "details": {"task_id": "T1"},
        },
        {
            "schema_version": "1.0",
            "ts": "2026-01-01T00:05:00Z",
            "primitive": "INSPECT",
            "status": "succeeded",
            "details": {"task_id": "T2", "signal_state": "idle"},
        },
    ]
    assert hs.verify_hook_signal_trace(trace) == []


def test_supersede_skips_non_string_branch() -> None:
    records = [{"verdict": "approve", "branch": 123, "reviewed_sha": SHA}]
    assert vsp.verify_review_supersede(records) == []


def test_nudge_cli_summary_out(tmp_path: Path) -> None:
    import importlib.util
    import io
    import os
    from contextlib import redirect_stderr, redirect_stdout

    spec = importlib.util.spec_from_file_location(
        "verify_nudge_dedup_cli",
        REPO_ROOT / "scripts/verify_nudge_dedup.py",
    )
    assert spec and spec.loader
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "nudge-state.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "pr_url": "https://github.com/o/r/pull/1",
                "entries": [
                    {"key": "k", "kind": "ci", "signature": "s", "attempts": 1},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_env = sys.argv, os.environ.copy()
    sys.argv = ["verify_nudge_dedup.py", str(run_dir), "--summary-out", str(summary)]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            assert cli.main() == 0
    finally:
        sys.argv = old_argv
        os.environ.clear()
        os.environ.update(old_env)
    assert json.loads(summary.read_text())["ok"] is True