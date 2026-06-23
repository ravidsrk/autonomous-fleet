"""Tests for scripts/lib/analyze_seat.py and scripts/analyze_seat.py."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.analyze_seat import (  # noqa: E402
    COST_EPSILON,
    _decision_count,
    _iter_trace_events,
    _parse_iso,
    _read_json,
    _read_yaml_outcome,
    aggregate,
    analyze_run,
    discover_runs,
)


# --- Helper / fixture builders ------------------------------------------


def _mini_archive(
    root: Path,
    *,
    findings: list[dict] | None = None,
    cost: float = 0.5,
    blind_fix_files: dict[str, str] | None = None,
    fix_attestations: list[str] | None = None,
    trace_events: list[dict] | None = None,
    decisions: list[dict] | None = None,
) -> Path:
    """Build a tiny test archive under root and return its path."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps({"schema_version": "1.0"}))

    if findings is not None:
        (root / "p0-review-findings.json").write_text(
            json.dumps({"schema_version": "1.0", "findings": findings})
        )

    if fix_attestations is not None:
        for fid in fix_attestations:
            (root / f"p1-fix-attestation-{fid}.json").write_text(
                json.dumps({"finding_id": fid, "blind_fix_attested": True})
            )

    (root / "fleet-outcome.yaml").write_text(
        f"status: done\ncost_estimate: {cost}\nrun_id: 20260623T000000Z-test-000001\n"
    )

    if trace_events is not None:
        (root / "trace.jsonl").write_text(
            "\n".join(json.dumps(e) for e in trace_events) + "\n"
        )

    if decisions is not None:
        (root / "stop-verify-decisions.log").write_text(
            "\n".join(json.dumps(d) for d in decisions) + "\n"
        )

    return root


# --- analyze_run ---------------------------------------------------------


def test_analyze_run_happy_path(tmp_path: Path) -> None:
    arc = _mini_archive(
        tmp_path / "arc1",
        findings=[
            {
                "id": "F-001",
                "verified": True,
                "blind_fix_chain": {
                    "fixer_draft_sha": "abc1234",
                    "integration_sha": "def5678",
                },
            },
            {"id": "F-002", "verified": False},
        ],
        cost=2.0,
        fix_attestations=["F-001"],
        trace_events=[
            {"ts": "2026-06-23T00:00:00Z", "primitive": "SPAWN_WORKER"},
            {"ts": "2026-06-23T00:01:00Z", "primitive": "FREEZE"},
            {"ts": "2026-06-23T00:05:00Z", "primitive": "COMMIT"},
        ],
        decisions=[
            {"decision": "block", "reason": "x"},
            {"decision": "allow", "reason": "y"},
        ],
    )

    result = analyze_run(arc)
    assert result["findings_emitted"] == 2
    assert result["findings_verified"] == 1
    assert result["findings_closed"] == 1
    assert result["findings_withdrawn_post_blind_fix"] == 1
    assert result["cost_estimate"] == 2.0
    assert result["value_per_dollar"] == 0.5  # 1 / 2.0
    assert result["wall_clock_to_freeze_s"] == 60
    assert result["wall_clock_to_all_closed_s"] == 300
    assert result["stop_verify_activations"] == 1
    assert result["parsable"] is True


def test_analyze_run_legacy_attestation_path(tmp_path: Path) -> None:
    """Legacy p1-fix-attestation.json (single shared file) counts too."""
    arc = _mini_archive(
        tmp_path / "legacy",
        findings=[{"id": "F-1", "verified": True}],
        cost=1.0,
    )
    (arc / "p1-fix-attestation.json").write_text(json.dumps({"finding_id": "F-1"}))
    result = analyze_run(arc)
    assert result["findings_closed"] == 1


def test_analyze_run_cost_zero_uses_epsilon(tmp_path: Path) -> None:
    arc = _mini_archive(
        tmp_path / "free",
        findings=[{"id": "F-1", "verified": True}],
        cost=0,
        fix_attestations=["F-1"],
    )
    result = analyze_run(arc)
    # vpd = 1 / max(0, epsilon) = 1 / 0.01 = 100
    assert result["value_per_dollar"] == 1 / COST_EPSILON


def test_analyze_run_missing_findings_doc(tmp_path: Path) -> None:
    arc = tmp_path / "minimal"
    arc.mkdir()
    (arc / "manifest.json").write_text("{}")
    (arc / "fleet-outcome.yaml").write_text("status: done\n")
    result = analyze_run(arc)
    assert result["findings_emitted"] == 0
    assert result["parsable"] is True  # outcome still parsable


