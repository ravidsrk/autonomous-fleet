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


def _build_e2e_harness(tmp_path: Path, stub_body: str, campaign: str) -> Path:
    """Copy the campaign machinery into a throwaway repo with a STUB mission runner."""
    import os
    import shutil

    e = tmp_path / "e2e"
    (e / "scripts" / "lib").mkdir(parents=True)
    (e / "scripts" / "campaigns").mkdir()
    (e / "docs").mkdir()
    for f in (
        "run-campaign.sh", "eval-campaign-edge.sh", "eval-campaign-edge.py",
        "validate-fleet-outcome.sh", "validate_fleet_outcome.py",
    ):
        shutil.copy(ROOT / "scripts" / f, e / "scripts" / f)
    for f in (ROOT / "scripts" / "lib").glob("*"):
        if f.is_file():
            shutil.copy(f, e / "scripts" / "lib" / f.name)
    (e / ".venv").symlink_to(ROOT / ".venv")
    (e / "scripts" / "campaigns" / "t.yaml").write_text(campaign)
    stub = e / "scripts" / "run-mission-headless.sh"
    stub.write_text(stub_body)
    stub.chmod(0o755)
    subprocess.run(["git", "init", "-q"], cwd=e, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.co"], cwd=e, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=e, check=True)
    (e / "README.md").write_text("# e2e\n")
    subprocess.run(["git", "add", "-A"], cwd=e, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=e, check=True)
    os.environ.pop("VIRTUAL_ENV", None)
    return e


def test_blocked_node_halts_campaign(tmp_path: Path):
    """E2E regression: a node finishing status:blocked HALTS the campaign (exit 2), not flow through.
    The D1 fix's status-read silently no-op'd by passing a str to parse_readiness (which needs a
    Path); only an end-to-end run with a genuinely blocked outcome catches it."""
    stub = (
        "#!/usr/bin/env bash\nset -euo pipefail\nMISSION=\"$2\"; shift 2\nREPO=\"\"\n"
        "while [[ $# -gt 0 ]]; do case \"$1\" in --repo) REPO=\"$2\"; shift 2;; *) shift;; esac; done\n"
        "mkdir -p \"$REPO/docs\"\n"
        "printf -- '---\\nfleet-outcome:\\n  mission: adversarial-review-and-fix\\n  status: blocked\\n"
        "  repo: r\\n  base_branch: b\\n  prs_merged: 0\\n  metrics: {p0_open: 1, p1_open: 0, "
        "findings_open: 1, ops_queue_count: 0}\\n---\\n' > \"$REPO/docs/arch-build-readiness.md\"\n"
    )
    campaign = (
        "campaign: t\nstart: audit\nnodes:\n  audit: { mission: adversarial-review-and-fix }\n"
        "  deps: { mission: dependency-update }\nedges:\n"
        "  audit: [{ to: deps, if: findings_open == 0 }]\n  deps: []\n"
    )
    e = _build_e2e_harness(tmp_path, stub, campaign)
    r = subprocess.run(
        [str(e / "scripts" / "run-campaign.sh"), "codex", "--campaign", "scripts/campaigns/t.yaml", "--repo", str(e)],
        cwd=e, capture_output=True, text=True, check=False,
    )
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "BLOCKED" in r.stderr, r.stderr
    # And it must NOT have advanced to the deps node.
    assert "node=deps" not in (r.stdout + r.stderr)