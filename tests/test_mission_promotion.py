"""Exploratory mission promotion readiness validator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _write_ready_shipped_fixture(root: Path) -> None:
    from lib.mission_registry import MISSION_DOCS, SHIPPED_MISSIONS

    docs = root / "docs"
    docs.mkdir()
    for slug in sorted(SHIPPED_MISSIONS):
        mission_docs = MISSION_DOCS[slug]
        (docs / mission_docs["progress"]).write_text(
            "PHASE: DONE\nTASK T1 | CODED=fixture\n", encoding="utf-8"
        )
        (docs / mission_docs["readiness"]).write_text(
            "---\nfleet-outcome:\n  status: done\n---\n", encoding="utf-8"
        )
        run_id = f"20260627T120000Z-{slug}-abc123"
        run_dir = root / ".fleet" / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps({"mission": slug, "run_id": run_id}),
            encoding="utf-8",
        )


def test_shipped_missions_are_not_in_exploratory_list() -> None:
    from lib.mission_promotion import list_exploratory_missions

    exploratory = set(list_exploratory_missions(ROOT))
    for shipped in ("doc-sync", "test-coverage", "adversarial-review-and-fix"):
        assert shipped not in exploratory


def test_adversarial_archive_evidence_excludes_quarantined_run() -> None:
    """Issue #78: the 8358f1 archive was quarantined to .fleet/fixtures/ and its
    dogfood doc carries the promotion-evidence exclusion marker — neither may
    count as archive evidence anymore. Other dogfood docs (bench, gemoji) still
    reference the mission and remain the discoverable refs."""
    from lib.mission_promotion import assess_promotion

    report = assess_promotion(ROOT, "adversarial-review-and-fix")
    joined = " ".join(report.archive_refs)
    assert "first-substrate" not in joined
    assert "8358f1" not in joined


def test_assess_promotion_uses_registry_doc_paths(tmp_path: Path) -> None:
    from lib.mission_promotion import assess_promotion

    _write_ready_shipped_fixture(tmp_path)
    report = assess_promotion(tmp_path, "adversarial-review-and-fix")
    assert report.ready
    assert report.progress_path == tmp_path / "docs" / "arch-build-progress.md"
    assert report.readiness_path == tmp_path / "docs" / "arch-build-readiness.md"


def test_assess_promotion_honors_fleet_ledger_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ARCH-003 / PROMO-002: progress and readiness resolve under FLEET_LEDGER_DIR."""
    from lib.mission_promotion import assess_promotion
    from lib.mission_registry import MISSION_DOCS

    monkeypatch.setenv("FLEET_LEDGER_DIR", ".fleet/docs")
    ledger = tmp_path / ".fleet" / "docs"
    ledger.mkdir(parents=True)
    mission = "adversarial-review-and-fix"
    mission_docs = MISSION_DOCS[mission]
    (ledger / mission_docs["progress"]).write_text(
        "PHASE: DONE\nTASK T1 | CODED=fixture\n", encoding="utf-8"
    )
    (ledger / mission_docs["readiness"]).write_text(
        "---\nfleet-outcome:\n  status: done\n---\n", encoding="utf-8"
    )
    run_id = f"20260627T120000Z-{mission}-abc123"
    run_dir = tmp_path / ".fleet" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps({"mission": mission, "run_id": run_id}),
        encoding="utf-8",
    )

    report = assess_promotion(tmp_path, mission)
    assert report.ready
    assert report.progress_path == ledger / mission_docs["progress"]
    assert report.readiness_path == ledger / mission_docs["readiness"]
    assert "progress" not in report.missing
    assert "readiness" not in report.missing