def test_analyze_run_completely_broken(tmp_path: Path) -> None:
    """Empty archive directory yields parsable=False."""
    arc = tmp_path / "broken"
    arc.mkdir()
    result = analyze_run(arc)
    assert result["parsable"] is False


def test_analyze_run_non_dict_finding_skipped(tmp_path: Path) -> None:
    arc = tmp_path / "weird"
    arc.mkdir()
    (arc / "p0-review-findings.json").write_text(
        json.dumps({"findings": [{"id": "F-1"}, "not-a-dict", 42, None]})
    )
    (arc / "fleet-outcome.yaml").write_text("cost_estimate: 1.0\n")
    result = analyze_run(arc)
    assert result["findings_emitted"] == 1


def test_analyze_run_chain_without_disagreement(tmp_path: Path) -> None:
    """Chain present but fixer_draft == integration → not withdrawn."""
    arc = _mini_archive(
        tmp_path / "agree",
        findings=[
            {
                "id": "F-1",
                "verified": True,
                "blind_fix_chain": {
                    "fixer_draft_sha": "abc",
                    "integration_sha": "abc",
                },
            }
        ],
        cost=1.0,
    )
    result = analyze_run(arc)
    assert result["findings_withdrawn_post_blind_fix"] == 0


def test_analyze_run_verified_without_id(tmp_path: Path) -> None:
    arc = _mini_archive(
        tmp_path / "noid",
        findings=[{"verified": True}],  # missing id → no attestation lookup
        cost=1.0,
    )
    result = analyze_run(arc)
    assert result["findings_verified"] == 1
    assert result["findings_closed"] == 0  # no id → can't find attestation


def test_analyze_run_outcome_cost_invalid(tmp_path: Path) -> None:
    arc = tmp_path / "badcost"
    arc.mkdir()
    (arc / "p0-review-findings.json").write_text(json.dumps({"findings": []}))
    (arc / "fleet-outcome.yaml").write_text("cost_estimate: not-a-number\n")
    result = analyze_run(arc)
    assert result["cost_estimate"] == 0.0


def test_analyze_run_trace_with_bad_ts(tmp_path: Path) -> None:
    arc = _mini_archive(
        tmp_path / "badts",
        findings=[],
        cost=0.1,
        trace_events=[
            {"ts": "not-an-iso", "primitive": "FREEZE"},
            {"primitive": "COMMIT"},  # no ts
        ],
    )
    result = analyze_run(arc)
    assert result["wall_clock_to_freeze_s"] is None
    assert result["wall_clock_to_all_closed_s"] is None


# --- aggregate -----------------------------------------------------------


def test_aggregate_empty() -> None:
    out = aggregate([])
    assert out["runs"] == 0
    assert out["value_per_dollar_avg"] == 0.0


def test_aggregate_multiple_runs(tmp_path: Path) -> None:
    a = _mini_archive(
        tmp_path / "a",
        findings=[{"id": "X", "verified": True}],
        cost=1.0,
        fix_attestations=["X"],
        trace_events=[
            {"ts": "2026-06-23T00:00:00Z", "primitive": "SPAWN_WORKER"},
            {"ts": "2026-06-23T00:00:30Z", "primitive": "FREEZE"},
            {"ts": "2026-06-23T00:01:30Z", "primitive": "COMMIT"},
        ],
        decisions=[{"decision": "block"}],
    )
    b = _mini_archive(
        tmp_path / "b",
        findings=[{"id": "Y", "verified": False}],
        cost=0.5,
    )
    result = aggregate([analyze_run(a), analyze_run(b)])
    assert result["runs"] == 2
    assert result["findings_emitted_total"] == 2
    assert result["findings_verified_total"] == 1
    assert result["findings_closed_total"] == 1
    assert result["cost_estimate_total"] == 1.5
    assert result["stop_verify_activations_total"] == 1
    assert result["wall_clock_to_freeze_avg_s"] == 30


def test_aggregate_no_wallclock_returns_none(tmp_path: Path) -> None:
    a = _mini_archive(tmp_path / "a", findings=[], cost=0.1)
    result = aggregate([analyze_run(a)])
    assert result["wall_clock_to_freeze_avg_s"] is None


# --- discover_runs -------------------------------------------------------


