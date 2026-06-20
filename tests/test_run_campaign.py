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


def test_unknown_runtime_rejected():
    """H2c: unsupported runtime values must exit non-zero before any work."""
    r = subprocess.run(
        [str(SCRIPT), "banana", "--preset", "repo-health", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "unsupported runtime" in r.stderr


def test_custom_campaign_dryrun_unknown_metric_no_traceback(tmp_path: Path):
    """M1: dry-run must not traceback when an edge references a metric
    that isn't part of the current node's mission stub.
    """
    campaign = tmp_path / "custom-gaps.yaml"
    campaign.write_text(
        "campaign: custom-gaps\n"
        "repo: single\n"
        "base: fleet/custom-base\n"
        "start: docs\n"
        "nodes:\n"
        "  docs: { mission: doc-sync }\n"
        "  tests: { mission: test-coverage }\n"
        "edges:\n"
        "  docs:\n"
        '    - { to: tests, if: "gaps_open > 0" }\n'
        "    - { to: tests, if: always }\n"
        "  tests: []\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            str(SCRIPT),
            "grok",
            "--campaign",
            str(campaign),
            "--repo",
            str(ROOT),
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    combined = r.stdout + r.stderr
    assert "Traceback" not in combined, combined