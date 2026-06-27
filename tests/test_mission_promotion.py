"""Exploratory mission promotion readiness validator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_shipped_missions_are_not_in_exploratory_list() -> None:
    from lib.mission_promotion import list_exploratory_missions

    exploratory = set(list_exploratory_missions(ROOT))
    for shipped in ("doc-sync", "test-coverage", "adversarial-review-and-fix"):
        assert shipped not in exploratory


def test_adversarial_has_archive_evidence() -> None:
    from lib.mission_promotion import assess_promotion

    report = assess_promotion(ROOT, "adversarial-review-and-fix")
    assert report.archive_refs
    assert "first-substrate" in " ".join(report.archive_refs) or any(
        ".fleet/runs" in ref for ref in report.archive_refs
    )


def test_cleanup_not_promotion_ready() -> None:
    from lib.mission_promotion import assess_promotion

    report = assess_promotion(ROOT, "cleanup")
    assert not report.ready
    assert "progress" in report.missing or "archive" in report.missing


def test_validate_mission_promotion_cli_exits_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_mission_promotion.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "exploratory missions" in r.stdout


def test_schema_11_event_validates() -> None:
    from lib.emit_trace import validate_event

    event = {
        "schema_version": "1.1",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "ts": "2026-06-27T12:00:00Z",
        "run_id": "20260627T120000Z-doc-sync-abc123",
        "mission": "doc-sync",
        "primitive": "WAIT",
        "role": "COORDINATOR",
        "status": "started",
    }
    assert validate_event(event) == []


def test_assess_all_exploratory_returns_fifteen() -> None:
    from lib.mission_promotion import assess_all_exploratory

    reports = assess_all_exploratory(ROOT)
    assert len(reports) == 15
    slugs = {r.mission for r in reports}
    for gstack in ("product-framing", "browser-qa-fix", "security-cso-audit"):
        assert gstack in slugs


def test_require_ready_cli_fails_for_cleanup() -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_mission_promotion.py"),
            "--require-ready",
            "cleanup",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "NOT ready" in r.stderr


def test_promotion_readiness_helpers(tmp_path: Path) -> None:
    from lib.mission_promotion import assess_promotion

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "exploratory" / "missions" / "demo").mkdir(parents=True)
    (tmp_path / "docs" / "exploratory" / "missions" / "demo" / "SKILL.md").write_text(
        "x", encoding="utf-8"
    )
    (tmp_path / "docs" / "demo-progress.md").write_text(
        "PHASE: DONE\nTASK T1 | CODED=t\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "demo-readiness.md").write_text(
        "---\nfleet-outcome:\n  status: done\n---\n", encoding="utf-8"
    )
    (tmp_path / ".fleet" / "runs" / "20260627T120000Z-demo-abc123").mkdir(parents=True)
    (tmp_path / ".fleet" / "runs" / "20260627T120000Z-demo-abc123" / "manifest.json").write_text(
        '{"mission":"demo","run_id":"20260627T120000Z-demo-abc123"}',
        encoding="utf-8",
    )
    report = assess_promotion(tmp_path, "demo")
    assert report.ready
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_mission_promotion.py"),
            "--require-ready",
            "demo",
            "--repo",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr


def test_validate_mission_promotion_main_direct() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import validate_mission_promotion as mod

    assert mod.main([]) == 0
    assert mod.main(["--require-ready", "cleanup"]) == 1


def test_mission_promotion_edge_cases(tmp_path: Path) -> None:
    from lib.mission_promotion import (
        _archive_evidence,
        _fleet_outcome_valid,
        _progress_substantive,
        list_exploratory_missions,
    )

    assert list_exploratory_missions(tmp_path / "nope") == []
    bad = tmp_path / "r.md"
    bad.write_text("no yaml\n", encoding="utf-8")
    assert not _fleet_outcome_valid(bad)
    prog = tmp_path / "p.md"
    prog.write_text("no phase\n", encoding="utf-8")
    assert not _progress_substantive(prog)
    dogfood = tmp_path / "docs" / "external-dogfood"
    dogfood.mkdir(parents=True)
    (dogfood / "note.md").write_text(
        "archive .fleet/runs/20260627T120000Z-demo-abc123 for demo mission\n",
        encoding="utf-8",
    )
    refs = _archive_evidence(tmp_path, "demo")
    assert refs


def test_mission_promotion_readiness_and_archive_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lib.mission_promotion import _archive_evidence, _fleet_outcome_valid, _progress_substantive

    r = tmp_path / "r.md"
    r.write_text("---\nnot-a-mapping\n---\n", encoding="utf-8")
    assert not _fleet_outcome_valid(r)
    r.write_text("---\nfleet-outcome: []\n---\n", encoding="utf-8")
    assert not _fleet_outcome_valid(r)
    r.write_text("---\nfleet-outcome:\n  status: blocked\n---\n", encoding="utf-8")
    assert not _fleet_outcome_valid(r)
    r.write_text("---\n", encoding="utf-8")
    assert not _fleet_outcome_valid(r)

    p = tmp_path / "p.md"
    p.write_text("PHASE: DONE\n", encoding="utf-8")
    assert not _progress_substantive(p)

    runs = tmp_path / ".fleet" / "runs" / "20260627T120000Z-my-mission-abc123"
    runs.mkdir(parents=True)
    (runs / "manifest.json").write_text("{", encoding="utf-8")
    refs = _archive_evidence(tmp_path, "my_mission")
    assert refs

    (tmp_path / ".fleet" / "runs" / "skip.txt").write_text("x", encoding="utf-8")
    dogfood = tmp_path / "docs" / "external-dogfood"
    dogfood.mkdir(parents=True, exist_ok=True)
    bad_md = dogfood / "bad.md"
    bad_md.write_text("demo .fleet/runs/x\n", encoding="utf-8")

    real_read = Path.read_text

    def flaky_read(self, *args, **kwargs):
        if self == bad_md:
            raise OSError("nope")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read)
    assert _archive_evidence(tmp_path, "demo") == []


def test_validate_mission_promotion_ready_paths(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import validate_mission_promotion as mod

    (tmp_path / "docs" / "exploratory" / "missions" / "demo").mkdir(parents=True)
    (tmp_path / "docs" / "exploratory" / "missions" / "demo" / "SKILL.md").write_text(
        "x", encoding="utf-8"
    )
    (tmp_path / "docs" / "demo-progress.md").write_text(
        "PHASE: DONE\nTASK T1 | CODED=t\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "demo-readiness.md").write_text(
        "---\nfleet-outcome:\n  status: done\n---\n", encoding="utf-8"
    )
    (tmp_path / ".fleet" / "runs" / "20260627T120000Z-demo-abc123").mkdir(parents=True)
    (tmp_path / ".fleet" / "runs" / "20260627T120000Z-demo-abc123" / "manifest.json").write_text(
        '{"mission":"demo","run_id":"20260627T120000Z-demo-abc123"}',
        encoding="utf-8",
    )
    assert mod.main(["--require-ready", "demo", "--repo", str(tmp_path)]) == 0
    assert mod.main(["--repo", str(tmp_path)]) == 0