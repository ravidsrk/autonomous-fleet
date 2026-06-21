"""Smoke test for run-campaign.sh dry-run."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
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


def _write_minimal_wheel(
    wheelhouse: Path,
    dist: str,
    version: str,
    files: dict[str, str],
) -> Path:
    normalized = dist.lower().replace("-", "_")
    wheel = wheelhouse / f"{normalized}-{version}-py3-none-any.whl"
    dist_info = f"{normalized}-{version}.dist-info"
    written = []

    with zipfile.ZipFile(wheel, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
            written.append(name)

        metadata = f"{dist_info}/METADATA"
        zf.writestr(metadata, f"Metadata-Version: 2.1\nName: {dist}\nVersion: {version}\n")
        written.append(metadata)

        wheel_meta = f"{dist_info}/WHEEL"
        zf.writestr(
            wheel_meta,
            "Wheel-Version: 1.0\n"
            "Generator: tests\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )
        written.append(wheel_meta)

        record = f"{dist_info}/RECORD"
        zf.writestr(record, "".join(f"{name},,\n" for name in [*written, record]))

    return wheel


def test_run_campaign_dry_run_self_heals_broken_real_venv(tmp_path: Path):
    """run-campaign.sh must re-check imports and reinstall requirements for a stale .venv."""
    import shutil

    repo = tmp_path / "self-heal"
    (repo / "scripts" / "lib").mkdir(parents=True)
    (repo / "scripts" / "campaigns").mkdir()

    shutil.copy(ROOT / "scripts" / "run-campaign.sh", repo / "scripts" / "run-campaign.sh")
    for path in (ROOT / "scripts" / "lib").glob("*"):
        if path.is_file():
            shutil.copy(path, repo / "scripts" / "lib" / path.name)

    wheelhouse = repo / "wheelhouse"
    wheelhouse.mkdir()
    pyyaml_wheel = _write_minimal_wheel(
        wheelhouse,
        "PyYAML",
        "6.0.2",
        {
            "yaml.py": (
                "import json\n\n"
                "class YAMLError(Exception):\n"
                "    pass\n\n"
                "def safe_load(text):\n"
                "    try:\n"
                "        return json.loads(text)\n"
                "    except Exception as exc:\n"
                "        raise YAMLError(str(exc)) from exc\n"
            ),
        },
    )
    pytest_wheel = _write_minimal_wheel(
        wheelhouse,
        "pytest",
        "8.3.4",
        {"pytest.py": "__version__ = '8.3.4'\n"},
    )
    (repo / "requirements.txt").write_text(
        f"--no-index\n{pyyaml_wheel}\n{pytest_wheel}\n",
        encoding="utf-8",
    )
    (repo / "scripts" / "campaigns" / "t.yaml").write_text(
        json.dumps(
            {
                "campaign": "self-heal",
                "start": "docs",
                "nodes": {"docs": {"mission": "doc-sync"}},
                "edges": {"docs": []},
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run([sys.executable, "-m", "venv", str(repo / ".venv")], check=True)
    assert not (repo / ".venv").is_symlink()

    venv_python = repo / ".venv" / "bin" / "python"
    missing_imports = subprocess.run(
        [str(venv_python), "-c", "import yaml, pytest"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing_imports.returncode != 0

    r = subprocess.run(
        [
            str(repo / "scripts" / "run-campaign.sh"),
            "grok",
            "--campaign",
            "scripts/campaigns/t.yaml",
            "--repo",
            str(repo),
            "--dry-run",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = r.stdout + r.stderr
    assert r.returncode == 0, combined
    assert "Campaign dry-run complete" in r.stdout
    assert "ModuleNotFoundError" not in combined
    assert "Traceback" not in combined

    healed_imports = subprocess.run(
        [str(venv_python), "-c", "import yaml, pytest"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert healed_imports.returncode == 0, healed_imports.stderr


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
