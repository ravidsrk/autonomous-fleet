"""Behavioral tests for run-mission-headless.sh auth pre-check + timeout watchdog (issue #75).

The gemoji headless run failed auth mid-flight and was completed by hand; a hung runtime
previously blocked a campaign forever (no watchdog around run_runtime_emit). These tests
drive the real script against fake runtime binaries, mirroring tests/test_run_campaign.py.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-mission-headless.sh"
CAMPAIGN_SCRIPT = ROOT / "scripts" / "run-campaign.sh"


def _external_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def _fake_codex(tmp_path: Path, *, login_rc: int = 0, login_out: str = "Logged in using ChatGPT",
                exec_sleep: int = 0, marker: Path | None = None) -> Path:
    """Fake codex CLI: `codex login status` reports auth; `codex exec ...` is the runtime."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    marker_line = f"touch {marker}\n" if marker else ""
    fake = fake_bin / "codex"
    fake.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "login" ]; then echo "{login_out}"; exit {login_rc}; fi\n'
        f"{marker_line}"
        f"[ {exec_sleep} -gt 0 ] && sleep {exec_sleep}\n"
        'echo "{\\"done\\":true}"\n'
        "exit 0\n"
    )
    fake.chmod(0o755)
    return fake_bin


def _env_with(fake_bin: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    return env


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args], cwd=ROOT, capture_output=True, text=True, check=False, env=env
    )


def test_unauthenticated_codex_fails_fast_before_runtime(tmp_path: Path) -> None:
    repo = _external_repo(tmp_path)
    marker = tmp_path / "runtime-invoked"
    fake_bin = _fake_codex(tmp_path, login_rc=1, login_out="Not logged in", marker=marker)

    r = _run(["codex", "doc-sync", "--repo", str(repo)], _env_with(fake_bin))

    assert r.returncode == 3, r.stdout + r.stderr
    assert "not authenticated" in r.stderr
    assert "--skip-auth-check" in r.stderr
    assert not marker.exists(), "runtime must not be invoked when the auth probe fails"


def test_authenticated_codex_probe_passes_and_runtime_runs(tmp_path: Path) -> None:
    repo = _external_repo(tmp_path)
    marker = tmp_path / "runtime-invoked"
    fake_bin = _fake_codex(tmp_path, marker=marker)

    r = _run(["codex", "doc-sync", "--repo", str(repo)], _env_with(fake_bin))

    assert r.returncode == 0, r.stdout + r.stderr
    assert "auth-check: codex authenticated" in r.stdout
    assert marker.exists()


def test_skip_auth_check_bypasses_probe(tmp_path: Path) -> None:
    repo = _external_repo(tmp_path)
    marker = tmp_path / "runtime-invoked"
    fake_bin = _fake_codex(tmp_path, login_rc=1, login_out="Not logged in", marker=marker)

    r = _run(
        ["codex", "doc-sync", "--repo", str(repo), "--skip-auth-check"], _env_with(fake_bin)
    )

    assert r.returncode == 0, r.stdout + r.stderr
    assert "auth-check: skipped" in r.stdout
    assert marker.exists()


def test_probe_subcommand_missing_warns_and_proceeds(tmp_path: Path) -> None:
    """Version tolerance: a codex whose `login` subcommand vanished warns, never blocks."""
    repo = _external_repo(tmp_path)
    fake_bin = _fake_codex(tmp_path, login_rc=2, login_out="error: unrecognized subcommand 'login'")

    r = _run(["codex", "doc-sync", "--repo", str(repo)], _env_with(fake_bin))

    assert r.returncode == 0, r.stdout + r.stderr
    assert "cannot pre-verify auth" in r.stderr


