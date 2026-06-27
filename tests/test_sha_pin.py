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


def test_leading_dash_branch_is_rejected() -> None:
    """A branch name that begins with a dash (e.g. '--help') is the
    option-injection vector into `git rev-parse <branch>`. The branch regex now
    requires an alphanumeric first character, so such a record is a schema
    error and never reaches the git argv. The head_resolver must not run."""
    def explode(branch: str) -> str:
        raise AssertionError("head_resolver must not run for a rejected branch")

    for bad in ("--help", "-x", "--upload-pack=evil", ".hidden", "/abs", "-"):
        errors = sp.verify_sha_pin([_record(branch=bad)], explode)
        assert errors, bad
        assert any("branch must match" in e for e in errors), (bad, errors)
        assert any(repr(bad) in e for e in errors), (bad, errors)


def test_branch_pattern_requires_alphanumeric_first_char() -> None:
    """Pin the exact tightened pattern and its first-char anchor."""
    assert sp._BRANCH_PATTERN == r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*$"
    assert sp._BRANCH_RE.match("fleet/sha-pin")
    assert sp._BRANCH_RE.match("a")
    assert sp._BRANCH_RE.match("9-release.x")
    assert not sp._BRANCH_RE.match("-leading")
    assert not sp._BRANCH_RE.match(".dot")
    assert not sp._BRANCH_RE.match("")


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


def test_cli_disable_without_ack_fails_closed() -> None:
    """SHA-pin is a security gate, not an escape-hatch quality gate. A bare
    FLEET_DISABLE_SHA_PIN=1 with no operator override must FAIL CLOSED so a
    stray env var in CI cannot silently drop the integrity check."""
    rc, out, err = _run_cli(env={"FLEET_DISABLE_SHA_PIN": "1"})
    assert rc == 1
    assert out == ""
    assert "REFUSING to disable a security check" in err
    assert "FLEET_SECURITY_OVERRIDE_ACK=1" in err
    # It must NOT print the escape-hatch no-op notice — that would imply PASS.
    assert "no-op exit 0" not in err


def test_cli_disable_with_ack_short_circuits_before_argparse() -> None:
    """With the explicit operator override acked, the disable is honored: the
    CLI no-ops to exit 0 with the standard notice, short-circuiting BEFORE
    argparse (no positional target supplied)."""
    rc, out, err = _run_cli(
        env={"FLEET_DISABLE_SHA_PIN": "1", "FLEET_SECURITY_OVERRIDE_ACK": "1"}
    )
    assert rc == 0
    assert out == ""
    assert "SHA-pin: DISABLED via FLEET_DISABLE_SHA_PIN=1 (no-op exit 0)" in err


def test_cli_disable_unset_runs_normally(tmp_path: Path) -> None:
    """Counterfactual: with the disable knob falsy, the security gate runs.
    Pointing at a nonexistent target makes main() reach its normal
    target-not-found exit (1), proving neither the fail-closed branch nor the
    no-op branch short-circuited a normally-enabled run."""
    rc, out, err = _run_cli(
        str(tmp_path / "missing"),
        "--repo",
        str(tmp_path),
        env={"FLEET_DISABLE_SHA_PIN": "0"},
    )
    assert rc == 1
    assert "target not found" in err
    assert "REFUSING to disable a security check" not in err
    assert "no-op exit 0" not in err


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


def test_git_head_resolves_real_branch_with_end_of_options(git_repo: Path) -> None:
    """The hardened argv (`rev-parse --verify --end-of-options <branch>`) must
    still resolve a legitimate branch to its single HEAD SHA — proving the
    option-parsing guard didn't break normal resolution."""
    cli = _load_cli()
    head = _commit(git_repo, "a.txt", "one\n")
    assert cli._git_head(git_repo, "fleet/sha-pin") == head


def test_git_head_uses_end_of_options_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Pin the exact rev-parse argv: option parsing must be terminated before
    the branch so a crafted name can never be read as a git option."""
    cli = _load_cli()
    captured: dict[str, list[str]] = {}

    class Result:
        returncode = 0
        stdout = "deadbeef\n"

    def fake_run(argv, *args, **kwargs):
        captured["argv"] = argv
        return Result()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    assert cli._git_head(tmp_path, "fleet/x") == "deadbeef"
    argv = captured["argv"]
    assert argv[:4] == ["git", "-C", str(tmp_path), "rev-parse"]
    assert "--verify" in argv
    assert "--end-of-options" in argv
    # The branch is the final arg, AFTER the option-terminator.
    assert argv[-1] == "fleet/x"
    assert argv.index("--end-of-options") < len(argv) - 1


def test_git_head_injection_branch_does_not_leak_option(git_repo: Path) -> None:
    """Defense-in-depth at the git layer: even if an option-like name reached
    `_git_head` directly (bypassing the lib regex), `--end-of-options` plus
    `--verify` makes rev-parse fail rather than honor it as an option, so the
    result is None (treated as unknown branch) — never an executed option."""
    cli = _load_cli()
    _commit(git_repo, "a.txt", "one\n")
    assert cli._git_head(git_repo, "--upload-pack=evil") is None
    assert cli._git_head(git_repo, "--help") is None