def test_discover_runs(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    a = runs / "arc-a"
    a.mkdir()
    (a / "manifest.json").write_text("{}")
    b = runs / "arc-b"
    b.mkdir()
    # No manifest → not an archive.
    c = runs / "ignored.txt"
    c.write_text("not a dir")

    out = discover_runs(runs)
    assert len(out) == 1
    assert out[0] == a


def test_discover_runs_missing_root(tmp_path: Path) -> None:
    assert discover_runs(tmp_path / "nope") == []


# --- Helper purity --------------------------------------------------------


def test_read_json_missing(tmp_path: Path) -> None:
    assert _read_json(tmp_path / "nope.json") is None


def test_read_json_invalid(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert _read_json(p) is None


def test_read_json_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "fine.json"
    p.write_text("{}")
    real = Path.read_text

    def boom(self: Path, *a, **kw):  # noqa: ANN001
        if self == p:
            raise OSError("simulated EIO")
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom)
    assert _read_json(p) is None


def test_read_yaml_outcome_missing(tmp_path: Path) -> None:
    assert _read_yaml_outcome(tmp_path / "nope.yaml") is None


def test_read_yaml_outcome_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "x.yaml"
    p.write_text("a: b\n")
    real = Path.read_text

    def boom(self: Path, *a, **kw):  # noqa: ANN001
        if self == p:
            raise OSError("eio")
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom)
    assert _read_yaml_outcome(p) is None


def test_read_yaml_outcome_typed_values(tmp_path: Path) -> None:
    p = tmp_path / "out.yaml"
    p.write_text(
        "archive_enabled: true\n"
        "disabled_flag: false\n"
        "count: 7\n"
        "cost: 1.25\n"
        "label: 'hello'  # inline comment\n"
        "weird: stillstring\n"
    )
    out = _read_yaml_outcome(p)
    assert out["archive_enabled"] is True
    assert out["disabled_flag"] is False
    assert out["count"] == 7
    assert out["cost"] == 1.25
    assert out["label"] == "hello"
    assert out["weird"] == "stillstring"


def test_iter_trace_events_missing(tmp_path: Path) -> None:
    assert list(_iter_trace_events(tmp_path / "nope.jsonl")) == []


def test_iter_trace_events_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "t.jsonl"
    p.write_text('{"ts":"x"}\n')
    real = Path.read_text

    def boom(self: Path, *a, **kw):  # noqa: ANN001
        if self == p:
            raise OSError("eio")
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom)
    assert list(_iter_trace_events(p)) == []


def test_iter_trace_events_tolerates_garbage(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    p.write_text('{"ok":1}\n\nnot json\n"not a dict"\n')
    events = list(_iter_trace_events(p))
    assert events == [{"ok": 1}]


def test_parse_iso_variants() -> None:
    assert _parse_iso("2026-06-23T00:00:00Z") is not None
    # ISO with offset.
    assert _parse_iso("2026-06-23T00:00:00+00:00") is not None
    assert _parse_iso("not-iso") is None
    assert _parse_iso(None) is None


def test_decision_count_missing_log(tmp_path: Path) -> None:
    assert _decision_count(tmp_path / "nope.log", "block") == 0


def test_decision_count_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "x.log"
    p.write_text('{"decision":"block"}\n')
    real = Path.read_text

    def boom(self: Path, *a, **kw):  # noqa: ANN001
        if self == p:
            raise OSError("eio")
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom)
    assert _decision_count(p, "block") == 0


def test_decision_count_tolerates_garbage(tmp_path: Path) -> None:
    p = tmp_path / "x.log"
    p.write_text('{"decision":"block"}\nnot-json\n"string-not-dict"\n{"decision":"allow"}\n')
    assert _decision_count(p, "block") == 1
    assert _decision_count(p, "allow") == 1


# --- CLI -----------------------------------------------------------------


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "analyze_seat_cli",
        REPO_ROOT / "scripts" / "analyze_seat.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*argv: str) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    sys.argv = ["analyze_seat.py", *argv]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main()
    finally:
        sys.argv = old_argv
    return rc, out.getvalue(), err.getvalue()


def test_cli_bad_root() -> None:
    rc, _, err = _run_cli("--runs-root", "/this/path/does/not/exist", "per-run")
    assert rc == 2
    assert "not a directory" in err


def test_cli_no_archives(tmp_path: Path) -> None:
    rc, _, err = _run_cli("--runs-root", str(tmp_path), "per-run")
    assert rc == 1
    assert "no archives" in err


