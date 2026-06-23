"""--yolo against an external --repo is a full RCE surface; it must require explicit
acknowledgement (or running under run-sandboxed.sh). Guards run-campaign.sh and
run-mission-headless.sh."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "scripts" / "run-campaign.sh"
HEADLESS = ROOT / "scripts" / "run-mission-headless.sh"
GATE_MARK = "yolo-untrusted-acknowledged"


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.co"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "README.md").write_text("# ext\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    return path


def test_campaign_yolo_external_repo_blocked_without_ack(tmp_path: Path):
    repo = _git_repo(tmp_path / "ext")
    r = subprocess.run(
        [str(CAMPAIGN), "grok", "--preset", "repo-health", "--repo", str(repo), "--yolo", "--dry-run"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert GATE_MARK in r.stderr


def test_campaign_yolo_external_repo_allowed_with_ack(tmp_path: Path):
    repo = _git_repo(tmp_path / "ext")
    r = subprocess.run(
        [str(CAMPAIGN), "grok", "--preset", "repo-health", "--repo", str(repo),
         "--yolo", "--yolo-untrusted-acknowledged", "--dry-run"],
        capture_output=True, text=True,
    )
    # The gate must not block once acknowledged (dry-run then proceeds normally).
    assert GATE_MARK not in r.stderr
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_campaign_yolo_own_clone_not_blocked(tmp_path: Path):
    # --yolo without an external --repo (defaults to this clone) must not trip the gate.
    r = subprocess.run(
        [str(CAMPAIGN), "grok", "--preset", "repo-health", "--yolo", "--dry-run"],
        capture_output=True, text=True,
    )
    assert GATE_MARK not in r.stderr
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_headless_yolo_external_repo_blocked_without_ack(tmp_path: Path):
    repo = _git_repo(tmp_path / "ext")
    r = subprocess.run(
        [str(HEADLESS), "grok", "doc-sync", "--repo", str(repo), "--yolo"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert GATE_MARK in r.stderr
