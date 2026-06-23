"""Tests for verify_findings lib + CLI.

Two surfaces:
  - lib.verify_findings.validate_findings_doc — structural validation
  - lib.verify_findings.verify_findings_doc — source-grep verification
  - scripts/verify_findings.py main() — CLI exit codes

Discipline test the verifier exists to enforce: a reviewer that fabricates a
quoted_line not present in the cited file MUST be downgraded. The tests cover
the happy path, the hallucination path, the file-missing path, the
whitespace-tolerance path, and several schema violations.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.verify_findings import (  # noqa: E402
    validate_findings_doc,
    verify_finding_against_source,
    verify_findings_doc,
)


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "verify_findings_cli", ROOT / "scripts" / "verify_findings.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _minimal_finding(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "F-001",
        "severity": "high",
        "category": "bug",
        "claim": "Null guard at point of use; root cause is upstream constructor.",
        "evidence": {
            "file_path": "src/main.py",
            "line_number": 12,
            "quoted_line": "    return result",
        },
        "fix_alternatives": [
            {"label": "A", "description": "Fix at source", "effort": "moderate", "recommended": True},
            {"label": "B", "description": "Guard at caller", "effort": "minimal"},
        ],
        "confidence": 85,
        "fix_strategy": "ask",
    }
    base.update(overrides)
    return base


def _minimal_doc(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "1.0",
        "mission": "adversarial-review-and-fix",
        "review_id": "main-round-1-claude",
        "findings": [_minimal_finding()],
        "verdict": {
            "decision": "request_changes",
            "reasoning": "One blocking finding; address before merge.",
        },
    }
    base.update(overrides)
    return base


# ───────────────────────────────────────────────────────────────────────
# validate_findings_doc — structural
# ───────────────────────────────────────────────────────────────────────


def test_validate_accepts_minimal_well_formed_doc():
    assert validate_findings_doc(_minimal_doc()) == []


def test_validate_rejects_non_object_top_level():
    errs = validate_findings_doc([])  # type: ignore[arg-type]
    assert any("top-level must be an object" in e for e in errs)


def test_validate_reports_missing_required_top_fields():
    doc = {"mission": "x"}
    errs = validate_findings_doc(doc)
    # Should report each missing required field independently
    expected_missing = {"schema_version", "review_id", "findings", "verdict"}
    for field in expected_missing:
        assert any(f"missing required field '{field}'" in e for e in errs), field


def test_validate_pins_schema_version_to_1_0():
    doc = _minimal_doc(schema_version="2.0")
    errs = validate_findings_doc(doc)
    assert any("schema_version must be '1.0'" in e for e in errs)


def test_validate_rejects_bad_review_id_pattern():
    doc = _minimal_doc(review_id="has spaces and !!")
    errs = validate_findings_doc(doc)
    assert any("review_id must match" in e for e in errs)


def test_validate_rejects_duplicate_finding_ids():
    doc = _minimal_doc(findings=[_minimal_finding(id="F-001"), _minimal_finding(id="F-001")])
    errs = validate_findings_doc(doc)
    assert any("duplicate id 'F-001'" in e for e in errs)


def test_validate_rejects_bad_severity_and_category():
    bad = _minimal_finding(severity="nuclear", category="dance")
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("severity must be one of" in e for e in errs)
    assert any("category must be one of" in e for e in errs)


def test_validate_requires_evidence_quoted_line_and_file_path():
    bad = _minimal_finding(evidence={"file_path": "src/main.py"})
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("evidence missing 'quoted_line'" in e for e in errs)


def test_validate_rejects_empty_quoted_line():
    bad = _minimal_finding(
        evidence={"file_path": "src/main.py", "quoted_line": "   "},
    )
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("evidence.quoted_line must be a non-empty string" in e for e in errs)


def test_validate_rejects_line_number_zero_or_negative():
    bad = _minimal_finding(
        evidence={"file_path": "src/main.py", "quoted_line": "x", "line_number": 0}
    )
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("evidence.line_number must be a positive int" in e for e in errs)


def test_validate_requires_at_least_one_fix_alternative():
    bad = _minimal_finding(fix_alternatives=[])
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("fix_alternatives must be a non-empty list" in e for e in errs)


def test_validate_rejects_more_than_four_fix_alternatives():
    too_many = [
        {"label": ch, "description": "x", "effort": "minimal"} for ch in "ABCDE"
    ]
    bad = _minimal_finding(fix_alternatives=too_many)
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("must have at most 4 entries" in e for e in errs)


def test_validate_rejects_duplicate_fix_alternative_labels():
    bad = _minimal_finding(
        fix_alternatives=[
            {"label": "A", "description": "x", "effort": "minimal"},
            {"label": "A", "description": "y", "effort": "moderate"},
        ]
    )
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("label duplicate 'A'" in e for e in errs)


def test_validate_rejects_multi_recommended_fix_alternatives():
    bad = _minimal_finding(
        fix_alternatives=[
            {"label": "A", "description": "x", "effort": "minimal", "recommended": True},
            {"label": "B", "description": "y", "effort": "moderate", "recommended": True},
        ]
    )
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any(
        "recommended=true; schema permits at most one" in e for e in errs
    )


@pytest.mark.parametrize("conf", [-1, 101, "high", 50.5, True])
def test_validate_rejects_bad_confidence(conf):
    bad = _minimal_finding(confidence=conf)
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("confidence must be int 0-100" in e for e in errs)


def test_validate_rejects_unknown_fix_strategy():
    bad = _minimal_finding(fix_strategy="maybe")
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("fix_strategy must be one of" in e for e in errs)


def test_validate_requires_cascade_impact_for_root_cause_depth():
    bad = _minimal_finding(category="root_cause_depth")
    # cascade_impact missing
    errs = validate_findings_doc(_minimal_doc(findings=[bad]))
    assert any("category=root_cause_depth requires non-empty cascade_impact" in e for e in errs)


def test_validate_accepts_root_cause_depth_with_cascade_impact():
    good = _minimal_finding(
        category="root_cause_depth",
        cascade_impact="Affects all 3 callers of foo() via the same null path.",
    )
    assert validate_findings_doc(_minimal_doc(findings=[good])) == []


def test_validate_rejects_bad_verdict_decision_and_empty_reasoning():
    doc = _minimal_doc(verdict={"decision": "maybe", "reasoning": ""})
    errs = validate_findings_doc(doc)
    assert any("verdict.decision must be one of" in e for e in errs)
    assert any("verdict.reasoning must be a non-empty string" in e for e in errs)


# ───────────────────────────────────────────────────────────────────────
# verify_finding_against_source — source grep
# ───────────────────────────────────────────────────────────────────────


def test_verify_marks_finding_verified_when_quote_matches_verbatim(tmp_path: Path):
    src = tmp_path / "src" / "main.py"
    src.parent.mkdir(parents=True)
    src.write_text("def f():\n    return result\n")
    f = _minimal_finding(
        evidence={"file_path": "src/main.py", "line_number": 2, "quoted_line": "    return result"}
    )
    verify_finding_against_source(f, repo_root=tmp_path)
    assert f["verified"] is True
    assert "verify_reason" not in f


def test_verify_marks_finding_verified_with_whitespace_tolerance(tmp_path: Path):
    """Lineage: GodModeSkill ql_norm/source_norm collapse runs of whitespace. We
    must match a quote that uses single spaces against a source line that uses
    tabs/multi-space — otherwise tab-vs-space accidents look like
    hallucinations and erode reviewer trust."""
    src = tmp_path / "code.py"
    src.write_text("\tif\t\tcondition:\n\t\treturn  True\n")
    f = _minimal_finding(
        evidence={"file_path": "code.py", "quoted_line": "return True"}
    )
    verify_finding_against_source(f, repo_root=tmp_path)
    assert f["verified"] is True


def test_verify_downgrades_hallucinated_quote(tmp_path: Path):
    """The actual reason this verifier exists: reviewer cites a line that
    isn't in the file. The mutation MUST flip verified to false with a
    machine-readable reason so fleet-outcome.metrics.unverified_findings can
    surface it."""
    src = tmp_path / "src" / "main.py"
    src.parent.mkdir(parents=True)
    src.write_text("def f():\n    return result\n")
    f = _minimal_finding(
        evidence={"file_path": "src/main.py", "quoted_line": "return result.unwrap_silently_panic()"}
    )
    verify_finding_against_source(f, repo_root=tmp_path)
    assert f["verified"] is False
    assert f["verify_reason"] == "quoted_line not found in cited file"


def test_verify_downgrades_when_file_missing(tmp_path: Path):
    f = _minimal_finding(
        evidence={"file_path": "src/never-existed.py", "quoted_line": "x = 1"}
    )
    verify_finding_against_source(f, repo_root=tmp_path)
    assert f["verified"] is False
    assert "file not found" in f["verify_reason"]


def test_verify_downgrades_when_path_is_directory(tmp_path: Path):
    d = tmp_path / "subdir"
    d.mkdir()
    f = _minimal_finding(evidence={"file_path": "subdir", "quoted_line": "x"})
    verify_finding_against_source(f, repo_root=tmp_path)
    assert f["verified"] is False
    assert "not a regular file" in f["verify_reason"]


def test_verify_downgrades_when_evidence_fields_empty(tmp_path: Path):
    f = _minimal_finding(evidence={"file_path": "", "quoted_line": ""})
    verify_finding_against_source(f, repo_root=tmp_path)
    assert f["verified"] is False
    assert "evidence.file_path or quoted_line missing/empty" in f["verify_reason"]


def test_verify_clears_stale_verify_reason_on_pass(tmp_path: Path):
    """If a prior verify pass marked the finding unverified and the reviewer
    fixed the quote, a re-verify with a now-matching quote MUST drop the
    stale verify_reason — otherwise the audit trail lies."""
    src = tmp_path / "code.py"
    src.write_text("return ok\n")
    f = _minimal_finding(
        evidence={"file_path": "code.py", "quoted_line": "return ok"},
        verified=False,
        verify_reason="quoted_line not found in cited file (from earlier round)",
    )
    verify_finding_against_source(f, repo_root=tmp_path)
    assert f["verified"] is True
    assert "verify_reason" not in f


def test_verify_rejects_absolute_path_outside_repo(tmp_path: Path):
    """A finding is reviewer-produced (suspect) data. An absolute path that
    escapes the repo root must be REJECTED — the verifier is not a
    read-anything primitive."""
    src = tmp_path / "absolute.py"
    src.write_text("CONST = 42\n")
    f = _minimal_finding(
        evidence={"file_path": str(src), "quoted_line": "CONST = 42"}
    )
    other = tmp_path / "other"
    other.mkdir()
    verify_finding_against_source(f, repo_root=other)
    assert f["verified"] is False
    assert "escapes repo root" in f["verify_reason"]


def test_verify_rejects_path_traversal(tmp_path: Path):
    """A ../ traversal that escapes the repo root is rejected."""
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    f = _minimal_finding(
        evidence={"file_path": "../secret.txt", "quoted_line": "TOPSECRET"}
    )
    verify_finding_against_source(f, repo_root=repo)
    assert f["verified"] is False
    assert "escapes repo root" in f["verify_reason"]


def test_verify_rejects_oversized_file(tmp_path: Path):
    """A cited file larger than the read cap is treated as unverified rather
    than OOM-ing the verifier."""
    from lib.verify_findings import MAX_SOURCE_BYTES

    big = tmp_path / "big.py"
    big.write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
    f = _minimal_finding(
        evidence={"file_path": "big.py", "quoted_line": "x"}
    )
    verify_finding_against_source(f, repo_root=tmp_path)
    assert f["verified"] is False
    assert "read cap" in f["verify_reason"]


def test_verify_doc_counts_reconcile_with_non_dict_entries(tmp_path: Path):
    """total = verified + unverified + skipped_non_dict, even when the findings
    list contains non-dict junk."""
    src = tmp_path / "a.py"
    src.write_text("HELLO\n")
    good = _minimal_finding(evidence={"file_path": "a.py", "quoted_line": "HELLO"})
    doc = {"findings": ["junk", good]}
    summary = verify_findings_doc(doc, repo_root=tmp_path)
    assert summary["total_findings"] == 2
    assert summary["skipped_non_dict"] == 1
    assert (
        summary["verified_findings"]
        + summary["unverified_findings"]
        + summary["skipped_non_dict"]
        == summary["total_findings"]
    )


# ───────────────────────────────────────────────────────────────────────
# verify_findings_doc — aggregate summary
# ───────────────────────────────────────────────────────────────────────


def test_verify_doc_summary_counts_split_correctly(tmp_path: Path):
    """Build a doc with 4 findings: 2 verified+ask, 1 verified+auto+conf90, 1
    hallucinated. Confirm the summary buckets are exactly what fleet-outcome
    will surface."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("alpha line\n")
    (tmp_path / "src" / "b.py").write_text("beta line\n")
    (tmp_path / "src" / "c.py").write_text("gamma line\n")
    # d.py contains the wrong content, so the cited quote will fail to match
    (tmp_path / "src" / "d.py").write_text("something different\n")

    doc = _minimal_doc(
        findings=[
            _minimal_finding(
                id="F-001",
                fix_strategy="ask",
                confidence=70,
                evidence={"file_path": "src/a.py", "quoted_line": "alpha line"},
            ),
            _minimal_finding(
                id="F-002",
                fix_strategy="ask",
                confidence=95,
                evidence={"file_path": "src/b.py", "quoted_line": "beta line"},
            ),
            _minimal_finding(
                id="F-003",
                fix_strategy="auto",
                confidence=90,
                evidence={"file_path": "src/c.py", "quoted_line": "gamma line"},
            ),
            _minimal_finding(
                id="F-004",
                fix_strategy="auto",
                confidence=95,
                evidence={"file_path": "src/d.py", "quoted_line": "this is fabricated"},
            ),
        ]
    )

    summary = verify_findings_doc(doc, repo_root=tmp_path)
    assert summary["total_findings"] == 4
    assert summary["verified_findings"] == 3
    assert summary["unverified_findings"] == 1
    assert summary["unverified_ids"] == ["F-004"]
    # F-003 only: F-001/F-002 are ask, F-004 is unverified (so disqualified
    # even though it claims auto with conf>=80). This is the discipline the
    # schema mechanises — auto-apply requires verified=true.
    assert summary["auto_applicable_findings"] == 1
    assert summary["human_gated_findings"] == 2


