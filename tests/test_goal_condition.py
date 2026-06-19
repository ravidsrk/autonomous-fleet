"""Tests for validate-goal-condition.sh logic."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "validate-goal-condition.sh"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_mission_condition():
    cond = (
        "Mission doc-sync DONE: docs/doc-sync-progress.md all flags true, "
        "docs/doc-sync-readiness.md with fleet-outcome.status done"
    )
    r = run_script("--text", cond)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_invalid_condition_missing_docs():
    r = run_script("--text", "Mission done when tests pass")
    assert r.returncode != 0
    assert "docs/" in r.stderr


def test_ledger_with_runtime_goal():
    ledger = ROOT / "docs" / "fleet-program-progress.md"
    assert ledger.exists()
    r = run_script("--ledger", str(ledger))
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"