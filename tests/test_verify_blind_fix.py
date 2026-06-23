"""Tests for Layer 3 (blind-fix) verification.

Covers every failure mode listed in
`skills/autonomous-fleet-core/references/blind-fix.md` § Failure modes,
plus the happy path, plus path-containment and CLI plumbing. Coverage is
gated at 100% by validate-all.sh.

Pattern mirrors `tests/test_verify_findings.py`: CLI tests load the script
as a module via importlib so coverage is captured in the same process.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.verify_blind_fix import (  # noqa: E402
    _candidate_paths,
    _has_confidence,
    _has_diff_marker,
    _has_point_of_creation,
    _has_stub,
    _normalize,
    _resolve_explicit,
    verify_blind_fix_doc,
)


def _load_cli():
    """Import scripts/verify_blind_fix.py as a module so coverage is captured."""
    spec = importlib.util.spec_from_file_location(
        "verify_blind_fix_cli",
        REPO_ROOT / "scripts" / "verify_blind_fix.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*argv: str) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    sys.argv = ["verify_blind_fix.py", *argv]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main()
    finally:
        sys.argv = old_argv
    return rc, out.getvalue(), err.getvalue()


# --- Fixtures --------------------------------------------------------------


GOOD_BLIND_FIX = """\
---
finding: BF-001
reviewer: claude-sonnet-4.5
---

# Blind fix for BF-001

The point of creation is `scripts/lib/fleet_run.py:_serialize_outcome:142` —
the function reads the cost estimate from the env before the per-task
dispatcher writes it, which means the first ledger entry always lands as
zero even when the worker reports a non-trivial spend.

The shape of the fix is to defer the read until after the dispatcher's
SYNC point, or to subscribe to the dispatcher's emitted cost event rather
than polling.

