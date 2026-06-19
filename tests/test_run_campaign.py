"""Smoke test for run-campaign.sh dry-run."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-campaign.sh"


def test_repo_health_dry_run():
    r = subprocess.run(
        [str(SCRIPT), "grok", "--preset", "repo-health", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "doc-sync" in r.stdout
    assert "test-coverage" in r.stdout
    assert "cleanup" in r.stdout