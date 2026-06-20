"""Prove malicious mission values cannot execute code via driver scripts."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_SCRIPT = ROOT / "scripts" / "run-campaign.sh"
HEADLESS_SCRIPT = ROOT / "scripts" / "run-mission-headless.sh"

# Payload from adversarial audit: closes the old single-quoted python -c literal and runs shell.
MALICIOUS_MISSION = "x'));__import__('os').system('touch injected-proof');print(('"


@pytest.fixture
def evil_campaign(tmp_path: Path) -> Path:
    campaign = tmp_path / "evil.yaml"
    campaign.write_text(
        textwrap.dedent(
            f"""\
            campaign: evil
            start: pwn
            nodes:
              pwn:
                mission: {MALICIOUS_MISSION!r}
            edges:
              pwn: []
            """
        ),
        encoding="utf-8",
    )
    return campaign


@pytest.fixture
def proof_marker(tmp_path: Path) -> Path:
    return tmp_path / "injected-proof"


def test_campaign_dry_run_rejects_malicious_mission(evil_campaign: Path, proof_marker: Path):
    """--dry-run must not execute injected Python from a crafted mission value."""
    r = subprocess.run(
        [
            str(CAMPAIGN_SCRIPT),
            "grok",
            "--campaign",
            str(evil_campaign),
            "--repo",
            str(ROOT),
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "unknown mission" in (r.stderr + r.stdout).lower()
    assert not proof_marker.exists()


def test_headless_rejects_malicious_mission(proof_marker: Path):
    """Headless driver must reject unknown missions before building prompts."""
    r = subprocess.run(
        [
            str(HEADLESS_SCRIPT),
            "grok",
            MALICIOUS_MISSION,
            "--repo",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "unknown mission" in (r.stderr + r.stdout).lower()
    assert not proof_marker.exists()


def test_campaign_missing_start_errors_cleanly(tmp_path: Path):
    campaign = tmp_path / "no-start.yaml"
    campaign.write_text("nodes:\n  a:\n    mission: doc-sync\n", encoding="utf-8")
    r = subprocess.run(
        [str(CAMPAIGN_SCRIPT), "grok", "--campaign", str(campaign), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "campaign missing 'start'" in r.stderr


def test_campaign_cycle_detected(tmp_path: Path):
    campaign = tmp_path / "cycle.yaml"
    campaign.write_text(
        textwrap.dedent(
            """\
            start: a
            nodes:
              a: { mission: doc-sync }
              b: { mission: test-coverage }
            edges:
              a: [{ to: b, if: always }]
              b: [{ to: a, if: always }]
            """
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            str(CAMPAIGN_SCRIPT),
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
    assert r.returncode != 0
    assert "cycle detected" in r.stderr