def test_verify_doc_unverified_finding_never_counts_as_auto(tmp_path: Path):
    """Regression guard: an unverified finding with fix_strategy=auto and
    confidence=99 still MUST NOT be auto-applicable. This is the core safety
    property of the schema."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("real line\n")
    doc = _minimal_doc(
        findings=[
            _minimal_finding(
                id="F-001",
                fix_strategy="auto",
                confidence=99,
                evidence={"file_path": "src/a.py", "quoted_line": "completely made up"},
            )
        ]
    )
    summary = verify_findings_doc(doc, repo_root=tmp_path)
    assert summary["verified_findings"] == 0
    assert summary["unverified_findings"] == 1
    assert summary["auto_applicable_findings"] == 0


# ───────────────────────────────────────────────────────────────────────
# CLI integration
# ───────────────────────────────────────────────────────────────────────


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    sys.argv = ["verify_findings.py", *argv]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main()
    finally:
        sys.argv = old_argv
    return rc, out.getvalue(), err.getvalue()


def test_cli_exit_3_when_doc_missing(tmp_path: Path):
    rc, _out, err = _run_cli([str(tmp_path / "nope.json"), "--repo", str(tmp_path)])
    assert rc == 3
    assert "not a file" in err


def test_cli_exit_3_when_repo_missing(tmp_path: Path):
    doc_path = tmp_path / "f.json"
    doc_path.write_text(json.dumps(_minimal_doc()))
    rc, _out, err = _run_cli([str(doc_path), "--repo", str(tmp_path / "nope")])
    assert rc == 3
    assert "--repo not a directory" in err


def test_cli_exit_2_on_invalid_json(tmp_path: Path):
    doc_path = tmp_path / "bad.json"
    doc_path.write_text("{ this is not json")
    rc, _out, err = _run_cli([str(doc_path), "--repo", str(tmp_path)])
    assert rc == 2
    assert "invalid JSON" in err


def test_cli_exit_2_on_schema_violation(tmp_path: Path):
    bad = _minimal_doc(findings=[_minimal_finding(severity="nuclear")])
    doc_path = tmp_path / "bad.json"
    doc_path.write_text(json.dumps(bad))
    rc, _out, err = _run_cli([str(doc_path), "--repo", str(tmp_path)])
    assert rc == 2
    assert "SCHEMA" in err
    assert "severity must be one of" in err


def test_cli_exit_1_on_unverified_finding(tmp_path: Path):
    """The whole point: when the reviewer hallucinates, exit non-zero so the
    fleet-program edge that gates on a passing verify halts the loop."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("real line\n")
    doc = _minimal_doc(
        findings=[
            _minimal_finding(
                evidence={"file_path": "src/a.py", "quoted_line": "fabricated"}
            )
        ]
    )
    doc_path = tmp_path / "f.json"
    doc_path.write_text(json.dumps(doc))
    rc, out, err = _run_cli([str(doc_path), "--repo", str(tmp_path)])
    assert rc == 1
    assert "unverified: 1" in out
    assert "DOWNGRADE" in err


