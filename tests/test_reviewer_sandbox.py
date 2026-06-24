"""Tests for reviewer-role read-only sandboxing and manifest attribution."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SANDBOX = REPO_ROOT / "scripts" / "run-sandboxed.sh"
RUN_ID = "20260624T000000Z-doc-sync-abcdef"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.reviewer_sandbox import (  # noqa: E402
    ALLOWED_REVIEWER_KINDS,
    WRITE_ATTRIBUTION_KINDS,
    detect_reviewer_producers,
    verify_reviewer_sandbox_manifest,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "tracked_file.py").write_text("old\n", encoding="utf-8")
    _git(repo, "add", "tracked_file.py")
    _git(repo, "commit", "-m", "init")
    return repo


def _sandbox_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
    }


def _fallback_only_path(tmp_path: Path) -> str:
    bin_dir = tmp_path / "fallback-bin"
    bin_dir.mkdir()
    for name in (
        "awk",
        "bash",
        "cmp",
        "diff",
        "env",
        "git",
        "grep",
        "mkdir",
        "mktemp",
        "printf",
        "rm",
        "sed",
        "sh",
        "shasum",
        "sha256sum",
        "sort",
        "tr",
        "xargs",
    ):
        found = shutil.which(name)
        if found is None:
            continue
        link = bin_dir / name
        if not link.exists():
            os.symlink(found, link)
    return str(bin_dir)


def _manifest(*files: dict[str, object], **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "mission": "doc-sync",
        "candidate_branch": "fleet/candidate",
        "created_utc": "2026-06-24T00:00:00Z",
        "files": list(files),
    }
    payload.update(overrides)
    return payload


def _entry(
    *,
    kind: str = "findings",
    producer: str = "p0-reviewer-codex",
    path: str = "p0-review-findings.json",
    branch: str | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "path": path,
        "kind": kind,
        "producer": producer,
        "sha256": "0" * 64,
        "mtime_utc": "2026-06-24T00:01:00Z",
        "bytes": 1,
    }
    if branch is not None:
        entry["branch"] = branch
    return entry


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "verify_reviewer_sandbox_cli",
        REPO_ROOT / "scripts" / "verify_reviewer_sandbox.py",
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
    sys.argv = ["verify_reviewer_sandbox.py", *argv]
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


def test_run_sandboxed_role_reviewer_blocks_tracked_file_write(
    git_repo: Path, tmp_path: Path
) -> None:
    tracked = git_repo / "tracked_file.py"
    cmd = f"echo x > {shlex.quote(str(tracked))}"

    result = subprocess.run(
        [str(SANDBOX), "--role", "reviewer", "--run-id", RUN_ID, "--", "sh", "-c", cmd],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=False,
        env=_sandbox_env(tmp_path),
    )

    assert result.returncode != 0
    assert tracked.read_text(encoding="utf-8") == "old\n"


def test_run_sandboxed_role_reviewer_allows_run_tmp_and_test_output(
    git_repo: Path, tmp_path: Path
) -> None:
    command = (
        'echo run > "$FLEET_RUN_DIR/out.txt"; '
        'echo tmp > "$TMPDIR/tmp.txt"; '
        'echo test > "$FLEET_TEST_OUTPUT_DIR/out.txt"'
    )

    result = subprocess.run(
        [str(SANDBOX), "--role", "reviewer", "--run-id", RUN_ID, "--", "sh", "-c", command],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=False,
        env=_sandbox_env(tmp_path),
    )

    run_dir = git_repo / ".fleet" / "runs" / RUN_ID
    assert result.returncode == 0, result.stderr
    assert (run_dir / "out.txt").read_text(encoding="utf-8") == "run\n"
    assert (run_dir / "tmp" / "tmp.txt").read_text(encoding="utf-8") == "tmp\n"
    assert (run_dir / "test-output" / "out.txt").read_text(encoding="utf-8") == "test\n"


def test_run_sandboxed_fallback_detects_untracked_file_write(
    git_repo: Path, tmp_path: Path
) -> None:
    env = {**_sandbox_env(tmp_path), "PATH": _fallback_only_path(tmp_path)}

    result = subprocess.run(
        [
            str(SANDBOX),
            "--role",
            "reviewer",
            "--run-id",
            RUN_ID,
            "--",
            "sh",
            "-c",
            "printf new > untracked.txt",
        ],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 4
    assert "tracked/untracked files outside .fleet/runs" in result.stderr
    assert (git_repo / "untracked.txt").read_text(encoding="utf-8") == "new"


def test_clean_reviewer_manifest_passes() -> None:
    summary = verify_reviewer_sandbox_manifest(
        _manifest(
            _entry(kind="blind_fix", path="reviewer-blind-fix-F1.md"),
            _entry(kind="findings"),
            _entry(kind="verify_summary", path="verify.json"),
            _entry(kind="diff", producer="builder", path="patch.diff"),
        )
    )

    assert summary["ok"] is True
    assert summary["checked_files"] == 3
    assert summary["reviewer_producers"] == ["p0-reviewer-codex"]
    assert summary["candidate_branch"] == "fleet/candidate"
    assert summary["violations"] == []
    assert "blind_fix" in ALLOWED_REVIEWER_KINDS
    assert "diff" in WRITE_ATTRIBUTION_KINDS


def test_reviewer_diff_on_candidate_branch_is_rejected() -> None:
    summary = verify_reviewer_sandbox_manifest(
        _manifest(_entry(kind="diff", path="patch.diff", branch="fleet/candidate"))
    )

    assert summary["ok"] is False
    assert summary["violations"][0]["kind"] == "diff"
    assert "candidate branch 'fleet/candidate'" in summary["violations"][0]["message"]


def test_reviewer_commit_on_manifest_candidate_branch_is_rejected() -> None:
    summary = verify_reviewer_sandbox_manifest(
        _manifest(_entry(kind="commit", path="commit.txt"))
    )

    assert summary["ok"] is False
    assert summary["violations"][0]["kind"] == "commit"
    assert "candidate branch" in summary["violations"][0]["message"]


def test_explicit_reviewer_producer_catches_non_reviewer_slug_and_forbidden_kind() -> None:
    summary = verify_reviewer_sandbox_manifest(
        _manifest(_entry(kind="prompt", producer="skeptic-pass-gpt5", path="prompt.txt")),
        reviewer_producers=["skeptic-pass-gpt5"],
        candidate_branch="fleet/override",
    )

    assert summary["ok"] is False
    assert summary["reviewer_producers"] == ["skeptic-pass-gpt5"]
    assert summary["candidate_branch"] == "fleet/override"
    assert "forbidden kind 'prompt'" in summary["violations"][0]["message"]


def test_malformed_manifest_shapes_are_reported() -> None:
    not_object = verify_reviewer_sandbox_manifest([], label="list-manifest")
    no_files = verify_reviewer_sandbox_manifest({"files": "nope"}, label="bad-files")

    assert not_object["ok"] is False
    assert "manifest must be an object" in not_object["violations"][0]["message"]
    assert no_files["ok"] is False
    assert "files must be a list" in no_files["violations"][0]["message"]
    assert detect_reviewer_producers({"files": "nope"}) == frozenset()


def test_detection_ignores_non_dict_entries_and_blank_producers() -> None:
    manifest = _manifest(
        {"producer": "  ", "kind": "findings"},
        "not-an-entry",  # type: ignore[arg-type]
        _entry(kind="findings", producer="p0-reviewer-claude"),
    )

    assert detect_reviewer_producers(manifest) == frozenset({"p0-reviewer-claude"})


def test_reviewer_diff_without_candidate_branch_falls_back_to_forbidden_kind() -> None:
    summary = verify_reviewer_sandbox_manifest(
        _manifest(
            "not-an-entry",  # type: ignore[arg-type]
            _entry(kind="diff", path="patch.diff"),
            candidate_branch=None,
        ),
        reviewer_producers=["p0-reviewer-codex"],
    )

    assert summary["ok"] is False
    assert summary["violations"][0]["kind"] == "diff"
    assert "forbidden kind 'diff'" in summary["violations"][0]["message"]


def test_cli_acceptance_rejects_reviewer_diff_and_accepts_clean_manifest(tmp_path: Path) -> None:
    bad = tmp_path / "bad-manifest.json"
    bad.write_text(
        json.dumps(_manifest(_entry(kind="diff", path="patch.diff"))) + "\n",
        encoding="utf-8",
    )
    rc_bad, out_bad, err_bad = _run_cli(str(bad), "--reviewer-producer", "p0-reviewer-codex")
    assert rc_bad == 1
    assert "1 manifest(s) checked; 1 violation(s)" in out_bad
    assert "candidate branch 'fleet/candidate'" in err_bad

    clean_run = tmp_path / "run"
    clean_run.mkdir()
    (clean_run / "manifest.json").write_text(
        json.dumps(_manifest(_entry(kind="findings"))) + "\n",
        encoding="utf-8",
    )
    rc_clean, out_clean, err_clean = _run_cli(str(clean_run))
    assert rc_clean == 0
    assert "1 manifest(s) checked; 0 violation(s)" in out_clean
    assert err_clean == ""


def test_cli_scans_repo_root_and_writes_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / ".fleet" / "runs" / RUN_ID
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(_manifest(_entry(kind="findings"))) + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "summary.json"

    rc, out, err = _run_cli(str(tmp_path), "--summary-out", str(summary_path))

    assert rc == 0
    assert "1 manifest(s) checked; 0 violation(s)" in out
    assert err == ""
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["ok"] is True
    assert summary["manifests"] == 1
    assert summary["results"][0]["checked_files"] == 1


def test_cli_missing_invalid_empty_and_disabled_paths(tmp_path: Path, monkeypatch) -> None:
    rc_missing, out_missing, err_missing = _run_cli(str(tmp_path / "missing"))
    assert rc_missing == 1
    assert out_missing == ""
    assert "target not found" in err_missing

    rc_empty, out_empty, err_empty = _run_cli(str(tmp_path))
    assert rc_empty == 0
    assert "no manifest.json files found" in out_empty
    assert err_empty == ""

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not json", encoding="utf-8")
    rc_invalid, out_invalid, err_invalid = _run_cli(str(invalid))
    assert rc_invalid == 1
    assert "1 manifest(s) checked; 1 violation(s)" in out_invalid
    assert "cannot read" in err_invalid

    non_object = tmp_path / "list.json"
    non_object.write_text("[]\n", encoding="utf-8")
    rc_non_object, _, err_non_object = _run_cli(str(non_object))
    assert rc_non_object == 1
    assert "manifest must be an object" in err_non_object

    monkeypatch.setenv("FLEET_DISABLE_REVIEWER_SANDBOX", "1")
    rc_disabled, out_disabled, err_disabled = _run_cli("--bad-arg")
    assert rc_disabled == 0
    assert out_disabled == ""
    assert "FLEET_DISABLE_REVIEWER_SANDBOX=1" in err_disabled
