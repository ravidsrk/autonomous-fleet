"""Tests for the stop-verify lib + CLI.

Three surfaces under test:
  - lib.stop_verify.evaluate — orchestrator returning a Verdict
  - lib.stop_verify.detect_* — individual evidence detectors
  - scripts/stop_verify.py main() — CLI exit + JSON decision contract

The library is the meat of the gate; the CLI is a thin bridge to Claude
Code's Stop-hook JSON. The discipline tests EXIST to enforce:
  1. Stale evidence (outside window) is NEVER counted as fresh
  2. Disabled state always wins (no surprises for kill-switch users)
  3. Internal errors fail-open (CLI exits 0, allows session, logs warning)
  4. BLOCK message includes actionable remediation steps (no vague blocks)
  5. Hook NEVER raises to the CC harness regardless of FS state
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.stop_verify import (  # noqa: E402
    DEFAULT_WINDOW_MIN,
    EVID_PATTERN,
    MAX_WINDOW_SEC,
    MIN_WINDOW_SEC,
    StopVerifyConfig,
    Verdict,
    detect_e2e_artifact_evidence,
    detect_progress_flag_evidence,
    detect_readiness_evidence,
    detect_test_artifact_evidence,
    detect_verify_summary_evidence,
    evaluate,
)


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "stop_verify_cli", ROOT / "scripts" / "stop_verify.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _set_mtime(p: Path, ago_sec: float) -> None:
    """Force a file's mtime to N seconds ago. Used to simulate stale or fresh
    artifacts deterministically — relying on real wall-clock pauses would
    make tests both slow and flaky."""
    t = time.time() - ago_sec
    os.utime(p, (t, t))


# ───────────────────────────────────────────────────────────────────────
# Config + normalization
# ───────────────────────────────────────────────────────────────────────


def test_config_normalises_window_into_bounds(tmp_path: Path):
    cfg = StopVerifyConfig(window_sec=1, repo_root=tmp_path).normalised()
    assert cfg.window_sec >= MIN_WINDOW_SEC
    assert cfg.window_sec <= MAX_WINDOW_SEC


def test_config_normalises_huge_window_to_max(tmp_path: Path):
    cfg = StopVerifyConfig(window_sec=10**9, repo_root=tmp_path).normalised()
    assert cfg.window_sec == MAX_WINDOW_SEC


def test_config_normalises_negative_window_to_min(tmp_path: Path):
    cfg = StopVerifyConfig(window_sec=-500, repo_root=tmp_path).normalised()
    assert cfg.window_sec == MIN_WINDOW_SEC


def test_config_normalises_min_kinds_at_least_one(tmp_path: Path):
    cfg = StopVerifyConfig(
        min_evidence_kinds=0, repo_root=tmp_path
    ).normalised()
    assert cfg.min_evidence_kinds == 1


def test_default_window_minutes_is_thirty():
    """Pin the default. claude-code-orchestra and multi-llm both ship a
    30-min default; we match. A casual edit to e.g. 5min would crater the
    gate's false-positive rate; this test makes the change visible."""
    assert DEFAULT_WINDOW_MIN == 30


# ───────────────────────────────────────────────────────────────────────
# Disabled / kill switch
# ───────────────────────────────────────────────────────────────────────


def test_evaluate_disabled_via_config_returns_allow(tmp_path: Path):
    cfg = StopVerifyConfig(repo_root=tmp_path, disabled=True)
    v = evaluate(cfg)
    assert v.allow is True
    assert "disabled" in v.reason
    # Disabled state should NOT trigger any detector — pin via empty evidence.
    assert v.evidence == []