def test_grok_has_no_probe_and_relies_on_watchdog(tmp_path: Path) -> None:
    repo = _external_repo(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_grok = fake_bin / "grok"
    fake_grok.write_text('#!/bin/sh\necho \'{"stopReason":"EndTurn"}\'\nexit 0\n')
    fake_grok.chmod(0o755)

    r = _run(["grok", "doc-sync", "--repo", str(repo)], _env_with(fake_bin))

    assert r.returncode == 0, r.stdout + r.stderr
    assert "grok exposes no auth status probe" in r.stdout


def test_timeout_kills_hung_runtime_and_still_archives(tmp_path: Path) -> None:
    repo = _external_repo(tmp_path)
    fake_bin = _fake_codex(tmp_path, exec_sleep=60)

    r = _run(
        ["codex", "doc-sync", "--repo", str(repo), "--timeout", "2"], _env_with(fake_bin)
    )

    assert r.returncode == 124, r.stdout + r.stderr
    assert "timed out after 2s" in r.stderr
    runs = sorted((repo / ".fleet" / "runs").iterdir())
    assert len(runs) == 1, f"transcript archive must still be emitted on timeout, got {runs}"


def test_timeout_bash_fallback_normalizes_to_124(tmp_path: Path) -> None:
    """Codex review finding: during the watchdog's TERM->KILL grace the watchdog is still
    alive, so PID-liveness misclassified a real timeout as rc 143. The sentinel file must
    classify it as 124 on the bash fallback path (no GNU timeout)."""
    repo = _external_repo(tmp_path)
    fake_bin = _fake_codex(tmp_path, exec_sleep=60)
    env = _env_with(fake_bin)
    env["FLEET_FORCE_TIMEOUT_FALLBACK"] = "1"

    r = subprocess.run(
        [str(SCRIPT), "codex", "doc-sync", "--repo", str(repo), "--timeout", "2"],
        cwd=ROOT, capture_output=True, text=True, check=False, env=env,
    )

    assert r.returncode == 124, r.stdout + r.stderr
    assert "timed out after 2s" in r.stderr


def test_timeout_rejects_non_integer(tmp_path: Path) -> None:
    repo = _external_repo(tmp_path)
    fake_bin = _fake_codex(tmp_path)

    r = _run(
        ["codex", "doc-sync", "--repo", str(repo), "--timeout", "soon"], _env_with(fake_bin)
    )

    assert r.returncode == 1, r.stdout + r.stderr
    assert "--timeout expects a non-negative integer" in r.stderr


def test_dry_run_needs_no_auth(tmp_path: Path) -> None:
    """Dry-run must not require an authenticated (or even present) runtime CLI."""
    repo = _external_repo(tmp_path)
    marker = tmp_path / "runtime-invoked"
    fake_bin = _fake_codex(tmp_path, login_rc=1, login_out="Not logged in", marker=marker)

    r = _run(["codex", "doc-sync", "--repo", str(repo), "--dry-run"], _env_with(fake_bin))

    assert r.returncode == 0, r.stdout + r.stderr
    assert "auth-check" not in r.stdout
    assert not marker.exists()


_DOC_SYNC_READINESS = """---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: /tmp/r
  base_branch: fleet/b
  prs_merged: 1
  metrics:
    drift_open: 0
    code_bug_findings: 0
---
# ok
"""


def test_campaign_passes_timeout_and_skip_auth_through(tmp_path: Path) -> None:
    repo = _external_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "doc-sync-readiness.md").write_text(_DOC_SYNC_READINESS, encoding="utf-8")
    campaign = tmp_path / "one-node.yaml"
    campaign.write_text(
        "campaign: one\nstart: docs\nnodes:\n  docs: { mission: doc-sync }\nedges:\n  docs: []\n",
        encoding="utf-8",
    )
    fake_bin = _fake_codex(tmp_path, login_rc=1, login_out="Not logged in")

    r = subprocess.run(
        [
            str(CAMPAIGN_SCRIPT), "codex", "--campaign", str(campaign),
            "--repo", str(repo), "--timeout", "300", "--skip-auth-check",
        ],
        cwd=ROOT, capture_output=True, text=True, check=False, env=_env_with(fake_bin),
    )

    # skip-auth-check must reach the headless layer (unauthenticated fake would exit 3 otherwise)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "auth-check: skipped" in r.stdout
    assert "timeout:  300s" in r.stdout


def test_real_run_emit_failure_is_fatal(tmp_path: Path) -> None:
    """OPS-001: archive emit failure on a real run must make headless exit non-zero."""
    repo = _external_repo(tmp_path)
    # Block archive creation: .fleet/runs as a file makes ensure_archive_dir raise.
    fleet = repo / ".fleet"
    fleet.mkdir()
    (fleet / "runs").write_text("not-a-directory\n", encoding="utf-8")
    fake_bin = _fake_codex(tmp_path)

    r = _run(["codex", "doc-sync", "--repo", str(repo)], _env_with(fake_bin))

    assert r.returncode != 0, r.stdout + r.stderr
    assert "emit_headless_dryrun_trace failed" in (r.stderr + r.stdout)
    assert "non-fatal" not in (r.stderr + r.stdout)


def test_dry_run_emit_failure_stays_non_fatal(tmp_path: Path) -> None:
    """OPS-001 narrowed: dry-run cleanup path keeps emit failure non-fatal."""
    repo = _external_repo(tmp_path)
    fleet = repo / ".fleet"
    fleet.mkdir()
    (fleet / "runs").write_text("not-a-directory\n", encoding="utf-8")
    fake_bin = _fake_codex(tmp_path)

    r = _run(["codex", "doc-sync", "--repo", str(repo), "--dry-run"], _env_with(fake_bin))

    assert r.returncode == 0, r.stdout + r.stderr
    assert "emit_headless_dryrun_trace failed (non-fatal)" in (r.stderr + r.stdout)