def test_promotion_uses_unkeyed_ledgers_when_run_short_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from lib.mission_promotion import assess_promotion
    from lib.mission_registry import SHIPPED_MISSIONS
    import validate_mission_promotion as mod

    _write_ready_shipped_fixture(tmp_path)
    monkeypatch.setenv("FLEET_RUN_SHORT", "abc123")

    reports = [assess_promotion(tmp_path, slug) for slug in sorted(SHIPPED_MISSIONS)]
    assert len(reports) == 3
    assert all(report.ready for report in reports)
    assert sum(report.progress_path is not None for report in reports) == 3
    assert all("-abc123-" not in str(report.progress_path) for report in reports)
    assert mod.main(["--require-shipped", "--repo", str(tmp_path)]) == 0
    assert "shipped missions ready" in capsys.readouterr().out


def test_assess_promotion_prefers_unkeyed_readiness_over_newer_run_keyed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lib.mission_promotion import assess_promotion

    _write_ready_shipped_fixture(tmp_path)
    canonical = tmp_path / "docs" / "doc-sync-readiness.md"
    keyed = tmp_path / "docs" / "doc-sync-abc123-readiness.md"
    keyed.write_text("---\nfleet-outcome:\n  status: blocked\n---\n", encoding="utf-8")
    monkeypatch.setenv("FLEET_RUN_SHORT", "abc123")

    report = assess_promotion(tmp_path, "doc-sync")

    assert report.ready
    assert report.readiness_path == canonical


def test_evidence_exclusion_marker_skips_doc(tmp_path: Path) -> None:
    """A dogfood doc with the exclusion marker must not count as archive
    evidence even when it names the mission and a run-id."""
    from lib.mission_promotion import _archive_evidence

    dogfood = tmp_path / "docs" / "external-dogfood"
    dogfood.mkdir(parents=True)
    body = (
        "# run notes\nmission demo-mission ran as "
        "20260101T000000Z-demo-mission-abc123 under .fleet/runs/\n"
    )
    (dogfood / "counted.md").write_text(body, encoding="utf-8")
    (dogfood / "excluded.md").write_text(
        "<!-- promotion-evidence: exclude -->\n" + body, encoding="utf-8"
    )

    refs = _archive_evidence(tmp_path, "demo-mission")
    assert refs == ["docs/external-dogfood/counted.md"]


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


def test_assess_all_exploratory_returns_active_missions_only() -> None:
    from lib.mission_promotion import assess_all_exploratory

    reports = assess_all_exploratory(ROOT)
    assert len(reports) == 12
    slugs = {r.mission for r in reports}
    for active in (
        "browser-qa-fix",
        "cleanup",
        "dependency-update",
        "incident-investigate",
        "targeted-migration",
        "take-product-to-completion",
    ):
        assert active in slugs
    for archived in (
        "product-framing",
        "security-cso-audit",
        "devex-audit",
        "release-document",
    ):
        assert archived not in slugs


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