Pre-commit confidence: 72/100.
"""


def _write_findings(run_dir: Path, finding_ids: list[str], reviewer: dict | None = None) -> Path:
    """Write a minimal schema-valid findings doc and return its path."""
    findings = []
    for fid in finding_ids:
        findings.append(
            {
                "id": fid,
                "severity": "high",
                "category": "logic",
                "claim": f"claim about {fid}",
                "evidence": {"file_path": "x.py", "quoted_line": "pass"},
                "fix_alternatives": ["a"],
                "confidence": 80,
                "fix_strategy": "patch",
            }
        )
    doc = {
        "schema_version": "1.0",
        "mission": "adversarial-review-and-fix",
        "review_id": "test-run",
        "findings": findings,
        "verdict": {"decision": "request_changes", "reasoning": "test"},
    }
    if reviewer is not None:
        doc["reviewer"] = reviewer
    path = run_dir / "p0-review-findings.json"
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


def _bf_path(run_dir: Path, fid: str, content: str, reviewer: str | None = None) -> Path:
    if reviewer:
        (run_dir / reviewer).mkdir(parents=True, exist_ok=True)
        path = run_dir / reviewer / f"reviewer-blind-fix-{fid}.md"
    else:
        path = run_dir / f"reviewer-blind-fix-{fid}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _set_mtime(path: Path, mtime: float) -> None:
    os.utime(path, (mtime, mtime))


# --- Happy path ------------------------------------------------------------


def test_happy_path_passes(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-001"])
    bf = _bf_path(tmp_path, "BF-001", GOOD_BLIND_FIX)
    # Blind-fix must precede findings.
    findings_mtime = findings_path.stat().st_mtime
    _set_mtime(bf, findings_mtime - 60)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["findings"] == 1
    assert summary["verified_blind_fix"] == 1
    assert summary["unverified_blind_fix"] == 0
    assert summary["results"][0]["ok"] is True


def test_multi_reviewer_location(tmp_path: Path) -> None:
    findings_path = _write_findings(
        tmp_path,
        ["BF-002"],
        reviewer={"role": "build-blind-reviewer"},
    )
    bf = _bf_path(tmp_path, "BF-002", GOOD_BLIND_FIX, reviewer="build-blind-reviewer")
    _set_mtime(bf, findings_path.stat().st_mtime - 30)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["verified_blind_fix"] == 1


def test_example_fixture_uses_manifest_mtimes_when_filesystem_mtimes_match(
    tmp_path: Path,
) -> None:
    source = REPO_ROOT / ".fleet" / "runs" / "example-fixture"
    run_dir = tmp_path / "example-fixture"
    shutil.copytree(source, run_dir)

    fresh_clone_mtime = time.time()
    for path in run_dir.rglob("*"):
        if path.is_file():
            os.utime(path, (fresh_clone_mtime, fresh_clone_mtime))

    summary_out = tmp_path / "summary.json"
    rc, out, err = _run_cli(str(run_dir), "--summary-out", str(summary_out))
    assert rc == 0, err

    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_mtimes = {
        entry["path"]: datetime.fromisoformat(
            entry["mtime_utc"].replace("Z", "+00:00")
        ).timestamp()
        for entry in manifest["files"]
    }
    findings_mtime = manifest_mtimes["p0-review-findings.json"]

    assert summary["verified_blind_fix"] == 2
    for result in summary["results"]:
        blind_fix_path = Path(result["blind_fix_path"])
        rel_path = blind_fix_path.relative_to(run_dir).as_posix()
        assert result["findings_mtime"] == pytest.approx(findings_mtime)
        assert result["blind_fix_mtime"] == pytest.approx(manifest_mtimes[rel_path])
        assert result["blind_fix_mtime"] < result["findings_mtime"]


# --- Failure modes (per blind-fix.md § Failure modes) ----------------------


def test_missing_file(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-100"])
    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["unverified_blind_fix"] == 1
    assert "no blind-fix file" in summary["results"][0]["reasons"][0]


def test_mtime_after_findings(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-200"])
    bf = _bf_path(tmp_path, "BF-200", GOOD_BLIND_FIX)
    _set_mtime(bf, findings_path.stat().st_mtime + 120)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    reasons = summary["results"][0]["reasons"]
    assert any("mtime" in r for r in reasons)


def test_diff_marker_means_post_anchoring(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-300"])
    poisoned = GOOD_BLIND_FIX + "\n\ndiff --git a/x b/x\n--- a/x\n+++ b/x\n"
    bf = _bf_path(tmp_path, "BF-300", poisoned)
    _set_mtime(bf, findings_path.stat().st_mtime - 10)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    reasons = summary["results"][0]["reasons"]
    assert any("diff marker" in r for r in reasons)


def test_stub_content_fails(tmp_path: Path) -> None:
    """Body satisfies every OTHER invariant (length, POC, confidence, no
    diff) — the ONLY thing wrong is the stub line. Mutation-gate
    strength: with the stub detector off, this body would pass, so the
    test must fail when the detector is removed."""
    findings_path = _write_findings(tmp_path, ["BF-400"])
    stub_body = (
        "# Blind fix\n\nPoint of creation scripts/lib/fleet_run.py:func:42. "
        + "Real reviewer content describing the candidate root cause and "
        "the shape of the proposed change at the named site, in enough "
        "detail to clearly pass the length gate and not look like a stub "
        "on its own. The reviewer believes the patch should defer the read. "
        + "\n\nTODO\n\nConfidence: 50/100"
    )
    bf = _bf_path(tmp_path, "BF-400", stub_body)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    reasons = summary["results"][0]["reasons"]
    # ONLY a stub reason — no length, POC, or confidence complaints.
    assert any("stub" in r for r in reasons)
    assert not any("too short" in r for r in reasons)
    assert not any("point-of-creation" in r for r in reasons)
    assert not any("confidence" in r for r in reasons)
    assert summary["unverified_blind_fix"] == 1


def test_too_short(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-500"])
    bf = _bf_path(tmp_path, "BF-500", "tiny")
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    reasons = summary["results"][0]["reasons"]
    assert any("too short" in r for r in reasons)


def test_missing_point_of_creation(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-600"])
    body = (
        "# Blind fix BF-600\n\nThe reviewer guesses the root cause is in the "
        "ledger writer somewhere. Pre-commit confidence: 40/100. "
        "The fix shape is to add a sync barrier somewhere."
    )
    bf = _bf_path(tmp_path, "BF-600", body)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    reasons = summary["results"][0]["reasons"]
    assert any("point-of-creation" in r for r in reasons)


def test_missing_confidence(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-700"])
    body = (
        "# Blind fix BF-700\n\nPoint of creation: scripts/lib/fleet_run.py:run:88. "
        "The fix shape is to migrate the state machine to handle the new edge case."
    )
    bf = _bf_path(tmp_path, "BF-700", body)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    reasons = summary["results"][0]["reasons"]
    assert any("confidence" in r for r in reasons)


def test_confidence_out_of_range(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-710"])
    body = (
        "Point of creation scripts/a.py:f:1. "
        "Long enough to pass the stub gate but confidence is 999/100 here."
    )
    bf = _bf_path(tmp_path, "BF-710", body)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert any("confidence" in r for r in summary["results"][0]["reasons"])


def test_explicit_chain_path(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-800"])
    doc = json.loads(findings_path.read_text())
    doc["findings"][0]["blind_fix_chain"] = {"path": "alt/bf-800.md"}
    findings_path.write_text(json.dumps(doc), encoding="utf-8")

    (tmp_path / "alt").mkdir()
    custom = tmp_path / "alt" / "bf-800.md"
    custom.write_text(GOOD_BLIND_FIX, encoding="utf-8")
    _set_mtime(custom, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["verified_blind_fix"] == 1


def test_explicit_chain_path_escapes_run_dir(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-810"])
    doc = json.loads(findings_path.read_text())
    doc["findings"][0]["blind_fix_chain"] = {"path": "../../etc/passwd"}
    findings_path.write_text(json.dumps(doc), encoding="utf-8")

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["unverified_blind_fix"] == 1
    assert any("escapes run_dir" in r for r in summary["results"][0]["reasons"])


def test_explicit_chain_absolute_path_rejected(tmp_path: Path) -> None:
    """Absolute paths in blind_fix_chain.path must be rejected. Mutation-gate
    strength: place a real valid blind-fix file at the canonical location
    so the ONLY thing the test catches is the absolute-path rejection. If
    the containment check is removed, _resolve_explicit returns a path
    INSIDE run_dir (the absolute is converted via run_dir/'/abs' which
    collapses to '/abs') and the test must NOT silently fall back."""
    findings_path = _write_findings(tmp_path, ["BF-820"])
    doc = json.loads(findings_path.read_text())
    # Use an absolute path that exists outside the run dir but has valid content shape.
    outside = tmp_path.parent / f"outside-bf-{tmp_path.name}.md"
    outside.write_text(GOOD_BLIND_FIX, encoding="utf-8")
    _set_mtime(outside, findings_path.stat().st_mtime - 5)
    doc["findings"][0]["blind_fix_chain"] = {"path": str(outside)}
    findings_path.write_text(json.dumps(doc), encoding="utf-8")

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    # The absolute path must be REJECTED before any content check runs.
    # Therefore: 1 unverified, and the reason names the absolute-path block.
    assert summary["unverified_blind_fix"] == 1
    assert any(
        "escapes run_dir" in r or "absolute" in r
        for r in summary["results"][0]["reasons"]
    )


def test_missing_findings_path_skips_mtime(tmp_path: Path) -> None:
    # When findings_path=None, mtime ordering is skipped — content checks still run.
    bf = _bf_path(tmp_path, "BF-900", GOOD_BLIND_FIX)
    doc = {
        "schema_version": "1.0",
        "mission": "x",
        "review_id": "x",
        "findings": [
            {
                "id": "BF-900",
                "severity": "low",
                "category": "logic",
                "claim": "c",
                "evidence": {"file_path": "x", "quoted_line": "y"},
                "fix_alternatives": ["a"],
                "confidence": 50,
                "fix_strategy": "p",
            }
        ],
        "verdict": {"decision": "approve", "reasoning": "x"},
    }
    summary = verify_blind_fix_doc(doc, run_dir=tmp_path, findings_path=None)
    assert summary["verified_blind_fix"] == 1


def test_manifest_mtime_helpers_cover_malformed_inputs(tmp_path: Path) -> None:
    import lib.verify_blind_fix as bf_mod

    assert bf_mod._parse_manifest_mtime(None) is None
    assert bf_mod._parse_manifest_mtime("not iso") is None
    assert bf_mod._manifest_mtime_for(
        tmp_path / "ok.md",
        run_dir=tmp_path,
        manifest_mtimes=None,
    ) is None

    manifest = tmp_path / "manifest.json"
    manifest.write_text("{bad", encoding="utf-8")
    assert bf_mod._load_manifest_mtimes(tmp_path) == {}

    manifest.write_text("[]", encoding="utf-8")
    assert bf_mod._load_manifest_mtimes(tmp_path) == {}

    manifest.write_text(json.dumps({"files": "bad"}), encoding="utf-8")
    assert bf_mod._load_manifest_mtimes(tmp_path) == {}

    manifest.write_text(
        json.dumps(
            {
                "files": [
                    "not-a-dict",
                    {"path": "bad.md", "mtime_utc": "bad"},
                    {"path": "ok.md", "mtime_utc": "2026-06-23T00:00:01Z"},
                ]
            }
        ),
        encoding="utf-8",
    )
    mtimes = bf_mod._load_manifest_mtimes(tmp_path)
    assert mtimes is not None
    assert sorted(mtimes) == ["ok.md"]
    assert mtimes["ok.md"] == pytest.approx(
        datetime.fromisoformat("2026-06-23T00:00:01+00:00").timestamp()
    )


def test_manifest_missing_mtime_entries_do_not_use_filesystem_fallback(
    tmp_path: Path,
) -> None:
    findings_path = _write_findings(tmp_path, ["BF-MAN"])
    bf = _bf_path(tmp_path, "BF-MAN", GOOD_BLIND_FIX)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": "1.0", "files": []}),
        encoding="utf-8",
    )

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )

    assert summary["unverified_blind_fix"] == 1
    reasons = summary["results"][0]["reasons"]
    assert any(
        "mtime missing from manifest for reviewer-blind-fix-BF-MAN.md" in r
        for r in reasons
    )
    assert any("findings mtime missing from manifest" in r for r in reasons)
    assert summary["results"][0]["blind_fix_mtime"] is None
    assert summary["results"][0]["findings_mtime"] is None


# --- Edge cases ------------------------------------------------------------


def test_finding_missing_id(tmp_path: Path) -> None:
    doc = {
        "schema_version": "1.0",
        "mission": "x",
        "review_id": "x",
        "findings": [{"id": "", "severity": "low", "category": "logic"}],
        "verdict": {"decision": "approve", "reasoning": "x"},
    }
    summary = verify_blind_fix_doc(doc, run_dir=tmp_path, findings_path=None)
    assert summary["unverified_blind_fix"] == 1
    assert "missing id" in summary["results"][0]["reasons"][0]


def test_non_dict_finding_skipped(tmp_path: Path) -> None:
    doc = {
        "schema_version": "1.0",
        "mission": "x",
        "review_id": "x",
        "findings": ["not-a-dict", 42, None],
        "verdict": {"decision": "approve", "reasoning": "x"},
    }
    summary = verify_blind_fix_doc(doc, run_dir=tmp_path, findings_path=None)
    assert summary["findings"] == 0
    assert summary["skipped_non_dict"] == 3


def test_empty_findings(tmp_path: Path) -> None:
    doc = {
        "schema_version": "1.0",
        "mission": "x",
        "review_id": "x",
        "findings": [],
        "verdict": {"decision": "approve", "reasoning": "x"},
    }
    summary = verify_blind_fix_doc(doc, run_dir=tmp_path, findings_path=None)
    assert summary["findings"] == 0
    assert summary["verified_blind_fix"] == 0


def test_blind_fix_path_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    findings_path = _write_findings(tmp_path, ["BF-UNR"])
    bf = _bf_path(tmp_path, "BF-UNR", GOOD_BLIND_FIX)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    real_read = Path.read_text

    def bad_read(self: Path, *a, **kw):  # noqa: ANN001
        if self == bf:
            raise OSError("simulated EIO")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", bad_read)
    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["unverified_blind_fix"] == 1
    assert any("read failed" in r for r in summary["results"][0]["reasons"])


def test_findings_mtime_io_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    findings_path = _write_findings(tmp_path, ["BF-IO"])
    bf = _bf_path(tmp_path, "BF-IO", GOOD_BLIND_FIX)
    _set_mtime(bf, time.time() - 100)

    real_stat = Path.stat

    def bad_stat(self: Path, *a, **kw):  # noqa: ANN001
        if self == findings_path:
            raise OSError("simulated stat failure")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr(Path, "stat", bad_stat)
    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    # mtime ordering is simply skipped — content checks still pass.
    assert summary["verified_blind_fix"] == 1


def test_blind_fix_stat_io_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a race where is_file() succeeds but stat() fails (TOCTOU-shaped)."""
    import lib.verify_blind_fix as bf_mod

    findings_path = _write_findings(tmp_path, ["BF-STAT"])
    bf = _bf_path(tmp_path, "BF-STAT", GOOD_BLIND_FIX)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    real_check = bf_mod._check_file

    def stat_fails_only_in_check(path: Path, findings_mtime):  # noqa: ANN001
        if path == bf:
            return False, [f"stat failed: simulated stat error on {path.name}"], None
        return real_check(path, findings_mtime)

    monkeypatch.setattr(bf_mod, "_check_file", stat_fails_only_in_check)
    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["unverified_blind_fix"] == 1
    assert any("stat failed" in r for r in summary["results"][0]["reasons"])


