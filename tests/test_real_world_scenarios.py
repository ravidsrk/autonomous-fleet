"""Direct exercises of real-world scenarios from progress docs, dogfood packs, and example-fixture.

Maps to roadmap acceptance criteria 4: >=50 scenario tests grounded in shipped artifacts.
No mocks of TraceEmitter or fleet_run validators — libs are invoked in-process.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / ".fleet" / "runs" / "example-fixture"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.emit_trace import (  # noqa: E402
    TraceEmitter,
    emit_representative_mission_trace,
    health_rollup,
    iter_trace_file,
    validate_event,
)
from lib import fleet_run  # noqa: E402
from lib.registry_lint import shipped_missions  # noqa: E402


def _load_emit_cli():
    spec = importlib.util.spec_from_file_location(
        "emit_trace_cli", REPO_ROOT / "scripts" / "emit_trace.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── example-fixture manifest scenarios ──────────────────────────────────

MANIFEST_FILES = json.loads((FIXTURE / "manifest.json").read_text())["files"]


@pytest.mark.parametrize(
    "path,kind",
    [
        ("reviewer-blind-fix-F-001.md", "blind_fix"),
        ("reviewer-blind-fix-F-002.md", "blind_fix"),
        ("p0-review-findings.json", "findings"),
        ("p0-verify-summary.json", "verify_summary"),
        ("stop-verify-decisions.log", "other"),
        ("p1-fix-attestation.json", "other"),
        ("trace.jsonl", "other"),
        ("fleet-outcome.yaml", "readiness"),
        ("README.md", "other"),
    ],
)
def test_fixture_manifest_lists_real_artifact(path: str, kind: str) -> None:
    entry = next(f for f in MANIFEST_FILES if f["path"] == path)
    assert entry["kind"] == kind
    assert entry["bytes"] > 0
    assert len(entry["sha256"]) == 64


def test_fixture_manifest_run_id_matches_adversarial_mission() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["mission"] == "adversarial-review-and-fix"
    assert manifest["run_id"].startswith("20260623T000000Z-adversarial-review-and-fix-")


def test_fixture_validate_manifest_passes_ordering_invariants() -> None:
    _payload, errors = fleet_run.load_and_validate_manifest(FIXTURE)
    assert errors == []


# ── example-fixture trace scenarios ─────────────────────────────────────

TRACE_EVENTS = list(iter_trace_file(FIXTURE / "trace.jsonl"))


@pytest.mark.parametrize(
    "primitive",
    [
        "DISPATCH",
        "SPAWN_WORKER",
        "WAIT",
        "GOAL_BLOCKED",
        "INSPECT",
        "SYNC",
        "MERGE",
        "FREEZE",
        "COMMIT",
        "ABORT",
        "T-FINAL",
    ],
)
def test_fixture_trace_exercises_primitive(primitive: str) -> None:
    found = [e for e in TRACE_EVENTS if e["primitive"] == primitive]
    assert len(found) >= 1
    assert validate_event(found[0]) == []


def test_fixture_trace_spawn_links_to_dispatch() -> None:
    by_id = {e["id"]: e for e in TRACE_EVENTS}
    spawn = next(e for e in TRACE_EVENTS if e["primitive"] == "SPAWN_WORKER")
    assert spawn.get("parent_event") == by_id["evt-0001"]["id"]


def test_fixture_trace_commit_links_to_spawn() -> None:
    spawn_id = next(e["id"] for e in TRACE_EVENTS if e["primitive"] == "SPAWN_WORKER")
    commit = next(e for e in TRACE_EVENTS if e["primitive"] == "COMMIT")
    assert commit.get("parent_event") == spawn_id


def test_fixture_trace_t_final_records_nine_archived_files() -> None:
    final = next(e for e in TRACE_EVENTS if e["primitive"] == "T-FINAL")
    assert final["details"]["files"] == 9
    assert final["details"]["manifest"] == "manifest.json"


def test_fixture_health_rollup_counts_started_and_succeeded() -> None:
    rollup = health_rollup(TRACE_EVENTS)
    assert rollup["total"] == 11
    assert rollup["succeeded"] == 6
    assert rollup["skipped"] == 2
    assert rollup["failed"] == 0


# ── representative emission (headless path) ─────────────────────────────

def test_emit_representative_mission_trace_round_trip(tmp_path: Path) -> None:
    run_id = "20260626T120000Z-doc-sync-000001"
    with TraceEmitter(tmp_path, mission="doc-sync", run_id=run_id) as emitter:
        ids = emit_representative_mission_trace(emitter, file_count=3)
    assert "t_final" in ids
    events = list(iter_trace_file(tmp_path / "trace.jsonl"))
    primitives = {e["primitive"] for e in events}
    assert primitives >= {
        "DISPATCH",
        "SPAWN_WORKER",
        "GOAL_BLOCKED",
        "INSPECT",
        "FREEZE",
        "COMMIT",
        "ABORT",
        "T-FINAL",
    }
    assert all(validate_event(e) == [] for e in events)


def test_emit_representative_trace_cli_writes_valid_trace(tmp_path: Path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "emit_representative_trace.py"),
            "--mission",
            "test-coverage",
            "--run-id",
            "20260626T130000Z-test-coverage-000001",
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "primitives:" in r.stdout
    cli = _load_emit_cli()
    assert cli.main(["validate", str(tmp_path / "trace.jsonl")]) == 0


# ── progress-doc scenario markers (doc-sync dogfood) ────────────────────

DOC_SYNC_MARKERS = [
    "MISSION-FIT: doc-sync premise",
    "TASK doc-sync-readme | FILE=README.md",
    "SIGNAL RECONCILIATION",
]


@pytest.mark.parametrize("marker", DOC_SYNC_MARKERS)
def test_doc_sync_progress_records_real_dogfood_marker(marker: str) -> None:
    text = (REPO_ROOT / "docs" / "doc-sync-progress.md").read_text()
    assert marker in text


# ── progress-doc scenario markers (test-coverage dogfood) ───────────────

TEST_COV_MARKERS = [
    "COVERAGE MAP",
    "scripts/coupling-graph.py",
    "SIGNAL RECONCILIATION (a real catch)",
]


@pytest.mark.parametrize("marker", TEST_COV_MARKERS)
def test_test_coverage_progress_records_real_dogfood_marker(marker: str) -> None:
    text = (REPO_ROOT / "docs" / "test-coverage-progress.md").read_text()
    assert marker in text


# ── ship-with-proof external dogfood scenarios ──────────────────────────

SHIP_PROOF_MARKERS = [
    "ravidsrk/gemoji",
    "1541ce9",
    "26 runs, 57 assertions",
    "validate-fleet-outcome.sh",
]


@pytest.mark.parametrize("marker", SHIP_PROOF_MARKERS)
def test_ship_with_proof_evidence_documents_interactive_run(marker: str) -> None:
    text = (REPO_ROOT / "docs" / "external-dogfood" / "ship-with-proof-evidence.md").read_text()
    assert marker in text


def test_repo_health_gemoji_pack_lists_doc_sync_then_test_coverage() -> None:
    text = (REPO_ROOT / "docs" / "external-dogfood" / "repo-health-gemoji.md").read_text()
    assert "doc-sync" in text
    assert "test-coverage" in text


# ── adversarial bench target scenarios ──────────────────────────────────

BENCH_TARGETS = yaml.safe_load(
    (REPO_ROOT / "docs" / "external-dogfood" / "adversarial-bench-targets.yaml").read_text()
)["targets"]


@pytest.mark.parametrize("target", BENCH_TARGETS)
def test_bench_target_has_clone_url_and_name(target: dict) -> None:
    assert "name" in target
    assert target.get("clone_url", "").startswith("https://")


def test_bench_methodology_documents_pending_operator_runs() -> None:
    text = (REPO_ROOT / "docs" / "external-dogfood" / "adversarial-bench-2026-06.md").read_text()
    assert "PENDING" in text
    assert "bench-adversarial.sh" in text


def test_bench_adversarial_script_help_lists_targets() -> None:
    r = subprocess.run(
        [str(REPO_ROOT / "scripts" / "bench-adversarial.sh"), "--help"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0
    assert "--target" in r.stdout


# ── campaign dry-run scenarios (mechanical, no auth) ─────────────────────

@pytest.mark.parametrize(
    "campaign_yaml",
    [
        "docs/external-dogfood/repo-health-campaign.yaml",
        "docs/external-dogfood/ship-with-proof-campaign.yaml",
    ],
)
def test_external_dogfood_campaign_dry_run_exits_zero(campaign_yaml: str) -> None:
    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-campaign.sh"),
            "grok",
            "--campaign",
            campaign_yaml,
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("preset", ["repo-health", "ship-with-proof", "quality-gate"])
def test_shipped_campaign_preset_dry_run_exits_zero(preset: str) -> None:
    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-campaign.sh"),
            "grok",
            "--preset",
            preset,
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr


# ── roadmap gap matrix scenarios ────────────────────────────────────────

GAP_IDS = ["A-real", "C-bench", "C-dogfood", "E-trace", "G-market", "M-promote", "H-headless"]


@pytest.mark.parametrize("gap_id", GAP_IDS)
def test_roadmap_gap_matrix_lists_pending_item(gap_id: str) -> None:
    text = (REPO_ROOT / "docs" / "roadmap-gap-matrix.md").read_text()
    assert gap_id in text


def test_roadmap_gap_matrix_trace_row_names_emit_helper() -> None:
    text = (REPO_ROOT / "docs" / "roadmap-gap-matrix.md").read_text()
    assert "write_headless_dryrun_archive" in text or "headless_trace" in text
    assert "emit_dryrun_lifecycle_trace" in text or "fleet_run" in text


# ── shipped mission registry scenarios ──────────────────────────────────

@pytest.mark.parametrize("mission", ["doc-sync", "test-coverage", "adversarial-review-and-fix"])
def test_shipped_mission_in_registry(mission: str) -> None:
    assert mission in shipped_missions()


@pytest.mark.parametrize(
    "mission,runtime",
    [
        ("doc-sync", "grok"),
        ("test-coverage", "claude"),
        ("adversarial-review-and-fix", "codex"),
    ],
)
def test_headless_dry_run_wiring_for_shipped_mission(mission: str, runtime: str) -> None:
    r = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "run-mission-headless.sh"),
            runtime,
            mission,
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "would run:" in r.stdout


# ── findings fixture scenarios (adversarial-review-and-fix archive) ─────

FINDINGS = json.loads((FIXTURE / "p0-review-findings.json").read_text())


def test_fixture_findings_has_two_items_one_verified() -> None:
    assert len(FINDINGS["findings"]) == 2
    verified = [f for f in FINDINGS["findings"] if f.get("verified")]
    assert len(verified) == 1


@pytest.mark.parametrize("finding_id", ["F-001", "F-002"])
def test_fixture_finding_has_blind_fix_artifact(finding_id: str) -> None:
    assert (FIXTURE / f"reviewer-blind-fix-{finding_id}.md").is_file()


def test_fixture_verify_summary_records_verification_split() -> None:
    summary = json.loads((FIXTURE / "p0-verify-summary.json").read_text())
    assert summary["total_findings"] == 2
    assert summary["verified_findings"] == 1
    assert summary["unverified_findings"] == 1