def test_cli_exit_0_on_clean_verification(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("real line\n")
    doc = _minimal_doc(
        findings=[
            _minimal_finding(
                evidence={"file_path": "src/a.py", "quoted_line": "real line"}
            )
        ]
    )
    doc_path = tmp_path / "f.json"
    doc_path.write_text(json.dumps(doc))
    rc, out, _err = _run_cli([str(doc_path), "--repo", str(tmp_path)])
    assert rc == 0
    assert "1/1 findings verified" in out
    assert "unverified: 0" in out


def test_cli_write_round_trips_verified_field(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("real line\n")
    doc = _minimal_doc(
        findings=[
            _minimal_finding(
                evidence={"file_path": "src/a.py", "quoted_line": "real line"}
            )
        ]
    )
    doc_path = tmp_path / "f.json"
    doc_path.write_text(json.dumps(doc))
    rc, _out, _err = _run_cli([str(doc_path), "--repo", str(tmp_path), "--write"])
    assert rc == 0
    rewritten = json.loads(doc_path.read_text())
    assert rewritten["findings"][0]["verified"] is True


def test_cli_summary_out_emits_json_summary(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("real line\n")
    doc = _minimal_doc(
        findings=[
            _minimal_finding(
                evidence={"file_path": "src/a.py", "quoted_line": "real line"}
            )
        ]
    )
    doc_path = tmp_path / "f.json"
    doc_path.write_text(json.dumps(doc))
    summary_path = tmp_path / "summary.json"
    rc, _out, _err = _run_cli(
        [str(doc_path), "--repo", str(tmp_path), "--summary-out", str(summary_path)]
    )
    assert rc == 0
    summary = json.loads(summary_path.read_text())
    assert summary["total_findings"] == 1
    assert summary["verified_findings"] == 1
    assert summary["unverified_findings"] == 0
    assert summary["auto_applicable_findings"] == 0  # default is ask
    assert summary["human_gated_findings"] == 1