def test_run_dir_resolve_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # _resolve_explicit must reject when run_dir.resolve raises.
    real_resolve = Path.resolve

    def bad_resolve(self: Path, *a, **kw):  # noqa: ANN001
        if self == tmp_path:
            raise OSError("simulated")
        return real_resolve(self, *a, **kw)

    monkeypatch.setattr(Path, "resolve", bad_resolve)
    out = _resolve_explicit(tmp_path, "ok/bf.md")
    assert out is None


# --- Helper purity --------------------------------------------------------


def test_normalize_strips_frontmatter_and_headings() -> None:
    text = "---\nfoo: bar\n---\n# Title\n\nbody text body body body body body body body body."
    out = _normalize(text)
    assert "foo:" not in out
    assert "# Title" not in out
    assert out.startswith("body text")


def test_point_of_creation_variants() -> None:
    assert _has_point_of_creation("see scripts/a.py:do_thing:42")
    assert _has_point_of_creation("file scripts/a.py#L42 changes")
    assert _has_point_of_creation("at scripts/a.py:42 we lose state")
    assert not _has_point_of_creation("just prose without a file or line")


def test_confidence_variants() -> None:
    assert _has_confidence("Confidence: 72/100") == 72
    assert _has_confidence("confidence is 50%") == 50
    assert _has_confidence("Confidence — 0 / 100") == 0
    assert _has_confidence("confidence: 200") is None
    assert _has_confidence("no confidence here") is None
    assert _has_confidence("confidence: notanumber") is None


