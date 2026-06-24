"""Tests for SHA-PIN enforcement.

The library stays hermetic: tests inject branch heads directly. CLI tests import
``scripts/verify_sha_pin.py`` in-process so the repository-wide 100% coverage
gate sees the new wrapper code.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = (
    REPO_ROOT / "skills" / "autonomous-fleet-core" / "assets" / "fleet-sha-pin.schema.json"
)
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import verify_sha_pin as sp  # noqa: E402

C1 = "1" * 40
C2 = "2" * 40


def _record(**overrides):
    record = {
        "schema_version": "1.0",
        "review_id": "review-1",
        "reviewed_sha": C1,
        "branch": "fleet/sha-pin",
        "verdict": "approve",
    }
    record.update(overrides)
    return record


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "verify_sha_pin_cli",
        REPO_ROOT / "scripts" / "verify_sha_pin.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    old_env = os.environ.copy()
    sys.argv = ["verify_sha_pin.py", *argv]
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


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, name: str, content: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"commit {name}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "checkout", "-b", "fleet/sha-pin")
    return repo


def test_acceptance_current_head_matches() -> None:
    assert sp.verify_sha_pin([_record()], lambda branch: C1) == []


def test_acceptance_head_moved_names_both_shas() -> None:
    errors = sp.verify_sha_pin([_record()], lambda branch: C2)
    assert errors
    assert C1 in errors[0]
    assert C2 in errors[0]
    assert "REVIEWED is OUTDATED" in errors[0]


def test_acceptance_unknown_branch_with_merged_marker_is_na() -> None:
    assert sp.verify_sha_pin([_record(merged=True)], lambda branch: None) == []


def test_unknown_branch_without_merged_marker_fails() -> None:
    errors = sp.verify_sha_pin([_record()], lambda branch: None)
    assert errors == [
        f"fleet/sha-pin: HEAD unknown for reviewed {C1} and no merged marker; "
        "cannot enforce SHA-pin"
    ]


def test_non_approved_verdict_is_schema_valid_but_skipped() -> None:
    def explode(branch: str) -> str:
        raise AssertionError("head_resolver should not run for request_changes")

    assert sp.verify_sha_pin([_record(verdict="request_changes")], explode) == []


def test_schema_errors_cover_invalid_shapes() -> None:
    invalid = {
        "schema_version": "2.0",
        "review_id": "bad id",
        "reviewed_sha": "abc",
        "branch": "bad branch",
        "verdict": "maybe",
        "merged": "yes",
        "extra": True,
    }
    errors = sp.verify_sha_pin([[], invalid], lambda branch: C1)
    joined = "\n".join(errors)
    assert "top-level must be an object" in joined
    assert "missing required field" not in joined
    assert "additional property not allowed: 'extra'" in joined
    assert "schema_version must be '1.0'" in joined
    assert "review_id must match" in joined
    assert "reviewed_sha must be a 40-hex git SHA" in joined
    assert "branch must match" in joined
    assert "verdict must be one of" in joined
    assert "merged must be boolean" in joined


def test_missing_required_fields_are_schema_errors() -> None:
    errors = sp.validate_sha_pin_record({}, label="empty")
    assert errors == [f"empty: missing required field '{field}'" for field in sp.REQUIRED_FIELDS]


def test_uppercase_reviewed_sha_matches_lowercase_head() -> None:
    assert sp.verify_sha_pin([_record(reviewed_sha="A" * 40)], lambda branch: "a" * 40) == []


def test_schema_asset_matches_lib_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == sp.SCHEMA_VERSION
    assert tuple(schema["required"]) == sp.REQUIRED_FIELDS
    assert set(schema["properties"]["verdict"]["enum"]) == sp.VALID_VERDICTS
    assert schema["properties"]["reviewed_sha"]["pattern"] == "^[0-9a-fA-F]{40}$"
    assert schema["additionalProperties"] is False


def test_cli_disable_short_circuits_before_argparse() -> None:
    rc, out, err = _run_cli(env={"FLEET_DISABLE_SHA_PIN": "1"})
    assert rc == 0
    assert out == ""
    assert "SHA-pin: DISABLED via FLEET_DISABLE_SHA_PIN=1" in err


def test_cli_rejects_bad_repo_and_missing_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    rc, out, err = _run_cli(str(target), "--repo", str(tmp_path / "missing-repo"))
    assert rc == 1
    assert out == ""
    assert "--repo not a directory" in err

    rc, out, err = _run_cli(str(tmp_path / "missing"), "--repo", str(tmp_path))
    assert rc == 1
    assert out == ""
    assert "target not found" in err


def test_cli_no_records_is_pass(tmp_path: Path) -> None:
    rc, out, err = _run_cli(str(tmp_path), "--repo", str(tmp_path))
    assert rc == 0
    assert "no sha-pin.json records found" in out
    assert err == ""


def test_cli_invalid_json_fails(tmp_path: Path) -> None:
    pin = tmp_path / "sha-pin.json"
    pin.write_text("{not json", encoding="utf-8")
    rc, out, err = _run_cli(str(pin), "--repo", str(tmp_path))
    assert rc == 1
    assert "0 record(s) checked" in out
    assert "cannot read" in err


def test_cli_passes_and_writes_summary_for_current_head(git_repo: Path, tmp_path: Path) -> None:
    c1 = _commit(git_repo, "a.txt", "one\n")
    run_dir = tmp_path / ".fleet" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "sha-pin.json").write_text(
        json.dumps(_record(reviewed_sha=c1, branch="fleet/sha-pin")) + "\n",
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"

    rc, out, err = _run_cli(str(run_dir), "--repo", str(git_repo), "--summary-out", str(summary))
    assert rc == 0
    assert "1 record(s) checked" in out
    assert err == ""
    assert json.loads(summary.read_text(encoding="utf-8")) == {
        "records": 1,
        "errors": [],
        "ok": True,
    }


def test_cli_fails_when_branch_head_moves(git_repo: Path, tmp_path: Path) -> None:
    c1 = _commit(git_repo, "a.txt", "one\n")
    c2 = _commit(git_repo, "b.txt", "two\n")
    pin = tmp_path / "sha-pin.json"
    pin.write_text(
        json.dumps(_record(reviewed_sha=c1, branch="fleet/sha-pin")) + "\n",
        encoding="utf-8",
    )

    rc, out, err = _run_cli(str(pin), "--repo", str(git_repo))
    assert rc == 1
    assert "1 record(s) checked" in out
    assert c1 in err
    assert c2 in err
    assert "force re-review" in err


def test_cli_unknown_branch_with_sibling_readiness_is_na(git_repo: Path, tmp_path: Path) -> None:
    c1 = _commit(git_repo, "a.txt", "one\n")
    run_dir = tmp_path / ".fleet" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "sha-pin.json").write_text(
        json.dumps(_record(reviewed_sha=c1, branch="fleet/deleted")) + "\n",
        encoding="utf-8",
    )
    (run_dir / "fleet-outcome.yaml").write_text(
        "---\nfleet-outcome:\n  status: done\n---\n",
        encoding="utf-8",
    )

    rc, out, err = _run_cli(str(tmp_path), "--repo", str(git_repo))
    assert rc == 0
    assert "1 record(s) checked" in out
    assert err == ""


def test_git_head_empty_stdout_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cli = _load_cli()

    class Result:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: Result())
    assert cli._git_head(tmp_path, "fleet/empty") is None
