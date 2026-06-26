"""run-mission-headless.sh --dry-run must validate without invoking runtime CLIs."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADLESS = ROOT / "scripts" / "run-mission-headless.sh"
VALIDATE = ROOT / "scripts" / "validate-headless.sh"


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