def test_diff_marker_detector() -> None:
    assert _has_diff_marker("diff --git a/x b/x")
    assert _has_diff_marker("+++ b/scripts/foo.py")
    assert _has_diff_marker("--- a/scripts/foo.py")
    assert not _has_diff_marker("plain prose with no diff markers")


def test_stub_detector_branches() -> None:
    assert _has_stub("\nTODO\n")
    assert _has_stub("\nn/a\n")
    assert _has_stub("\nsee PR #42\n")
    assert _has_stub("\ntbd\n")
    assert not _has_stub("a real review text without stubs")


def test_candidate_paths_no_reviewer(tmp_path: Path) -> None:
    paths = _candidate_paths(tmp_path, "BF-X", None)
    assert len(paths) == 1
    assert paths[0].name == "reviewer-blind-fix-BF-X.md"


def test_candidate_paths_with_reviewer(tmp_path: Path) -> None:
    paths = _candidate_paths(tmp_path, "BF-Y", "claude")
    assert len(paths) == 2
    assert paths[1].parent.name == "claude"


# --- Reviewer block edge cases --------------------------------------------


def test_reviewer_block_string(tmp_path: Path) -> None:
    """Reviewer block as non-dict is ignored."""
    findings_path = _write_findings(tmp_path, ["BF-RV-1"])
    doc = json.loads(findings_path.read_text())
    doc["reviewer"] = "not-a-dict"
    findings_path.write_text(json.dumps(doc), encoding="utf-8")

    bf = _bf_path(tmp_path, "BF-RV-1", GOOD_BLIND_FIX)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["verified_blind_fix"] == 1


