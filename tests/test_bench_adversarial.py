"""Tests for scripts/bench-adversarial.sh.

The driver is a bash script (not Python), so coverage gating doesn't
apply. These tests exercise:

1. Targets YAML parses and contains exactly the 5 specified targets
2. Bench driver's CLI surface — --help, --dry-run, bad-args
3. Driver --dry-run loops over targets and emits the expected plan

Lineage: docs/plans/way-ahead-2026-06-23.md §3 Commit C.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_DRIVER = REPO_ROOT / "scripts" / "bench-adversarial.sh"
TARGETS_FILE = REPO_ROOT / "docs" / "external-dogfood" / "adversarial-bench-targets.yaml"


def test_targets_yaml_loads_and_has_5_targets() -> None:
    with open(TARGETS_FILE) as f:
        doc = yaml.safe_load(f)
    assert doc["schema_version"] == "1.0"
    assert doc["mission"] == "adversarial-review-and-fix"
    assert doc["comparator"] == "substrate-off-vs-on"
    assert doc["operator_required"] is True
    targets = doc["targets"]
    assert len(targets) == 5

    names = {t["name"] for t in targets}
    assert names == {
        "pallets/click",
        "python-jsonschema/jsonschema",
        "pycqa-bandit-corpus",
        "swe-bench-lite-instance",
        "github/gemoji",
    }

    for target in targets:
        assert "clone_url" in target
        assert "why_chosen" in target
        assert "known_issue_surface" in target
        assert "expected_findings_band" in target


def test_driver_is_executable() -> None:
    assert BENCH_DRIVER.is_file()
    # Bash interprets shebang; checking shebang line is sufficient.
    text = BENCH_DRIVER.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text


def test_driver_help() -> None:
    result = subprocess.run(
        ["bash", str(BENCH_DRIVER), "--help"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "--substrate" in result.stdout
    assert "--both" in result.stdout


def test_driver_unknown_arg_exits_2() -> None:
    result = subprocess.run(
        ["bash", str(BENCH_DRIVER), "--this-arg-does-not-exist"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 2
    assert "unknown arg" in result.stderr


def test_driver_bad_substrate_value_exits_2() -> None:
    result = subprocess.run(
        ["bash", str(BENCH_DRIVER), "--substrate", "maybe"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 2
    assert "must be 'on' or 'off'" in result.stderr


def test_driver_missing_targets_file_exits_2(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(BENCH_DRIVER), "--targets", str(tmp_path / "nope.yaml")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 2
    assert "targets file not found" in result.stderr


def test_driver_target_not_found_exits_2() -> None:
    result = subprocess.run(
        [
            "bash",
            str(BENCH_DRIVER),
            "--target",
            "does-not-exist",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 2
    assert "target not found" in result.stderr


def test_driver_dry_run_both_modes() -> None:
    """--dry-run --both prints two dispatch lines per target."""
    result = subprocess.run(
        [
            "bash",
            str(BENCH_DRIVER),
            "--target",
            "pallets/click",
            "--both",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0
    # Each mode produces one "=== bench: ... (mode) ===" header.
    assert result.stdout.count("=== bench: pallets/click (off)") == 1
    assert result.stdout.count("=== bench: pallets/click (on)") == 1
    assert "would clone" in result.stdout


def test_driver_dry_run_single_mode() -> None:
    result = subprocess.run(
        [
            "bash",
            str(BENCH_DRIVER),
            "--target",
            "github/gemoji",
            "--substrate",
            "on",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.count("=== bench: github/gemoji (on)") == 1
    assert "(off)" not in result.stdout


def test_methodology_doc_references_comparator() -> None:
    """The methodology doc must declare the substrate-off vs substrate-on
    comparator as the falsifiable claim — this pins the doc against
    drift."""
    doc = (REPO_ROOT / "docs/external-dogfood/adversarial-bench-2026-06.md").read_text()
    assert "substrate OFF" in doc
    assert "substrate ON" in doc
    assert "DELTA" in doc
    assert "falsifiable" in doc.lower()


def test_per_target_stubs_exist() -> None:
    stubs_dir = REPO_ROOT / "docs/external-dogfood/adversarial-bench"
    assert stubs_dir.is_dir()
    stubs = list(stubs_dir.glob("*.md"))
    assert len(stubs) == 5


def test_summary_doc_exists_with_pending_status() -> None:
    summary = (REPO_ROOT / "docs/external-dogfood/adversarial-bench-summary.md").read_text()
    assert "pending" in summary.lower()
    assert "ready for operator" in summary.lower() or "infrastructure ready" in summary.lower()
    assert "substrate-off-vs-on" in summary or "substrate" in summary
