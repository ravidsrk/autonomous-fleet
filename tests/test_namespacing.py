"""Tests for hash-namespaced branch/worktree validation."""
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
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import namespace as ns  # noqa: E402

RUN_ID = "20260623T141522Z-m-3a9c2f"
RUN_ID_2 = "20260623T141522Z-m-aabbcc"


def _manifest(run_id: str = RUN_ID, progress_path: str = "progress.md") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "mission": "m",
        "files": [
            {"path": "notes.txt", "kind": "other"},
            {"path": progress_path, "kind": "progress"},
        ],
    }


def _ledger(branch: str, worktree: str | None = None) -> str:
    wt = f" | WT={worktree}" if worktree is not None else ""
    return f"TASK T-auth | BRANCH={branch}{wt} | MERGED=false\n"


def _archive(tmp_path: Path, ledger_text: str, manifest: dict[str, object] | None = None) -> Path:
    archive = tmp_path / "archive"
    archive.mkdir()
    payload = manifest or _manifest()
    (archive / "manifest.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    (archive / "progress.md").write_text(ledger_text, encoding="utf-8")
    return archive


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "validate_namespacing_cli",
        REPO_ROOT / "scripts" / "validate_namespacing.py",
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
    sys.argv = ["validate_namespacing.py", *argv]
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


def test_acceptance_namespace_helpers() -> None:
    assert ns.derive_run_short(RUN_ID) == "3a9c2f"
    assert ns.namespaced_branch("fleet/", "auth-fix", RUN_ID) == "fleet/auth-fix-3a9c2f"
    assert ns.namespaced_worktree("repo", "auth-fix", RUN_ID) == "../repo-auth-fix-3a9c2f"
    assert ns.namespaced_branch("fleet/", "auth-fix", RUN_ID) != ns.namespaced_branch(
        "fleet/", "auth-fix", RUN_ID_2
    )


def test_acceptance_validator_rejects_bare_branch_and_accepts_suffixed() -> None:
    bare_errors = ns.validate_archive_namespacing(
        _manifest(),
        {"progress.md": _ledger("fleet/auth-fix", "../repo-auth-fix")},
    )
    ok_errors = ns.validate_archive_namespacing(
        _manifest(),
        {"progress.md": _ledger("fleet/auth-fix-3a9c2f", "../repo-auth-fix-3a9c2f/")},
    )

    assert "branch 'fleet/auth-fix' must end with '-3a9c2f'" in bare_errors[0]
    assert "worktree '../repo-auth-fix' must end with '-3a9c2f'" in bare_errors[1]
    assert ok_errors == []
    assert ns.validate_ledger_namespacing(
        RUN_ID,
        "TASK T-hyphen | BRANCH=fleet/hyphen-3a9c2f | WORKTREE-PATH=../repo-hyphen\n",
    ) == [
        "progress ledger: TASK T-hyphen worktree '../repo-hyphen' must end with '-3a9c2f'"
    ]


def test_manifest_shape_errors_and_missing_ledger_are_reported() -> None:
    assert ns.progress_paths_from_manifest([], "bad") == (
        None,
        [],
        ["bad: manifest must be an object"],
    )

    run_id, paths, errors = ns.progress_paths_from_manifest(
        {
            "run_id": "not-a-run-id",
            "files": [
                [],
                {"kind": "other", "path": "x"},
                {"kind": "progress", "path": ""},
            ],
        },
        "bad",
    )
    assert run_id == "not-a-run-id"
    assert paths == []
    assert errors == [
        "bad: run_id must end with a 6-hex suffix, got 'not-a-run-id'",
        "bad.files[0]: file entry must be an object",
        "bad.files[2]: progress entry path must be a string",
    ]

    assert ns.progress_paths_from_manifest({"run_id": RUN_ID, "files": "nope"}, "bad") == (
        RUN_ID,
        [],
        ["bad: files must be a list"],
    )
    assert ns.progress_paths_from_manifest({"files": []}, "bad") == (
        None,
        [],
        ["bad: run_id must be a string"],
    )
    assert ns.validate_archive_namespacing({"run_id": 7, "files": []}, {}) == [
        "manifest: run_id must be a string"
    ]
    assert ns.validate_archive_namespacing(_manifest(), {}) == [
        "progress.md: progress ledger not provided"
    ]


def test_invalid_run_id_rejected() -> None:
    with pytest.raises(ValueError, match="run_id must end"):
        ns.derive_run_short("20260623T141522Z-m-nothex")


def test_cli_accepts_suffixed_archive_from_default_scan(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    run_dir = root / ".fleet" / "runs" / RUN_ID
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps(_manifest()) + "\n", encoding="utf-8")
    (run_dir / "progress.md").write_text(
        _ledger("fleet/auth-fix-3a9c2f", "../repo-auth-fix-3a9c2f"),
        encoding="utf-8",
    )

    rc, out, err = _run_cli("--repo-root", str(root))

    assert rc == 0
    assert out == f"OK   {run_dir}\n"
    assert err == ""


def test_cli_rejects_bare_branch(tmp_path: Path) -> None:
    archive = _archive(tmp_path, _ledger("fleet/auth-fix"))

    rc, out, err = _run_cli(str(archive))

    assert rc == 1
    assert out == ""
    assert f"FAIL {archive}" in err
    assert "branch 'fleet/auth-fix' must end with '-3a9c2f'" in err


def test_cli_kill_switch_requires_security_ack() -> None:
    """Fail-closed class (issue #85 / codex on PR #117): a bare truthy knob
    must NOT drop the check without the explicit security acknowledgement."""
    rc, out, err = _run_cli(
        "--not-a-real-arg",
        # hermetic: an ambient ack in the operator's shell must not flip this
        env={"FLEET_DISABLE_NAMESPACING": "1", "FLEET_SECURITY_OVERRIDE_ACK": ""},
    )

    assert rc == 1
    assert "REFUSING to disable" in err


def test_cli_kill_switch_short_circuits_with_ack() -> None:
    rc, out, err = _run_cli(
        "--not-a-real-arg",
        env={"FLEET_DISABLE_NAMESPACING": "1", "FLEET_SECURITY_OVERRIDE_ACK": "1"},
    )

    assert rc == 0
    assert out == ""
    assert "validate-namespacing: DISABLED via FLEET_DISABLE_NAMESPACING=1" in err


def test_cli_no_archives_and_not_directory(tmp_path: Path) -> None:
    rc_empty, out_empty, err_empty = _run_cli("--repo-root", str(tmp_path))
    assert rc_empty == 0
    assert out_empty == "validate-namespacing: no run archives found\n"
    assert err_empty == ""

    not_dir = tmp_path / "not-dir"
    not_dir.write_text("", encoding="utf-8")
    rc_bad, out_bad, err_bad = _run_cli(str(not_dir))
    assert rc_bad == 1
    assert out_bad == ""
    assert f"FAIL {not_dir} (not a directory)" in err_bad


def test_cli_reports_manifest_and_progress_io_errors(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "missing-manifest"
    missing_manifest.mkdir()
    rc_missing, _, err_missing = _run_cli(str(missing_manifest))
    assert rc_missing == 1
    assert "cannot read manifest" in err_missing

    bad_json = tmp_path / "bad-json"
    bad_json.mkdir()
    (bad_json / "manifest.json").write_text("{not json", encoding="utf-8")
    rc_json, _, err_json = _run_cli(str(bad_json))
    assert rc_json == 1
    assert "cannot read manifest" in err_json

    escaped = tmp_path / "escaped"
    escaped.mkdir()
    (escaped / "manifest.json").write_text(
        json.dumps(_manifest(progress_path="../progress.md")) + "\n",
        encoding="utf-8",
    )
    rc_escape, _, err_escape = _run_cli(str(escaped))
    assert rc_escape == 1
    assert "progress path escapes archive" in err_escape


def test_validate_archive_path_handles_manifest_errors_and_no_progress(tmp_path: Path) -> None:
    cli = _load_cli()
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "manifest.json").write_text(
        json.dumps({"run_id": RUN_ID, "files": "nope"}) + "\n",
        encoding="utf-8",
    )
    assert cli.validate_archive_path(invalid) == [
        f"{invalid / 'manifest.json'}: files must be a list"
    ]

    no_progress = tmp_path / "no-progress"
    no_progress.mkdir()
    (no_progress / "manifest.json").write_text(
        json.dumps({"run_id": RUN_ID, "files": [{"kind": "other", "path": "x"}]}) + "\n",
        encoding="utf-8",
    )
    assert cli.validate_archive_path(no_progress) == []