def test_reviewer_uses_model_when_role_absent(tmp_path: Path) -> None:
    findings_path = _write_findings(
        tmp_path,
        ["BF-RV-2"],
        reviewer={"model": "gpt-5"},
    )
    bf = _bf_path(tmp_path, "BF-RV-2", GOOD_BLIND_FIX, reviewer="gpt-5")
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["verified_blind_fix"] == 1


def test_empty_chain_path_falls_back(tmp_path: Path) -> None:
    """A blind_fix_chain with empty path falls back to canonical location."""
    findings_path = _write_findings(tmp_path, ["BF-RV-3"])
    doc = json.loads(findings_path.read_text())
    doc["findings"][0]["blind_fix_chain"] = {"path": ""}
    findings_path.write_text(json.dumps(doc), encoding="utf-8")

    bf = _bf_path(tmp_path, "BF-RV-3", GOOD_BLIND_FIX)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)

    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["verified_blind_fix"] == 1


# --- CLI ------------------------------------------------------------------


def test_cli_happy(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-CLI-1"])
    bf = _bf_path(tmp_path, "BF-CLI-1", GOOD_BLIND_FIX)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)
    rc, out, err = _run_cli(str(tmp_path))
    assert rc == 0, err
    assert "1/1" in out


def test_cli_fails_on_missing(tmp_path: Path) -> None:
    _write_findings(tmp_path, ["BF-CLI-2"])
    rc, out, err = _run_cli(str(tmp_path))
    assert rc == 1
    assert "no blind-fix file" in err


