"""SEC-001 / SEC-008: install-community.sh must not eval untrusted HOST/env values."""

from __future__ import annotations

import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-community.sh"


def _run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def test_host_injection_refused_and_no_exec(tmp_path: Path):
    """HOST with shell metacharacters must exit non-zero and must not run touch."""
    marker = tmp_path / f"pwned-sec001-{uuid.uuid4().hex}"
    # Classic eval injection: HOST closes the setup arg and runs touch.
    evil_host = f"true; touch {marker} #"
    assert not marker.exists()
    r = _run(["gstack", "--host", evil_host, "--execute"])
    assert r.returncode != 0, r.stdout + r.stderr
    assert "invalid --host" in (r.stderr + r.stdout).lower()
    assert not marker.exists(), f"injection executed: marker at {marker}"


def test_host_injection_acceptance_payload_refused():
    """Acceptance EVID shape: HOST='true touch ... #' must not create the pwned file."""
    marker = Path(tempfile.gettempdir()) / f"pwned-sec001-{uuid.uuid4().hex}"
    evil_host = f"true touch {marker} #"
    assert not marker.exists()
    try:
        r = _run(["gstack", "--host", evil_host, "--execute"])
        assert r.returncode != 0, r.stdout + r.stderr
        assert not os.path.exists(marker), f"injection executed: marker at {marker}"
    finally:
        if marker.exists():
            marker.unlink()


@pytest.mark.parametrize("host", ["cursor", "claude", "grok", "codex"])
def test_dry_run_prints_commands_for_allowed_hosts(host: str):
    r = _run(["gstack-browser", "--host", host, "--dry-run"])
    assert r.returncode == 0, r.stderr
    out = r.stdout
    # Dry-run prints human-readable argv lines (unquoted) before execute.
    assert "git clone" in out and "--single-branch" in out
    assert "./setup --host" in out
    assert host in out
    assert "dry-run only" in out


def test_mattpocock_pins_skills_version_not_latest():
    """SEC-008: mattpocock bundle must pin skills@1.5.12 (not @latest)."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "skills@latest" not in text
    assert "skills@1.5.12" in text
    r = _run(["mattpocock", "--dry-run"])
    assert r.returncode == 0, r.stderr
    assert "skills@1.5.12" in r.stdout
    assert "npx" in r.stdout
    assert "skills@latest" not in r.stdout


def test_script_has_no_eval():
    text = SCRIPT.read_text(encoding="utf-8")
    # Reject runtime eval; allow the word only inside comments if ever added.
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        assert "eval " not in stripped and not stripped.startswith("eval"), (
            f"eval must not appear in executable code: {line!r}"
        )


def test_gstack_env_metachar_repo_url_rejected(tmp_path: Path):
    """GSTACK_REPO_URL with shell metacharacters is rejected (defense in depth)."""
    evil = f"https://example.com/x.git; touch {tmp_path / 'pwned'} #"
    r = _run(
        ["gstack", "--host", "grok", "--dry-run"],
        env={"GSTACK_REPO_URL": evil, "GSTACK_SKILLS_DIR": str(tmp_path / "gstack")},
    )
    assert r.returncode != 0, r.stdout
    assert "GSTACK_REPO_URL" in r.stderr
    assert "metacharacters" in r.stderr.lower()
    assert not (tmp_path / "pwned").exists()


def test_gstack_env_metachar_skills_dir_rejected(tmp_path: Path):
    evil_dir = str(tmp_path / "gstack; touch pwned #")
    r = _run(
        ["gstack", "--host", "grok", "--dry-run"],
        env={"GSTACK_SKILLS_DIR": evil_dir},
    )
    assert r.returncode != 0, r.stdout
    assert "GSTACK_SKILLS_DIR" in r.stderr
    assert not (tmp_path / "pwned").exists()
