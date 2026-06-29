"""Tests for PR-feedback nudge dedup (AO sendOnce port)."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "skills/autonomous-fleet-core/assets/fleet-nudge-state.schema.json"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import nudge_dedup as nd  # noqa: E402

SHA = "a" * 40


def _state(**overrides):
    record = {
        "schema_version": "1.0",
        "pr_url": "https://github.com/org/repo/pull/1",
        "entries": [],
    }
    record.update(overrides)
    return record


def _load_cli(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_verify_nudge(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    cli = _load_verify_nudge()
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_env = sys.argv, os.environ.copy()
    sys.argv = ["verify_nudge_dedup.py", *argv]
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


def _load_verify_nudge():
    return _load_cli("verify_nudge_dedup_cli", REPO_ROOT / "scripts/verify_nudge_dedup.py")


def test_should_send_when_key_missing() -> None:
    assert nd.should_send_nudge(_state(), key="review:x", signature="sig1", kind="review")


def test_should_not_resend_same_signature() -> None:
    state = nd.record_nudge(
        _state(),
        key="review:x",
        kind="review",
        signature="sig1",
    )
    assert not nd.should_send_nudge(state, key="review:x", signature="sig1", kind="review")


def test_should_send_when_signature_changes() -> None:
    state = nd.record_nudge(_state(), key="review:x", kind="review", signature="sig1")
    assert nd.should_send_nudge(state, key="review:x", signature="sig2", kind="review")


def test_review_max_attempts_enforced() -> None:
    state = _state()
    for i in range(3):
        assert nd.should_send_nudge(state, key="review:x", signature=f"sig{i}", kind="review")
        state = nd.record_nudge(state, key="review:x", kind="review", signature=f"sig{i}")
    assert not nd.should_send_nudge(state, key="review:x", signature="sig3", kind="review")


def test_verify_rejects_duplicate_keys() -> None:
    state = _state(
        entries=[
            {"key": "k", "kind": "ci", "signature": "a", "attempts": 1},
            {"key": "k", "kind": "ci", "signature": "b", "attempts": 2},
        ]
    )
    errors = nd.verify_nudge_state_invariants(state)
    assert any("duplicate key" in e for e in errors)


def test_schema_asset_matches_lib() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == nd.SCHEMA_VERSION


def test_cli_disable_short_circuits() -> None:
    rc, out, err = _run_verify_nudge(env={"FLEET_DISABLE_NUDGE_DEDUP": "1"})
    assert rc == 0
    assert "DISABLED via FLEET_DISABLE_NUDGE_DEDUP" in err


def test_cli_rejects_missing_target(tmp_path: Path) -> None:
    rc, out, err = _run_verify_nudge(str(tmp_path / "missing"))
    assert rc == 1
    assert out == ""
    assert "target not found" in err


def test_cli_invalid_json_fails(tmp_path: Path) -> None:
    path = tmp_path / "nudge-state.json"
    path.write_text("{bad", encoding="utf-8")
    rc, out, err = _run_verify_nudge(str(path))
    assert rc == 1
    assert "1 record(s) checked" in out
    assert "cannot read" in err


def test_cli_no_records_is_pass(tmp_path: Path) -> None:
    rc, out, err = _run_verify_nudge(str(tmp_path))
    assert rc == 0
    assert "no nudge-state.json records found" in out
    assert err == ""


def test_cli_fails_when_attempts_exceed_max(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "nudge-state.json").write_text(
        json.dumps(
            _state(
                entries=[
                    {
                        "key": "review:x",
                        "kind": "review",
                        "signature": "sig",
                        "attempts": 4,
                        "max_attempts": 3,
                    }
                ]
            )
        )
        + "\n",
        encoding="utf-8",
    )
    rc, out, err = _run_verify_nudge(str(run_dir))
    assert rc == 1
    assert "exceed" in err


def test_cli_validates_fixture(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "nudge-state.json").write_text(
        json.dumps(_state(
            entries=[
                {
                    "key": "ci:x",
                    "kind": "ci",
                    "signature": "sig",
                    "attempts": 1,
                    "commit_sha": SHA,
                }
            ]
        ))
        + "\n",
        encoding="utf-8",
    )
    rc, out, err = _run_verify_nudge(str(run_dir))
    assert rc == 0
    assert "1 record(s) checked" in out
    assert err == ""