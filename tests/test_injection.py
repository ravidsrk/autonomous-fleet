"""Prove malicious mission values cannot execute code via driver scripts."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_SCRIPT = ROOT / "scripts" / "run-campaign.sh"
HEADLESS_SCRIPT = ROOT / "scripts" / "run-mission-headless.sh"


def injection_payload(marker: Path) -> str:
    """Craft a mission that escapes old single-quoted python -c interpolation.

    If the driver still interpolates $MISSION into generated Python source, this
    closes the literal and runs ``touch`` against *marker* (an absolute path under
    the test's tmp_path). A vulnerable driver would create the file even in
    --dry-run because readiness_path() ran before the dry-run branch.
    """
    target = str(marker.resolve())
    return f"x'));__import__('os').system('touch {target}');print(('"


@pytest.fixture
def proof_marker(tmp_path: Path) -> Path:
    return tmp_path / "injected-proof"


@pytest.fixture
def evil_campaign(tmp_path: Path, proof_marker: Path) -> Path:
    mission = injection_payload(proof_marker)
    campaign = tmp_path / "evil.yaml"
    campaign.write_text(
        textwrap.dedent(
            f"""\
            campaign: evil
            start: pwn
            nodes:
              pwn:
                mission: {mission!r}
            edges:
              pwn: []
            """
        ),
        encoding="utf-8",
    )
    return campaign


def test_campaign_dry_run_rejects_malicious_mission(evil_campaign: Path, proof_marker: Path):
    """--dry-run must not execute injected Python from a crafted mission value."""
    assert not proof_marker.exists()
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
    assert r.returncode != 0, r.stdout
    assert "unknown mission" in (r.stderr + r.stdout).lower()
    assert not proof_marker.exists(), f"injection executed: marker created at {proof_marker}"


def test_headless_rejects_malicious_mission(proof_marker: Path):
    """Headless driver must reject unknown missions before building prompts."""
    mission = injection_payload(proof_marker)
    assert not proof_marker.exists()
    r = subprocess.run(
        [
            str(HEADLESS_SCRIPT),
            "grok",
            mission,
            "--repo",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0, r.stdout
    assert "unknown mission" in (r.stderr + r.stdout).lower()
    assert not proof_marker.exists(), f"injection executed: marker created at {proof_marker}"


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