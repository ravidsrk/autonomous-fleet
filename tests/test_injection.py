"""Prove malicious mission values cannot execute code via driver scripts."""

from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import uuid
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


def _shell_meta_payload() -> tuple[str, Path]:
    """Build a mission string of the form ``<valid-prefix>; touch <marker>``.

    Returns (mission_string, marker_path). The prefix is a real registered
    mission so the payload pinpoints the metachar-handling boundary rather than
    the validity check. Marker is an absolute path under the system temp dir
    keyed by a uuid so concurrent runs don't collide.
    """
    marker = Path(tempfile.gettempdir()) / f"fleet_pwn_marker_{uuid.uuid4().hex}"
    mission = f"doc-sync; touch {marker}"
    return mission, marker


def test_headless_rejects_shell_metachar_mission_and_no_exec():
    """M3c: passing a known-valid mission name with appended shell metacharacters
    to run-mission-headless.sh must be rejected as an unknown mission AND must
    not execute the appended ``touch`` (proving no shell evaluation of $MISSION).
    """
    mission, marker = _shell_meta_payload()
    assert not marker.exists(), f"precondition: marker should not exist at {marker}"
    try:
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
        # The whole concatenated string is not a known mission, so the script
        # must exit non-zero and say "unknown mission".
        assert r.returncode != 0, r.stdout
        assert "unknown mission" in (r.stderr + r.stdout).lower(), (
            f"expected 'unknown mission' rejection; stderr={r.stderr!r} stdout={r.stdout!r}"
        )
        # Critical: the shell must not have evaluated the metacharacters.
        assert not os.path.exists(marker), (
            f"shell injection succeeded: marker created at {marker}"
        )
    finally:
        # Defensive cleanup in case a future regression DOES create it; we want
        # the test to still fail loudly above, but not litter /tmp.
        if marker.exists():
            marker.unlink()


def test_campaign_dry_run_rejects_shell_metachar_mission_and_no_exec(tmp_path: Path):
    """M3c: the same shell-metachar payload routed through run-campaign.sh (via
    a campaign YAML whose start node names that mission) must be rejected with
    a non-zero exit and the marker file must NOT exist after the run.
    """
    mission, marker = _shell_meta_payload()
    campaign = tmp_path / "shellmeta.yaml"
    campaign.write_text(
        textwrap.dedent(
            f"""\
            campaign: shellmeta
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
    assert not marker.exists(), f"precondition: marker should not exist at {marker}"
    try:
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
        assert r.returncode != 0, r.stdout
        assert "unknown mission" in (r.stderr + r.stdout).lower(), (
            f"expected 'unknown mission' rejection; stderr={r.stderr!r} stdout={r.stdout!r}"
        )
        assert not os.path.exists(marker), (
            f"shell injection succeeded via campaign driver: marker created at {marker}"
        )
    finally:
        if marker.exists():
            marker.unlink()


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
    # A genuine runaway loop still aborts (designed back-edges are allowed a small revisit budget,
    # but an unconditional a<->b cycle exhausts it / hits the step cap).
    assert r.returncode != 0
    assert ("revisited too many times" in r.stderr) or ("step limit exceeded" in r.stderr)


def test_campaign_tight_cycle_trips_revisit_budget_before_step_limit(tmp_path: Path):
    campaign = tmp_path / "tight-cycle.yaml"
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
    assert "revisited too many times (budget 3)" in r.stderr
    assert "step limit exceeded" not in r.stderr
