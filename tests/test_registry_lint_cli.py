"""Tests for the registry-lint CLI wrapper and the missing-dir lint path.

The lib functions are exercised by tests/test_fleet_registry_consistency.py; this
file covers ``scripts/registry_lint.py`` (the thin CLI) in-process so the
repository-wide 100% coverage gate sees the wrapper, plus the
``lint_shipped_mission_dirs`` missing-dir branch with a synthetic registry.
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import registry_lint as rl  # noqa: E402


def _run_cli(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    spec = importlib.util.spec_from_file_location(
        "registry_lint_cli", REPO_ROOT / "scripts" / "registry_lint.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_env = sys.argv, os.environ.copy()
    sys.argv = ["registry_lint.py", *argv]
    if env:
        os.environ.update(env)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = mod.main()
    finally:
        sys.argv = old_argv
        os.environ.clear()
        os.environ.update(old_env)
    return rc, out.getvalue(), err.getvalue()


def test_cli_passes_on_real_repo():
    rc, _, err = _run_cli(str(REPO_ROOT))
    assert rc == 0, err


def test_cli_kill_switch_disables():
    rc, _, err = _run_cli(str(REPO_ROOT), env={"FLEET_DISABLE_REGISTRY_LINT": "1"})
    assert rc == 0
    assert "DISABLED" in err and "FLEET_DISABLE_REGISTRY_LINT" in err


def test_cli_fails_and_reports_on_empty_root(tmp_path: Path):
    # No skills/ dir at all -> every shipped mission's dir is missing -> exit 1.
    rc, _, err = _run_cli(str(tmp_path))
    assert rc == 1
    assert "registry-lint:" in err


def test_missing_shipped_dir_is_flagged(tmp_path: Path):
    # Synthetic registry: a shipped mission whose skill dir does not exist.
    missions = {"ghost": {"shipped": True, "skill_dir": "ghost-mission-xyz"}}
    errors = rl.lint_shipped_mission_dirs(tmp_path, missions)
    assert any("ghost" in e and "ghost-mission-xyz" in e for e in errors)