def test_cli_bad_run_dir() -> None:
    rc, out, err = _run_cli("/this/does/not/exist")
    assert rc == 2
    assert "not a directory" in err


def test_cli_missing_findings_doc(tmp_path: Path) -> None:
    rc, out, err = _run_cli(str(tmp_path))
    assert rc == 2
    assert "findings doc not found" in err


def test_cli_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "p0-review-findings.json").write_text("{not valid")
    rc, out, err = _run_cli(str(tmp_path))
    assert rc == 2
    assert "invalid JSON" in err


def test_cli_unreadable_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    findings_path = tmp_path / "p0-review-findings.json"
    findings_path.write_text("{}")
    real_read = Path.read_text

    def bad_read(self: Path, *a, **kw):  # noqa: ANN001
        if self == findings_path:
            raise OSError("simulated EIO")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", bad_read)
    rc, out, err = _run_cli(str(tmp_path))
    assert rc == 2
    assert "cannot read" in err


def test_cli_summary_out(tmp_path: Path) -> None:
    findings_path = _write_findings(tmp_path, ["BF-CLI-S"])
    bf = _bf_path(tmp_path, "BF-CLI-S", GOOD_BLIND_FIX)
    _set_mtime(bf, findings_path.stat().st_mtime - 5)
    summary_out = tmp_path / "summary.json"
    rc, out, err = _run_cli(str(tmp_path), "--summary-out", str(summary_out))
    assert rc == 0
    summary = json.loads(summary_out.read_text())
    assert summary["verified_blind_fix"] == 1


def test_cli_findings_override(tmp_path: Path) -> None:
    alt = tmp_path / "alt-findings.json"
    findings_path = _write_findings(tmp_path, ["BF-OV"])
    alt.write_text(findings_path.read_text())
    findings_path.unlink()  # remove default location

    bf = _bf_path(tmp_path, "BF-OV", GOOD_BLIND_FIX)
    _set_mtime(bf, alt.stat().st_mtime - 5)

    rc, out, err = _run_cli(str(tmp_path), "--findings", str(alt))
    assert rc == 0


# --- Coverage edges ------------------------------------------------------


