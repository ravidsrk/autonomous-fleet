"""run-mission-headless.sh --dry-run must validate without invoking runtime CLIs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADLESS = ROOT / "scripts" / "run-mission-headless.sh"
VALIDATE = ROOT / "scripts" / "validate-headless.sh"
PREFLIGHT_COMMUNITY = ROOT / "scripts" / "preflight-community.sh"
RUN_CAMPAIGN = ROOT / "scripts" / "run-campaign.sh"


def test_headless_dry_run_doc_sync_grok():
    r = subprocess.run(
        [str(HEADLESS), "grok", "doc-sync", "--dry-run", "--repo", str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "grok not invoked" in r.stdout
    assert "would run:" in r.stdout
    assert "primitives (11):" in r.stdout


def test_headless_dry_run_rejects_unknown_runtime():
    r = subprocess.run(
        [str(HEADLESS), "banana", "doc-sync", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "unsupported runtime" in r.stderr


def test_validate_headless_script_passes():
    r = subprocess.run(
        [str(VALIDATE)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "all mechanical checks passed" in r.stdout


def test_preflight_community_emits_install_hint_with_isolated_home(tmp_path):
    probe_home = tmp_path / "empty-skills-home"
    probe_home.mkdir()
    env = {**os.environ, "COMMUNITY_PROBE_HOME": str(probe_home)}
    r = subprocess.run(
        [str(PREFLIGHT_COMMUNITY), "browser-qa-fix", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    combined = r.stdout + r.stderr
    assert "recommended community bundle" in combined
    assert "install-community.sh" in combined
    assert "WARN" in combined


def test_headless_dry_run_gstack_mission_surfaces_community_hints(tmp_path):
    probe_home = tmp_path / "empty-skills-home"
    probe_home.mkdir()
    env = {**os.environ, "COMMUNITY_PROBE_HOME": str(probe_home)}
    r = subprocess.run(
        [str(HEADLESS), "grok", "browser-qa-fix", "--dry-run", "--repo", str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    combined = r.stdout + r.stderr
    assert "install-community.sh" in combined
    assert "recommended community bundle" in combined


def test_archived_gstack_quality_preset_is_not_runnable():
    r = subprocess.run(
        [str(RUN_CAMPAIGN), "grok", "--preset", "gstack-quality", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert r.returncode != 0
    assert "campaign missing 'start'" in r.stderr


def test_headless_dry_run_external_git_repo_cleans_up(tmp_path):
    """--repo external git checkout: archive under target, removed after dry-run."""
    external = tmp_path / "external-gemoji"
    external.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=external, check=True)
    r = subprocess.run(
        [str(HEADLESS), "grok", "doc-sync", "--dry-run", "--repo", str(external)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "primitives (11):" in r.stdout
    assert f"repo:     {external.resolve()}" in r.stdout
    leftover = (
        list((external / ".fleet" / "runs").glob("*"))
        if (external / ".fleet" / "runs").is_dir()
        else []
    )
    assert leftover == [], f"expected cleanup under external repo, found {leftover}"