def test_cli_per_run_table(tmp_path: Path) -> None:
    a = _mini_archive(
        tmp_path / "a",
        findings=[{"id": "F-1", "verified": True}],
        cost=1.0,
        fix_attestations=["F-1"],
        trace_events=[
            {"ts": "2026-06-23T00:00:00Z", "primitive": "SPAWN_WORKER"},
            {"ts": "2026-06-23T00:00:30Z", "primitive": "FREEZE"},
            {"ts": "2026-06-23T00:01:00Z", "primitive": "COMMIT"},
        ],
    )
    rc, out, _ = _run_cli("--runs-root", str(tmp_path), "per-run")
    assert rc == 0
    assert "F-" not in out  # Table is column-aligned, no per-finding rows
    assert "run" in out  # header


def test_cli_per_run_json(tmp_path: Path) -> None:
    _mini_archive(tmp_path / "a", findings=[], cost=0.1)
    rc, out, _ = _run_cli("--runs-root", str(tmp_path), "--json", "per-run")
    assert rc == 0
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) == 1


def test_cli_aggregate(tmp_path: Path) -> None:
    _mini_archive(tmp_path / "a", findings=[], cost=0.1)
    rc, out, _ = _run_cli("--runs-root", str(tmp_path), "aggregate")
    assert rc == 0
    assert "runs: 1" in out


def test_cli_aggregate_json(tmp_path: Path) -> None:
    _mini_archive(
        tmp_path / "a",
        findings=[{"id": "F-1", "verified": True}],
        cost=0.5,
        fix_attestations=["F-1"],
        trace_events=[
            {"ts": "2026-06-23T00:00:00Z", "primitive": "SPAWN_WORKER"},
            {"ts": "2026-06-23T00:00:30Z", "primitive": "FREEZE"},
            {"ts": "2026-06-23T00:01:00Z", "primitive": "COMMIT"},
        ],
    )
    rc, out, _ = _run_cli("--runs-root", str(tmp_path), "--json", "aggregate")
    assert rc == 0
    data = json.loads(out)
    assert data["runs"] == 1


def test_cli_aggregate_table_with_wallclock(tmp_path: Path) -> None:
    """Exercises the human-readable aggregate output paths including
    wall_clock_to_freeze_avg_s formatting."""
    _mini_archive(
        tmp_path / "a",
        findings=[{"id": "F-1", "verified": True}],
        cost=0.5,
        fix_attestations=["F-1"],
        trace_events=[
            {"ts": "2026-06-23T00:00:00Z", "primitive": "SPAWN_WORKER"},
            {"ts": "2026-06-23T00:01:00Z", "primitive": "FREEZE"},
            {"ts": "2026-06-23T00:02:00Z", "primitive": "COMMIT"},
        ],
    )
    rc, out, _ = _run_cli("--runs-root", str(tmp_path), "aggregate")
    assert rc == 0
    assert "wall_clock_to_freeze_avg_s" in out
    assert "wall_clock_to_all_closed_avg_s" in out


def test_cli_no_parsable_archives(tmp_path: Path) -> None:
    """Archives with manifest.json but nothing else are not parsable."""
    arc = tmp_path / "shell"
    arc.mkdir()
    (arc / "manifest.json").write_text("{}")
    rc, _, err = _run_cli("--runs-root", str(tmp_path), "per-run")
    assert rc == 1
    assert "no parsable archives" in err


def test_read_yaml_outcome_skips_unmatched_lines(tmp_path: Path) -> None:
    """Lines that don't match key: value are skipped silently."""
    p = tmp_path / "x.yaml"
    p.write_text("# comment line\n\nthis-is-not-a-key-value\nkey: value\n---\n")
    out = _read_yaml_outcome(p)
    assert out == {"key": "value"}


def test_decision_count_skips_invalid_json(tmp_path: Path) -> None:
    """JSONDecodeError on individual lines is skipped, count still works."""
    p = tmp_path / "y.log"
    p.write_text('{"decision":"block"}\nnot valid json\n{"decision":"block"}\n')
    assert _decision_count(p, "block") == 2


def test_decision_count_skips_empty_lines(tmp_path: Path) -> None:
    """Blank lines hit the `if not line: continue` branch."""
    p = tmp_path / "z.log"
    p.write_text('\n\n{"decision":"block"}\n\n')
    assert _decision_count(p, "block") == 1