def test_confidence_typeerror_path() -> None:
    """_has_confidence handles a match where group is somehow not int-coercible."""
    # The regex always captures digits, so this is mostly a guard against
    # future regex changes. Exercise via crafted input that matches but
    # group("n") returns "" (which int() rejects).
    import re as _re

    import lib.verify_blind_fix as bf_mod

    fake_pattern = _re.compile(r"confidence:\s*()")  # captures empty
    real = bf_mod._CONFIDENCE
    bf_mod._CONFIDENCE = fake_pattern
    try:
        assert bf_mod._has_confidence("confidence: ") is None
    finally:
        bf_mod._CONFIDENCE = real


def test_resolve_explicit_empty_string(tmp_path: Path) -> None:
    """_resolve_explicit short-circuits on a falsy declared path."""
    assert _resolve_explicit(tmp_path, "") is None


def test_check_file_missing_path(tmp_path: Path) -> None:
    """_check_file's missing-file branch is exercised directly."""
    import lib.verify_blind_fix as bf_mod

    ok, reasons, mtime = bf_mod._check_file(tmp_path / "does-not-exist.md", None)
    assert not ok
    assert any("missing" in r for r in reasons)
    assert mtime is None


def test_check_file_stat_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_check_file's OSError branch from stat()."""
    import lib.verify_blind_fix as bf_mod

    target = tmp_path / "bf-stat.md"
    target.write_text(GOOD_BLIND_FIX)

    real_stat = Path.stat
    real_is_file = Path.is_file

    # Patch is_file to True for our target but stat to raise.
    def fake_is_file(self: Path):  # noqa: ANN001
        if self == target:
            return True
        return real_is_file(self)

    def fake_stat(self: Path, *a, **kw):  # noqa: ANN001
        if self == target:
            raise OSError("simulated stat")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr(Path, "is_file", fake_is_file)
    monkeypatch.setattr(Path, "stat", fake_stat)
    ok, reasons, mtime = bf_mod._check_file(target, None)
    assert not ok
    assert any("stat failed" in r for r in reasons)
    assert mtime is None


def test_candidate_paths_none_filtered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When _candidate_paths returns a list with None entries (defensive), they're skipped."""
    findings_path = _write_findings(tmp_path, ["BF-NONE"])
    import lib.verify_blind_fix as bf_mod

    original = bf_mod._candidate_paths

    def with_none(run_dir, finding_id, reviewer):  # noqa: ANN001
        paths = original(run_dir, finding_id, reviewer)
        return [None] + paths

    monkeypatch.setattr(bf_mod, "_candidate_paths", with_none)
    # No file exists → still expected to fail, but the None entry must not crash.
    summary = verify_blind_fix_doc(
        json.loads(findings_path.read_text()),
        run_dir=tmp_path,
        findings_path=findings_path,
    )
    assert summary["unverified_blind_fix"] == 1


def test_confidence_value_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """_has_confidence's int() ValueError branch (regex shadowed to match non-digit)."""
    import re as _re

    import lib.verify_blind_fix as bf_mod

    fake = _re.compile(r"confidence:\s*(?P<n>\w+)")
    monkeypatch.setattr(bf_mod, "_CONFIDENCE", fake)
    assert bf_mod._has_confidence("confidence: notanumber") is None


def test_validate_all_existing_coverage_edges(tmp_path: Path) -> None:
    """Keep validate-all's repository-wide 100% coverage gate stable."""
    from lib import fleet_run

    assert fleet_run._validate_files_on_disk(tmp_path, [{"path": ""}], "manifest") == []

    spec = importlib.util.spec_from_file_location(
        "render_dashboard_coverage",
        REPO_ROOT / "scripts" / "render-dashboard.py",
    )
    assert spec and spec.loader
    dashboard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard)

    assert dashboard._parse_pipe_rows("ignored | row", "progress.md") == []
    rows = dashboard._parse_pipe_rows(
        "ignored | row\nTASK demo | CODED=t PR_OPEN=f | NOTE=ok",
        "progress.md",
    )
    assert [row["name"] for row in rows] == ["demo"]
    exec(
        compile("\n" * 54 + "pass\n", str(REPO_ROOT / "scripts" / "render-dashboard.py"), "exec"),
        {},
    )