def test_require_shipped_cli_passes_when_all_shipped_ready(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import validate_mission_promotion as mod

    _write_ready_shipped_fixture(tmp_path)
    assert mod.main(["--require-shipped", "--repo", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert "shipped missions ready" in captured.out


def test_require_shipped_cli_lists_missing_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import validate_mission_promotion as mod

    _write_ready_shipped_fixture(tmp_path)
    (tmp_path / "docs" / "doc-sync-readiness.md").unlink()
    assert mod.main(["--require-shipped", "--repo", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "doc-sync missing: readiness" in captured.err


def test_require_shipped_cli_accepts_documented_known_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import validate_mission_promotion as mod

    _write_ready_shipped_fixture(tmp_path)
    (tmp_path / "docs" / "arch-build-progress.md").unlink()
    assert (
        mod.main(
            [
                "--require-shipped",
                "--known-gap",
                "adversarial-review-and-fix:legacy progress gap",
                "--repo",
                str(tmp_path),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "adversarial-review-and-fix missing: progress" in captured.err
    assert "known gap: legacy progress gap" in captured.err
    assert "documented known gaps" in captured.out


def test_require_shipped_cli_rejects_stale_known_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import validate_mission_promotion as mod

    _write_ready_shipped_fixture(tmp_path)
    assert (
        mod.main(
            [
                "--require-shipped",
                "--known-gap",
                "doc-sync:already fixed",
                "--repo",
                str(tmp_path),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert "known gap doc-sync does not match" in captured.err


def test_known_gap_requires_reason() -> None:
    import validate_mission_promotion as mod

    with pytest.raises(SystemExit):
        mod.main(["--require-shipped", "--known-gap", "doc-sync"])

def test_require_ready_and_require_shipped_are_mutually_exclusive() -> None:
    import validate_mission_promotion as mod

    with pytest.raises(SystemExit) as excinfo:
        mod.main(["--require-ready", "cleanup", "--require-shipped"])
    assert excinfo.value.code == 2


def test_known_gap_requires_require_shipped() -> None:
    import validate_mission_promotion as mod

    with pytest.raises(SystemExit) as excinfo:
        mod.main(["--known-gap", "doc-sync:temporary gap"])
    assert excinfo.value.code == 2



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


def test_promotion_gate_tolerates_unreadable_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed/non-UTF8 readiness or progress docs mark the mission not-ready
    instead of crashing assess_all_exploratory with a raw traceback."""
    from lib.mission_promotion import _fleet_outcome_valid, _progress_substantive

    # Broken YAML frontmatter -> yaml.YAMLError -> not valid (not a crash).
    broken_yaml = tmp_path / "broken-readiness.md"
    broken_yaml.write_text(
        "---\nfleet-outcome:\n  status: done\n :\n - [unbalanced\n---\n",
        encoding="utf-8",
    )
    assert not _fleet_outcome_valid(broken_yaml)

    # Non-UTF8 bytes -> UnicodeDecodeError -> not valid (readiness + progress).
    non_utf8_readiness = tmp_path / "binary-readiness.md"
    non_utf8_readiness.write_bytes(b"---\nfleet-outcome:\n  status: \xff\xfe\n---\n")
    assert not _fleet_outcome_valid(non_utf8_readiness)

    non_utf8_progress = tmp_path / "binary-progress.md"
    non_utf8_progress.write_bytes(b"PHASE: DONE\nTASK \xff\xfe\n")
    assert not _progress_substantive(non_utf8_progress)

    # OSError on read (e.g. transient I/O failure) -> not valid, no traceback.
    real_read = Path.read_text

    def boom_read(self, *args, **kwargs):
        if self in (non_utf8_readiness, non_utf8_progress):
            raise OSError("transient read failure")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom_read)
    assert not _fleet_outcome_valid(non_utf8_readiness)
    assert not _progress_substantive(non_utf8_progress)


def test_promotion_gate_survives_one_broken_mission(tmp_path: Path) -> None:
    """One unreadable mission doc must not abort the whole exploratory scan."""
    from lib.mission_promotion import assess_all_exploratory

    missions = tmp_path / "docs" / "exploratory" / "missions"
    good = missions / "good"
    bad = missions / "bad"
    good.mkdir(parents=True)
    bad.mkdir(parents=True)
    (good / "SKILL.md").write_text("x", encoding="utf-8")
    (bad / "SKILL.md").write_text("x", encoding="utf-8")

    # The "bad" mission has non-UTF8 readiness/progress; assess must not raise.
    (tmp_path / "docs" / "bad-readiness.md").write_bytes(b"---\n\xff\xfe\n---\n")
    (tmp_path / "docs" / "bad-progress.md").write_bytes(b"PHASE: DONE\n\xff\xfe\n")

    reports = assess_all_exploratory(tmp_path)
    by_mission = {r.mission for r in reports}
    assert {"good", "bad"} <= by_mission
    bad_report = next(r for r in reports if r.mission == "bad")
    assert not bad_report.ready
    assert "readiness" in bad_report.missing
    assert "progress" in bad_report.missing


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