def test_evaluate_disabled_via_env_returns_allow(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FLEET_DISABLE_STOP_VERIFY", "1")
    v = evaluate(StopVerifyConfig(repo_root=tmp_path))
    assert v.allow is True
    assert "disabled" in v.reason


@pytest.mark.parametrize("val", ["1", "true", "yes", "TRUE", "Yes"])
def test_env_disable_accepts_truthy_synonyms(tmp_path: Path, monkeypatch, val):
    monkeypatch.setenv("FLEET_DISABLE_STOP_VERIFY", val)
    assert evaluate(StopVerifyConfig(repo_root=tmp_path)).allow is True


@pytest.mark.parametrize("val", ["0", "false", "no", "", "  "])
def test_env_disable_rejects_falsy_synonyms(tmp_path: Path, monkeypatch, val):
    monkeypatch.setenv("FLEET_DISABLE_STOP_VERIFY", val)
    v = evaluate(StopVerifyConfig(repo_root=tmp_path))
    # No evidence in tmp_path -> BLOCK. Pin the contract: a non-truthy
    # FLEET_DISABLE_STOP_VERIFY MUST NOT silently disable the gate.
    assert v.allow is False


# ───────────────────────────────────────────────────────────────────────
# Pattern matching primitives (the regex DOES NOT match prose mentions)
# ───────────────────────────────────────────────────────────────────────


def test_evid_pattern_matches_explicit_true_only():
    assert EVID_PATTERN.search("EVID=true")
    assert EVID_PATTERN.search("- EVID = true (closed by PR#42)")
    assert EVID_PATTERN.search("evid=true")  # case-insensitive
    # Prose mentions WITHOUT =true must NOT match. This is the discipline
    # property — a paragraph discussing EVID can't satisfy the gate.
    assert not EVID_PATTERN.search("EVID is the close test for findings.")
    assert not EVID_PATTERN.search("EVID=false")
    assert not EVID_PATTERN.search("EVID:true")  # wrong separator


# ───────────────────────────────────────────────────────────────────────
# Progress flag detector
# ───────────────────────────────────────────────────────────────────────


def test_progress_flag_detector_finds_fresh_evid(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-progress.md"
    f.write_text("Fix loop\n- F-001 CODED EVID=true PR_OPEN MERGED\n")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_progress_flag_evidence(cfg, time.time())
    assert len(hits) == 1
    assert hits[0].kind == "evid_flag"
    assert hits[0].path == f


def test_progress_flag_detector_finds_fresh_wt_clean(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-progress.md"
    f.write_text("Cleanup\nWT_CLEAN=true on worker-3\n")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_progress_flag_evidence(cfg, time.time())
    assert len(hits) == 1
    assert hits[0].kind == "wt_clean_flag"


def test_progress_flag_detector_ignores_stale_files(tmp_path: Path):
    """The single most important behavior of the detector: STALE evidence
    does not count. A progress doc from last week with EVID=true must NOT
    satisfy today's stop-verify gate."""
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-progress.md"
    f.write_text("- F-001 EVID=true\n")
    # 2 hours ago, but window is 30min (default).
    _set_mtime(f, ago_sec=2 * 60 * 60)
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_progress_flag_evidence(cfg, time.time())
    assert hits == [], "stale progress doc must NOT satisfy the gate"


def test_progress_flag_detector_ignores_prose_mentions(tmp_path: Path):
    """A ledger that DISCUSSES EVID without ever asserting EVID=true must
    not count — discipline lives in the assertion, not the prose."""
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-progress.md"
    f.write_text(
        "We discussed EVID, the close test for findings, but did not "
        "verify any. Will follow up tomorrow.\n"
    )
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_progress_flag_evidence(cfg, time.time())
    assert hits == []


def test_progress_flag_detector_ignores_evid_false(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-progress.md"
    f.write_text("- F-001 EVID=false (still reproduces)\n")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_progress_flag_evidence(cfg, time.time())
    assert hits == []


def test_progress_flag_detector_handles_unreadable_file(tmp_path: Path):
    """Hostile FS: a file matching the glob but unreadable must not crash
    the detector. The hook must never raise to the CC harness."""
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-progress.md"
    f.write_text("EVID=true")
    os.chmod(f, 0o000)
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    try:
        hits = detect_progress_flag_evidence(cfg, time.time())
        # Best case: silent skip. Worst-acceptable case: no hits but no raise.
        # Either way, no exception.
        assert isinstance(hits, list)
    finally:
        os.chmod(f, 0o644)  # restore for cleanup


# ───────────────────────────────────────────────────────────────────────
# Readiness detector
# ───────────────────────────────────────────────────────────────────────


def test_readiness_detector_finds_e2e_verified(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-readiness.md"
    f.write_text(
        "---\n"
        "fleet-outcome:\n"
        "  mission: take-product-to-completion\n"
        "  status: done\n"
        "  metrics:\n"
        "    e2e_verified: true\n"
        "---\n"
        "# Done.\n"
    )
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_readiness_evidence(cfg, time.time())
    assert len(hits) == 1
    assert hits[0].kind == "e2e_verified"


def test_readiness_detector_falls_back_to_status_done(tmp_path: Path):
    """When e2e_verified isn't required by the mission, status:done alone is
    weaker but valid evidence."""
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-readiness.md"
    f.write_text(
        "---\n"
        "fleet-outcome:\n"
        "  mission: cleanup\n"
        "  status: done\n"
        "---\n"
    )
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_readiness_evidence(cfg, time.time())
    assert len(hits) == 1
    assert hits[0].kind == "status_done"


def test_readiness_detector_prefers_e2e_over_status_done(tmp_path: Path):
    """When BOTH e2e_verified:true AND status:done appear in the same doc,
    we record the stronger evidence (e2e_verified) only. Avoids
    double-counting the same readiness as two evidence kinds."""
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-readiness.md"
    f.write_text(
        "---\n"
        "fleet-outcome:\n"
        "  status: done\n"
        "  metrics:\n"
        "    e2e_verified: true\n"
        "---\n"
    )
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_readiness_evidence(cfg, time.time())
    kinds = [h.kind for h in hits]
    assert kinds == ["e2e_verified"], "single readiness must produce single hit"


def test_readiness_detector_ignores_stale_doc(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-readiness.md"
    f.write_text("---\nstatus: done\ne2e_verified: true\n---\n")
    _set_mtime(f, ago_sec=2 * 60 * 60)
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    assert detect_readiness_evidence(cfg, time.time()) == []


def test_readiness_detector_ignores_status_partial(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "mission-readiness.md"
    f.write_text("---\nstatus: partial\n---\n")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    assert detect_readiness_evidence(cfg, time.time()) == []


# ───────────────────────────────────────────────────────────────────────
# Verify-summary detector (Commit 1's bridge)
# ───────────────────────────────────────────────────────────────────────


def test_verify_summary_detector_accepts_zero_unverified(tmp_path: Path):
    runs = tmp_path / ".fleet" / "runs" / "abc123"
    runs.mkdir(parents=True)
    f = runs / "p0-verify-summary.json"
    f.write_text(
        json.dumps(
            {
                "total_findings": 5,
                "verified_findings": 5,
                "unverified_findings": 0,
                "auto_applicable_findings": 2,
                "human_gated_findings": 3,
            }
        )
    )
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_verify_summary_evidence(cfg, time.time())
    assert len(hits) == 1
    assert hits[0].kind == "verify_summary"
    assert "5/5" in hits[0].detail


def test_verify_summary_detector_rejects_nonzero_unverified(tmp_path: Path):
    """The Commit-1 schema gate blocks the fix loop on unverified > 0. The
    stop-verify hook must NOT count a failing verify as evidence — that
    would silently undo the gate."""
    runs = tmp_path / ".fleet" / "runs" / "abc123"
    runs.mkdir(parents=True)
    f = runs / "p0-verify-summary.json"
    f.write_text(
        json.dumps(
            {"total_findings": 5, "verified_findings": 4, "unverified_findings": 1}
        )
    )
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    assert detect_verify_summary_evidence(cfg, time.time()) == []


def test_verify_summary_detector_ignores_malformed_json(tmp_path: Path):
    runs = tmp_path / ".fleet" / "runs" / "abc"
    runs.mkdir(parents=True)
    (runs / "p0-verify-summary.json").write_text("{ not json")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    assert detect_verify_summary_evidence(cfg, time.time()) == []


def test_verify_summary_detector_ignores_array_payload(tmp_path: Path):
    """Defense: JSON could be valid but wrong shape (an array instead of an
    object). Must not crash."""
    runs = tmp_path / ".fleet" / "runs" / "abc"
    runs.mkdir(parents=True)
    (runs / "p0-verify-summary.json").write_text("[1, 2, 3]")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    assert detect_verify_summary_evidence(cfg, time.time()) == []


def test_verify_summary_detector_ignores_stale_summary(tmp_path: Path):
    runs = tmp_path / ".fleet" / "runs" / "abc"
    runs.mkdir(parents=True)
    f = runs / "p0-verify-summary.json"
    f.write_text('{"unverified_findings": 0, "total_findings": 1, "verified_findings": 1}')
    _set_mtime(f, ago_sec=2 * 60 * 60)
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    assert detect_verify_summary_evidence(cfg, time.time()) == []


# ───────────────────────────────────────────────────────────────────────
# Test-artifact + e2e-artifact detectors
# ───────────────────────────────────────────────────────────────────────


def test_test_artifact_detector_finds_pytest_cache(tmp_path: Path):
    cache = tmp_path / ".pytest_cache" / "v"
    cache.mkdir(parents=True)
    (cache / "lastfailed").write_text("{}")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_test_artifact_evidence(cfg, time.time())
    assert any(h.kind == "test_artifact" for h in hits)


def test_test_artifact_detector_deduplicates_by_parent_dir(tmp_path: Path):
    """One pytest cache dir of 50 files must yield ONE hit, not 50. Keeps
    the BLOCK message readable when artifacts pile up."""
    cache = tmp_path / "coverage"
    cache.mkdir()
    for i in range(50):
        (cache / f"f{i}.json").write_text("{}")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_test_artifact_evidence(cfg, time.time())
    test_hits = [h for h in hits if h.kind == "test_artifact"]
    assert len(test_hits) == 1


def test_test_artifact_detector_ignores_stale_cache(tmp_path: Path):
    cache = tmp_path / ".pytest_cache" / "v"
    cache.mkdir(parents=True)
    f = cache / "lastfailed"
    f.write_text("{}")
    _set_mtime(f, ago_sec=2 * 60 * 60)
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    assert detect_test_artifact_evidence(cfg, time.time()) == []


def test_e2e_artifact_detector_finds_playwright_png(tmp_path: Path):
    pw = tmp_path / "playwright-report"
    pw.mkdir()
    (pw / "screenshot.png").write_bytes(b"\x89PNG\r\n")
    cfg = StopVerifyConfig(repo_root=tmp_path).normalised()
    hits = detect_e2e_artifact_evidence(cfg, time.time())
    assert any(h.kind == "e2e_artifact" for h in hits)


# ───────────────────────────────────────────────────────────────────────
# evaluate() — orchestrator composition
# ───────────────────────────────────────────────────────────────────────


def test_evaluate_blocks_on_empty_repo(tmp_path: Path):
    v = evaluate(StopVerifyConfig(repo_root=tmp_path))
    assert v.allow is False
    assert "BLOCKED" in v.reason
    # The reason must include the actionable remediation list — vague
    # blocks cause retry loops. Pin the keywords.
    assert "To unblock" in v.reason
    assert "FLEET_DISABLE_STOP_VERIFY=1" in v.reason


def test_evaluate_allows_when_any_single_evidence_kind_matches(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mission-progress.md").write_text("EVID=true\n")
    v = evaluate(StopVerifyConfig(repo_root=tmp_path))
    assert v.allow is True
    assert v.counts.get("evid_flag", 0) >= 1


def test_evaluate_respects_min_evidence_kinds(tmp_path: Path):
    """min_kinds=2 means a single matched kind is NOT enough."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mission-progress.md").write_text("EVID=true\n")
    v = evaluate(
        StopVerifyConfig(repo_root=tmp_path, min_evidence_kinds=2)
    )
    assert v.allow is False
    assert "at least 2 distinct kind(s)" in v.reason


def test_evaluate_strict_progress_requires_both_flags(tmp_path: Path):
    """Paranoid mode: EVID=true alone is not enough; we also need
    WT_CLEAN=true in a ledger file in window."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mission-progress.md").write_text("EVID=true\n")
    v = evaluate(
        StopVerifyConfig(repo_root=tmp_path, require_progress_flag=True)
    )
    assert v.allow is False
    assert "strict-progress mode requires both" in v.reason


def test_evaluate_strict_progress_with_both_flags_allows(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mission-progress.md").write_text(
        "- F-001 EVID=true PR_OPEN MERGED\nWT_CLEAN=true on worker-3\n"
    )
    v = evaluate(
        StopVerifyConfig(repo_root=tmp_path, require_progress_flag=True)
    )
    assert v.allow is True


def test_evaluate_distinct_kinds_counted_not_duplicates(tmp_path: Path):
    """Two readiness docs with status:done should count as ONE distinct
    evidence kind, not two. The threshold is on DISTINCT kinds, not raw
    hit count — pin it so a doc-spam attack can't satisfy a paranoid
    `min_kinds=3` setting."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a-readiness.md").write_text("---\nstatus: done\n---\n")
    (docs / "b-readiness.md").write_text("---\nstatus: done\n---\n")
    v = evaluate(
        StopVerifyConfig(repo_root=tmp_path, min_evidence_kinds=2)
    )
    # Only one distinct kind (status_done), even though two hits. min=2 -> BLOCK.
    assert v.allow is False
    assert v.counts.get("status_done") == 2


def test_evaluate_block_lists_evidence_window_in_message(tmp_path: Path):
    """A 60-minute window operator should see "60min" in the BLOCK reason,
    not the default 30. Pin this so the reason is informative."""
    v = evaluate(StopVerifyConfig(repo_root=tmp_path, window_sec=60 * 60))
    assert v.allow is False
    assert "60min" in v.reason


# ───────────────────────────────────────────────────────────────────────
# CLI integration
# ───────────────────────────────────────────────────────────────────────


def _run_cli(argv: list[str], stdin: str = "") -> tuple[int, str, str]:
    cli = _load_cli()
    old_stdin = sys.stdin
    old_argv = sys.argv
    sys.stdin = io.StringIO(stdin)
    sys.argv = ["stop_verify.py", *argv]
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main()
    finally:
        sys.stdin = old_stdin
        sys.argv = old_argv
    return rc, out.getvalue(), err.getvalue()


def test_cli_block_emits_decision_json(tmp_path: Path):
    """The CC contract: BLOCK -> stdout JSON {decision:"block", reason:...}."""
    rc, out, _err = _run_cli(["--repo", str(tmp_path)])
    assert rc == 0  # CLI MUST always exit 0
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "BLOCKED" in payload["reason"]


def test_cli_allow_emits_silent_stdout_by_default(tmp_path: Path):
    """ALLOW -> stdout is silent (CC interprets no decision as no opinion =
    session may end). Matches multi-llm-plugin-cc behavior."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x-progress.md").write_text("EVID=true\n")
    rc, out, _err = _run_cli(["--repo", str(tmp_path)])
    assert rc == 0
    assert out.strip() == ""  # silent on allow


def test_cli_allow_emits_decision_when_json_out_flag_set(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x-progress.md").write_text("EVID=true\n")
    rc, out, _err = _run_cli(["--repo", str(tmp_path), "--json-out"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["decision"] == "approve"


def test_cli_reads_repo_from_hook_input_cwd(tmp_path: Path):
    """When --repo is not passed, the CLI should fall back to the JSON
    hook input's `cwd` field. Pin the contract — CC actually does pass
    `cwd` in its Stop hook payload."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x-progress.md").write_text("EVID=true\n")
    stdin_payload = json.dumps({"session_id": "test", "cwd": str(tmp_path)})
    rc, out, _err = _run_cli([], stdin=stdin_payload)
    assert rc == 0
    # No --repo passed, but tmp_path picked up from stdin -> allow
    assert out.strip() == ""


def test_cli_reads_repo_from_claude_project_dir_env(tmp_path: Path, monkeypatch):
    """CLAUDE_PROJECT_DIR is the env var CC sets when a project is loaded.
    The CLI must honour it when --repo is not passed."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x-progress.md").write_text("EVID=true\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc, out, _err = _run_cli([])
    assert rc == 0
    assert out.strip() == ""


def test_cli_repo_flag_beats_env_and_stdin(tmp_path: Path, monkeypatch):
    """Resolution order: --repo > $CLAUDE_PROJECT_DIR > stdin cwd > os.getcwd.
    Pin the order so future contributors don't reorder it silently."""
    good = tmp_path / "good"
    bad = tmp_path / "bad"
    (good / "docs").mkdir(parents=True)
    (bad / "docs").mkdir(parents=True)
    (good / "docs" / "p-progress.md").write_text("EVID=true\n")
    # bad has nothing
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(bad))
    stdin_payload = json.dumps({"cwd": str(bad)})
    rc, out, _err = _run_cli(["--repo", str(good)], stdin=stdin_payload)
    assert rc == 0
    # --repo wins -> allow
    assert out.strip() == ""


def test_cli_swallows_malformed_stdin(tmp_path: Path):
    """A non-JSON stdin must not crash the hook (operator running by hand)."""
    rc, out, err = _run_cli(["--repo", str(tmp_path)], stdin="this is not JSON")
    assert rc == 0
    # We still get a BLOCK because tmp_path has no evidence, but the
    # malformed stdin is logged not raised.
    assert "warning" in err.lower()
    payload = json.loads(out)
    assert payload["decision"] == "block"


def test_cli_handles_missing_repo_directory_gracefully(tmp_path: Path):
    """A missing --repo must NOT crash. Fail-open with stderr warning."""
    rc, out, err = _run_cli(["--repo", str(tmp_path / "nope")])
    assert rc == 0
    assert "warning" in err.lower()
    assert "repo not a directory" in err
    # ALLOW silently (no JSON on stdout)
    assert out.strip() == ""


def test_cli_explain_writes_human_readable_to_stderr(tmp_path: Path):
    rc, _out, err = _run_cli(["--repo", str(tmp_path), "--explain"])
    assert rc == 0
    assert "stop-verify: BLOCK" in err
    assert "To unblock" in err


def test_cli_disabled_via_env_emits_silent_allow(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FLEET_DISABLE_STOP_VERIFY", "1")
    rc, out, _err = _run_cli(["--repo", str(tmp_path)])
    assert rc == 0
    assert out.strip() == ""


def test_cli_kill_switch_short_circuits_bad_repo(tmp_path: Path, monkeypatch):
    """The kill switch MUST win over a bad --repo. An operator who set
    FLEET_DISABLE_STOP_VERIFY=1 to silence the hook should see clean silence,
    not "repo not found" warnings, regardless of whether hooks.json has a
    stale --repo path baked in. Pin the ordering."""
    monkeypatch.setenv("FLEET_DISABLE_STOP_VERIFY", "1")
    rc, out, err = _run_cli(["--repo", "/this/does/not/exist"])
    assert rc == 0
    assert out.strip() == ""  # silent allow
    # No bad-repo warning should leak through. (Other warnings are fine.)
    assert "repo not a directory" not in err


def test_cli_strict_blocks_missing_repo(tmp_path: Path, monkeypatch):
    """SEC-010: FLEET_STOP_VERIFY_STRICT=1 blocks when --repo is missing."""
    monkeypatch.setenv("FLEET_STOP_VERIFY_STRICT", "1")
    rc, out, err = _run_cli(["--repo", "/this/does/not/exist", "--json"])
    assert rc == 0  # hook always exits 0; decision is in JSON
    assert "repo not a directory" in err
    assert '"decision": "block"' in out
    assert "repo not found (strict)" in out


def test_cli_default_allows_missing_repo(tmp_path: Path, monkeypatch):
    """SEC-010: default remains fail-open on bad --repo."""
    monkeypatch.delenv("FLEET_STOP_VERIFY_STRICT", raising=False)
    rc, out, err = _run_cli(["--repo", "/this/does/not/exist", "--json"])
    assert rc == 0
    assert "repo not a directory" in err
    # ALLOW emits decision:"approve" (CC hook vocabulary), not "allow".
    assert '"decision": "approve"' in out
    assert "repo not found" in out


def test_cli_fails_open_on_internal_error(tmp_path: Path, monkeypatch):
    """The fail-open guarantee: an internal exception must result in
    ALLOW + warning, never a non-zero exit, never a crash to the CC
    harness. Inject a broken evaluate() to prove the wrapper handles it."""
    cli = _load_cli()
    monkeypatch.setattr(
        cli, "evaluate", lambda cfg: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    old_stdin = sys.stdin
    old_argv = sys.argv
    sys.stdin = io.StringIO("")
    sys.argv = ["stop_verify.py", "--repo", str(tmp_path)]
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main()
    finally:
        sys.stdin = old_stdin
        sys.argv = old_argv
    err_text = err.getvalue()
    out_text = out.getvalue()
    assert rc == 0  # never crashes the harness
    assert "internal error" in err_text.lower()
    assert "boom" in err_text
    # Silent allow on stdout
    assert out_text.strip() == ""


def test_cli_strict_progress_flag_propagates_to_lib(tmp_path: Path):
    """--strict-progress must reach the lib. With only EVID=true (no
    WT_CLEAN=true), the strict-progress mode must BLOCK with the
    strict-mode message."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "p-progress.md").write_text("EVID=true\n")
    rc, out, _err = _run_cli(["--repo", str(tmp_path), "--strict-progress"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "strict-progress" in payload["reason"]


# ───────────────────────────────────────────────────────────────────────
# Hook-asset existence (the shipped artifacts must remain on disk)
# ───────────────────────────────────────────────────────────────────────


def test_shipped_hook_wrapper_exists_and_is_executable():
    """The shell wrapper is the entry point operators copy into .claude/hooks/.
    It MUST exist and MUST be executable."""
    wrapper = (
        ROOT
        / "skills"
        / "autonomous-fleet-adapter-claude-code"
        / "assets"
        / "hooks"
        / "stop-verify.sh"
    )
    assert wrapper.is_file(), f"missing hook wrapper: {wrapper}"
    assert os.access(wrapper, os.X_OK), "hook wrapper not executable"


def test_shipped_hooks_json_is_valid_json_with_stop_entry():
    """The hooks.json template must parse as valid JSON and register the
    Stop hook. Strict-mode install instructions tell operators to copy
    this file wholesale; a malformed copy would break every install."""
    hooks_json = (
        ROOT
        / "skills"
        / "autonomous-fleet-adapter-claude-code"
        / "assets"
        / "hooks"
        / "hooks.json"
    )
    assert hooks_json.is_file()
    payload = json.loads(hooks_json.read_text(encoding="utf-8"))
    assert "hooks" in payload
    assert "Stop" in payload["hooks"]
    assert isinstance(payload["hooks"]["Stop"], list)
    assert len(payload["hooks"]["Stop"]) >= 1
    # Each entry must have a `hooks` array with at least one `command` entry.
    first = payload["hooks"]["Stop"][0]
    assert "hooks" in first
    cmd_entries = first["hooks"]
    assert any(e.get("type") == "command" for e in cmd_entries)
    assert any("stop-verify.sh" in str(e.get("command", "")) for e in cmd_entries)


# --- wrapper resolution on skills-install repos (issue #82) -----------------


def test_wrapper_resolves_bundled_substrate_without_env(tmp_path):
    """A skills-install repo (no framework clone, no AUTONOMOUS_FLEET_HOME)
    must resolve stop_verify.py from the core skill's bundled substrate via
    the hook's cwd."""
    import shutil
    import subprocess

    repo = tmp_path / "worker-repo"
    substrate_dst = repo / ".agents" / "skills" / "autonomous-fleet-core" / "assets" / "substrate"
    shutil.copytree(
        ROOT / "skills" / "autonomous-fleet-core" / "assets" / "substrate", substrate_dst
    )
    hooks_dst = repo / ".agents" / "skills" / "autonomous-fleet-adapter-claude-code" / "assets" / "hooks"
    hooks_dst.mkdir(parents=True)
    shutil.copy2(
        ROOT / "skills" / "autonomous-fleet-adapter-claude-code" / "assets" / "hooks" / "stop-verify.sh",
        hooks_dst / "stop-verify.sh",
    )

    env = {k: v for k, v in os.environ.items() if k not in ("AUTONOMOUS_FLEET_HOME", "FLEET_SUBSTRATE")}
    r = subprocess.run(
        ["bash", str(hooks_dst / "stop-verify.sh")],
        input='{"cwd": "."}',
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "not found" not in r.stderr, r.stderr
    # No evidence in a fresh repo -> the bundled CLI must BLOCK.
    assert '"decision": "block"' in r.stdout, r.stdout + r.stderr


def test_wrapper_prefers_fleet_substrate_env(tmp_path):
    import shutil
    import subprocess

    substrate = tmp_path / "custom-substrate"
    shutil.copytree(ROOT / "skills" / "autonomous-fleet-core" / "assets" / "substrate", substrate)
    repo = tmp_path / "repo"
    repo.mkdir()

    env = {k: v for k, v in os.environ.items() if k != "AUTONOMOUS_FLEET_HOME"}
    env["FLEET_SUBSTRATE"] = str(substrate)
    env["STOP_VERIFY_EXPLAIN"] = "1"
    r = subprocess.run(
        ["bash", str(ROOT / "skills" / "autonomous-fleet-adapter-claude-code" / "assets" / "hooks" / "stop-verify.sh")],
        input='{"cwd": "."}',
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "not found" not in r.stderr, r.stderr
    assert '"decision": "block"' in r.stdout, r.stdout + r.stderr


def test_wrapper_fail_open_when_cli_missing_everywhere(tmp_path):
    import shutil
    import subprocess

    repo = tmp_path / "bare-repo"
    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy2(
        ROOT / "skills" / "autonomous-fleet-adapter-claude-code" / "assets" / "hooks" / "stop-verify.sh",
        hooks / "stop-verify.sh",
    )
    env = {k: v for k, v in os.environ.items() if k not in ("AUTONOMOUS_FLEET_HOME", "FLEET_SUBSTRATE")}
    r = subprocess.run(
        ["bash", str(hooks / "stop-verify.sh")],
        input="{}",
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0
    assert "allowing session end" in r.stderr
    assert r.stdout.strip() == ""
