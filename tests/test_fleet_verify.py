"""Tests for the fleet-verify CLI and composed layer verifier."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import fleet_run, fleet_verify as fv  # noqa: E402

FIXTURE = ROOT / ".fleet" / "runs" / "example-fixture"
TEST_RUN_ID = "20260101T000000Z-adversarial-review-and-fix-abcdef"
TEST_MISSION = "adversarial-review-and-fix"


def _load_cli():
    spec = importlib.util.spec_from_file_location("fleet_verify_cli", ROOT / "scripts" / "fleet_verify.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*argv: str) -> tuple[int, str, str]:
    cli = _load_cli()
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


def _write_manifest(run_dir: Path, artifacts: list[tuple[Path, str]]) -> None:
    fleet_run.write_manifest(
        run_dir,
        run_id=TEST_RUN_ID,
        mission=TEST_MISSION,
        files=[
            fleet_run.file_entry_for(path, run_dir, kind=kind, producer="test")
            for path, kind in artifacts
        ],
    )


def _trace_event(run_id: str = TEST_RUN_ID, *, status: str = "succeeded") -> dict[str, str]:
    return {
        "schema_version": "1.0",
        "ts": "2026-01-01T00:00:00Z",
        "run_id": run_id,
        "mission": TEST_MISSION,
        "primitive": "T-FINAL",
        "role": "INTEGRATOR",
        "status": status,
    }


def _write_trace(run_dir: Path, events: list[dict[str, str]]) -> None:
    (run_dir / "trace.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )


def _write_valid_trace(run_dir: Path) -> None:
    _write_trace(run_dir, [_trace_event()])


def _write_outcome(run_dir: Path, run_id: str = TEST_RUN_ID) -> None:
    payload = {
        "mission": TEST_MISSION,
        "status": "partial",
        "repo": "owner/repo",
        "base_branch": "main",
        "reviewer_mode": "cross-vendor-structural",
        "prs_merged": 0,
        "archive_enabled": True,
        "run_id": run_id,
        "metrics": {
            "p0_open": 0,
            "p1_open": 0,
            "findings_open": 0,
            "ops_queue_count": 0,
        },
    }
    (run_dir / "fleet-outcome.yaml").write_text(
        "---\n" + yaml.safe_dump({"fleet-outcome": payload}, sort_keys=False) + "---\n",
        encoding="utf-8",
    )

def _minimal_findings(quoted_line: str = "return 42  # stable quoted source") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "mission": "adversarial-review-and-fix",
        "review_id": "test-review-1",
        "findings": [
            {
                "id": "F-001",
                "severity": "medium",
                "category": "bug",
                "claim": "The fixture source contains the cited line.",
                "evidence": {
                    "file_path": "src/main.py",
                    "line_number": 2,
                    "quoted_line": quoted_line,
                },
                "fix_alternatives": [
                    {
                        "label": "A",
                        "description": "Keep the source line verifiable.",
                        "effort": "minimal",
                        "recommended": True,
                    }
                ],
                "confidence": 90,
                "fix_strategy": "auto",
            }
        ],
        "verdict": {"decision": "request_changes", "reasoning": "test"},
    }


def test_fixture_cli_json_reports_real_layer_mix() -> None:
    rc, out, _err = _run_cli(str(FIXTURE), "--repo", str(ROOT), "--json")
    payload = json.loads(out)
    by_name = {layer["name"]: layer for layer in payload["layers"]}

    assert rc == payload["exit_code"] == 1
    assert set(by_name) == {"run-archive", "findings", "blind-fix", "fleet-outcome", "trace", "identity"}
    assert by_name["findings"]["status"] == fv.FAIL
    assert by_name["findings"]["errors"] == ["unverified finding(s): F-002"]
    assert by_name["blind-fix"]["status"] == fv.PASS
    assert by_name["fleet-outcome"]["status"] == fv.PASS
    assert by_name["trace"]["status"] == fv.PASS
    assert by_name["run-archive"]["status"] == fv.PASS
    assert by_name["identity"]["status"] == fv.PASS
    assert by_name["identity"]["data"]["run_id"] == "20260623T000000Z-adversarial-review-and-fix-000001"
    assert payload["summary"] == {fv.PASS: 5, fv.FAIL: 1, fv.SKIP: 0}


def test_corrupted_manifest_cli_prints_table_and_exits_one(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text('{"schema_version": "1.0"}\n', encoding="utf-8")

    rc, out, err = _run_cli(str(run_dir), "--repo", str(ROOT))

    assert rc == 1
    assert err == ""
    assert "Layer" in out and "Artifact" in out and "Status" in out
    assert "run-archive" in out and "FAIL" in out
    assert "findings" in out and "SKIP" in out

def test_non_utf8_manifest_is_layer_failure_not_traceback(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_bytes(b"\xff\xfe\xfa")

    rc, out, err = _run_cli(str(run_dir), "--repo", str(ROOT), "--json")
    payload = json.loads(out)
    manifest = {layer["name"]: layer for layer in payload["layers"]}["run-archive"]

    assert rc == payload["exit_code"] == 1
    assert err == ""
    assert manifest["status"] == fv.FAIL
    assert manifest["detail"] == "manifest unreadable"



def test_empty_run_dir_is_not_success(tmp_path: Path) -> None:
    rc, out, err = _run_cli(str(tmp_path), "--repo", str(ROOT))

    assert rc == 2
    assert err == ""
    assert out.count("SKIP") == 6


def test_identity_fails_manifest_outcome_run_id_mismatch_and_exits_one(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    artifact = run_dir / "notes.txt"
    artifact.write_text("evidence", encoding="utf-8")
    _write_manifest(run_dir, [(artifact, "other")])
    other_run_id = "20260101T000000Z-adversarial-review-and-fix-000001"
    _write_outcome(run_dir, other_run_id)

    report = fv.verify_run(run_dir, ROOT)
    by_name = {layer["name"]: layer for layer in report["layers"]}

    assert report["exit_code"] == 1
    assert by_name["run-archive"]["status"] == fv.PASS
    assert by_name["identity"]["status"] == fv.FAIL
    assert by_name["identity"]["detail"] == "run_id mismatch across artifacts (possible replayed evidence)"
    assert f"manifest={TEST_RUN_ID}" in by_name["identity"]["errors"]
    assert f"fleet-outcome={other_run_id}" in by_name["identity"]["errors"]


def test_identity_fails_when_valid_run_dir_name_conflicts_with_manifest(tmp_path: Path) -> None:
    dir_run_id = "20260101T000000Z-adversarial-review-and-fix-000001"
    run_dir = tmp_path / dir_run_id
    run_dir.mkdir()
    artifact = run_dir / "notes.txt"
    artifact.write_text("evidence", encoding="utf-8")
    _write_manifest(run_dir, [(artifact, "other")])

    report = fv.verify_run(run_dir, ROOT)
    identity = {layer["name"]: layer for layer in report["layers"]}["identity"]

    assert report["exit_code"] == 1
    assert identity["status"] == fv.FAIL
    assert f"manifest={TEST_RUN_ID}" in identity["errors"]
    assert f"dir-name={dir_run_id}" in identity["errors"]


def test_identity_skips_empty_run_dir_and_preserves_structural_exit_code(tmp_path: Path) -> None:
    report = fv.verify_run(tmp_path, ROOT)
    identity = {layer["name"]: layer for layer in report["layers"]}["identity"]

    assert report["exit_code"] == 2
    assert identity["status"] == fv.SKIP
    assert identity["detail"] == "no run_id-bearing artifacts"


def test_identity_fails_when_trace_contains_multiple_run_ids(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    other_run_id = "20260101T000000Z-adversarial-review-and-fix-000001"
    _write_trace(run_dir, [_trace_event(TEST_RUN_ID), _trace_event(other_run_id)])

    identity = {layer["name"]: layer for layer in fv.verify_run(run_dir, ROOT)["layers"]}["identity"]

    assert identity["status"] == fv.FAIL
    assert f"trace={TEST_RUN_ID}" in identity["errors"]
    assert f"trace={other_run_id}" in identity["errors"]


def test_identity_ignores_unreadable_run_id_artifacts_instead_of_traceback(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").mkdir()
    (run_dir / "fleet-outcome.yaml").write_bytes(b"\xff\xfe\xfa")
    (run_dir / "trace.jsonl").mkdir()

    identity = {layer["name"]: layer for layer in fv.verify_run(run_dir, ROOT)["layers"]}["identity"]

    assert identity["status"] == fv.SKIP
    assert identity["detail"] == "no run_id-bearing artifacts"


def test_trace_event_cap_fails_over_limit_and_allows_small_traces(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(fv, "MAX_TRACE_EVENTS", 2)

    over = tmp_path / "over"
    over.mkdir()
    _write_trace(over, [_trace_event(), _trace_event(), _trace_event()])
    over_trace = {layer["name"]: layer for layer in fv.verify_run(over, ROOT)["layers"]}["trace"]

    assert over_trace["status"] == fv.FAIL
    assert over_trace["detail"] == "trace exceeds 2 events (resource-exhaustion guard)"
    assert over_trace["errors"] == ["trace.jsonl exceeds the 2-event cap; refusing to load in full"]

    under = tmp_path / "under"
    under.mkdir()
    _write_trace(under, [_trace_event(), _trace_event()])
    under_trace = {layer["name"]: layer for layer in fv.verify_run(under, ROOT)["layers"]}["trace"]

    assert under_trace["status"] == fv.PASS


def test_findings_pass_without_blind_fix_is_success_with_skip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "main.py").write_text("def f():\n    return 42  # stable quoted source\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    findings_path = run_dir / "p0-review-findings.json"
    findings_path.write_text(json.dumps(_minimal_findings()), encoding="utf-8")
    _write_manifest(run_dir, [(findings_path, "findings")])

    report = fv.verify_run(run_dir, repo)
    by_name = {layer["name"]: layer for layer in report["layers"]}

    assert report["exit_code"] == 0
    assert by_name["run-archive"]["status"] == fv.PASS
    assert by_name["findings"]["status"] == fv.PASS
    assert by_name["findings"]["data"]["summary"]["verified_findings"] == 1
    assert by_name["blind-fix"]["status"] == fv.SKIP


def test_manifest_absent_with_valid_trace_is_structurally_unverifiable(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_valid_trace(run_dir)

    report = fv.verify_run(run_dir, ROOT)
    by_name = {layer["name"]: layer for layer in report["layers"]}

    assert report["exit_code"] == 2
    assert by_name["run-archive"]["status"] == fv.SKIP
    assert by_name["trace"]["status"] == fv.PASS


def test_manifest_declared_findings_at_wrong_path_promotes_skip_to_fail(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    nested = run_dir / "nested"
    nested.mkdir(parents=True)
    findings_path = nested / "p0-review-findings.json"
    findings_path.write_text(json.dumps(_minimal_findings()), encoding="utf-8")
    _write_manifest(run_dir, [(findings_path, "findings")])

    report = fv.verify_run(run_dir, ROOT)
    by_name = {layer["name"]: layer for layer in report["layers"]}

    assert report["exit_code"] == 1
    assert by_name["run-archive"]["status"] == fv.PASS
    assert by_name["findings"]["status"] == fv.FAIL
    assert "manifest declares" in by_name["findings"]["errors"][0]



def test_invalid_findings_fail_findings_and_blind_fix_prerequisite(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "p0-review-findings.json").write_text("{not json", encoding="utf-8")
    (run_dir / "reviewer-blind-fix-F-001.md").write_text("present", encoding="utf-8")

    report = fv.verify_run(run_dir, ROOT)
    by_name = {layer["name"]: layer for layer in report["layers"]}

    assert report["exit_code"] == 2
    assert by_name["findings"]["status"] == fv.FAIL
    assert "invalid JSON" in by_name["findings"]["errors"][0]
    assert by_name["blind-fix"]["status"] == fv.FAIL
    assert "invalid JSON" in by_name["blind-fix"]["errors"][0]

def test_directory_shaped_findings_is_layer_failure_not_traceback(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "p0-review-findings.json").mkdir()

    report = fv.verify_run(run_dir, ROOT)
    by_name = {layer["name"]: layer for layer in report["layers"]}

    assert report["exit_code"] == 2
    assert by_name["findings"]["status"] == fv.FAIL
    assert by_name["findings"]["detail"] == "findings document unreadable"
    assert by_name["blind-fix"]["status"] == fv.FAIL
    assert by_name["blind-fix"]["detail"] == "findings prerequisite unreadable"



def test_findings_schema_error_is_layer_failure(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    bad = _minimal_findings()
    bad["findings"][0]["severity"] = "nuclear"
    (run_dir / "p0-review-findings.json").write_text(json.dumps(bad), encoding="utf-8")

    findings = {layer["name"]: layer for layer in fv.verify_run(run_dir, ROOT)["layers"]}["findings"]

    assert findings["status"] == fv.FAIL
    assert "severity must be one of" in findings["errors"][0]


def test_blind_fix_invalid_chain_is_layer_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "main.py").write_text("def f():\n    return 42  # stable quoted source\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    doc = _minimal_findings()
    doc["findings"][0]["blind_fix_chain"] = {"path": "missing-blind-fix.md"}
    (run_dir / "p0-review-findings.json").write_text(json.dumps(doc), encoding="utf-8")

    blind = {layer["name"]: layer for layer in fv.verify_run(run_dir, repo)["layers"]}["blind-fix"]

    assert blind["status"] == fv.FAIL
    assert "F-001:" in blind["errors"][0]


def test_outcome_parse_error_is_layer_failure(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "fleet-outcome.yaml").write_text("---\nfleet-outcome: [\n", encoding="utf-8")

    report = fv.verify_run(run_dir, ROOT)
    outcome = {layer["name"]: layer for layer in report["layers"]}["fleet-outcome"]

    assert report["exit_code"] == 2
    assert outcome["status"] == fv.FAIL
    assert outcome["errors"]

def test_outcome_validation_error_is_layer_failure(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "fleet-outcome.yaml").write_text(
        "---\nfleet-outcome:\n  mission: made-up\n  status: nope\n  repo: owner/repo\n  base_branch: main\n  reviewer_mode: cross-vendor-structural\n  prs_merged: 0\n---\n",
        encoding="utf-8",
    )

    outcome = {layer["name"]: layer for layer in fv.verify_run(run_dir, ROOT)["layers"]}["fleet-outcome"]

    assert outcome["status"] == fv.FAIL
    assert any("invalid status" in error for error in outcome["errors"])



def test_trace_schema_malformed_empty_and_unreadable_failures(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "trace.jsonl").write_text("{}\nnot json\n", encoding="utf-8")
    invalid_trace = {layer["name"]: layer for layer in fv.verify_run(invalid, ROOT)["layers"]}["trace"]
    assert invalid_trace["status"] == fv.FAIL
    assert any("missing required field" in error for error in invalid_trace["errors"])
    assert any("malformed JSON" in error for error in invalid_trace["errors"])

    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "trace.jsonl").write_text("", encoding="utf-8")
    empty_trace = {layer["name"]: layer for layer in fv.verify_run(empty, ROOT)["layers"]}["trace"]
    assert empty_trace["errors"] == ["trace has no events"]

    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()
    (unreadable / "trace.jsonl").mkdir()
    unreadable_trace = {layer["name"]: layer for layer in fv.verify_run(unreadable, ROOT)["layers"]}["trace"]
    assert unreadable_trace["status"] == fv.FAIL
    assert "trace unreadable" in unreadable_trace["detail"]


def test_blind_fix_artifact_detection_edges(tmp_path: Path) -> None:
    assert fv._has_blind_fix_artifact(tmp_path, {"findings": "not-a-list"}) is False
    assert fv._has_blind_fix_artifact(tmp_path, {"findings": [None]}) is False
    assert fv._has_blind_fix_artifact(
        tmp_path, {"findings": [None, {"blind_fix_chain": {"path": "declared.md"}}]}
    ) is True
    nested = tmp_path / "reviewer"
    nested.mkdir()
    (nested / "reviewer-blind-fix-F-001.md").write_text("present", encoding="utf-8")
    assert fv._has_blind_fix_artifact(tmp_path, {}) is True


def test_cli_rejects_missing_run_dir_and_repo(tmp_path: Path) -> None:
    rc, _out, err = _run_cli(str(tmp_path / "missing"), "--repo", str(ROOT))
    assert rc == 2
    assert "not a directory" in err

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rc, _out, err = _run_cli(str(run_dir), "--repo", str(tmp_path / "missing-repo"))
    assert rc == 2
    assert "--repo not a directory" in err


def test_action_yaml_is_minimal_composite_and_references_existing_cli() -> None:
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    steps = action["runs"]["steps"]

    assert action["name"] == "fleet-verify"
    assert action["runs"]["using"] == "composite"
    assert "run-dir" in action["inputs"] and action["inputs"]["run-dir"]["required"] is True
    assert all(not str(step.get("uses", "")).startswith("actions/checkout@") for step in steps)
    assert any(step.get("uses") == "actions/setup-python@v5" for step in steps)
    install_steps = [step for step in steps if step["name"] == "Install Python dependencies"]
    assert install_steps == [
        {"name": "Install Python dependencies", "shell": "bash", "run": 'python -m pip install "PyYAML>=6.0"'}
    ]
    verify_step = next(step for step in steps if step["name"] == "Verify fleet run")
    assert verify_step["env"] == {
        "RUN_DIR": "${{ inputs.run-dir }}",
        "REPO": "${{ inputs.repo }}",
    }
    assert '"${{ github.action_path }}/scripts/fleet_verify.py"' in verify_step["run"]
    assert "${{ inputs." not in verify_step["run"]
    assert '"$RUN_DIR"' in verify_step["run"] and '--repo "$REPO"' in verify_step["run"]
    assert "--json" in verify_step["run"] and "tee" in verify_step["run"]
    assert (ROOT / "scripts" / "fleet_verify.py").is_file()
