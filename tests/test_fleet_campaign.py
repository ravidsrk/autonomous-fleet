"""Tests for fleet-outcome parsing and campaign edge evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.fleet_outcome import (  # noqa: E402
    eval_edge,
    parse_readiness,
    pick_next_node,
    split_frontmatter,
    validate_outcome,
)


DOC_SYNC_OUTCOME = {
    "mission": "doc-sync",
    "status": "done",
    "repo": "/tmp/repo",
    "base_branch": "fleet/base",
    "prs_merged": 1,
    "metrics": {"drift_open": 0, "code_bug_findings": 0},
    "deferred_missions": [],
}


def test_research_gate_optional_and_typed():
    # absent -> fine (cross-cutting + optional)
    assert validate_outcome(DOC_SYNC_OUTCOME) == []
    # valid non-negative ints -> pass, and branchable via eval_edge top-level fallback
    ok = {**DOC_SYNC_OUTCOME, "unverified_assumptions": 0, "sources_logged": 7}
    assert validate_outcome(ok) == []
    assert eval_edge("unverified_assumptions == 0", ok) is True
    # negative / non-int -> rejected
    assert any(
        "unverified_assumptions" in e
        for e in validate_outcome({**DOC_SYNC_OUTCOME, "unverified_assumptions": -1})
    )
    assert any(
        "sources_logged" in e
        for e in validate_outcome({**DOC_SYNC_OUTCOME, "sources_logged": "lots"})
    )


def test_cost_estimate_optional_and_numeric():
    # absent -> fine; non-negative int or float -> pass and branchable
    assert validate_outcome(DOC_SYNC_OUTCOME) == []
    assert validate_outcome({**DOC_SYNC_OUTCOME, "cost_estimate": 0}) == []
    ok = {**DOC_SYNC_OUTCOME, "cost_estimate": 4.25}
    assert validate_outcome(ok) == []
    assert eval_edge("cost_estimate > 4", ok) is True
    # negative / bool / string -> rejected
    for bad in (-1, True, "cheap"):
        assert any(
            "cost_estimate" in e
            for e in validate_outcome({**DOC_SYNC_OUTCOME, "cost_estimate": bad})
        )


def test_eval_always():
    assert eval_edge("always", DOC_SYNC_OUTCOME) is True


def test_eval_code_bug_branch_skip():
    assert eval_edge("code_bug_findings > 0", DOC_SYNC_OUTCOME) is False
    assert eval_edge("code_bug_findings == 0", DOC_SYNC_OUTCOME) is True


def test_eval_deferred_contains():
    outcome = {
        **DOC_SYNC_OUTCOME,
        "deferred_missions": [{"id": "bug-batch", "reason": "x", "blocker": None}],
    }
    assert eval_edge("deferred_missions contains bug-batch", outcome) is True
    assert eval_edge("deferred_missions contains test-coverage", outcome) is False


def test_pick_next_docs_if_bugs_skips_bug_batch():
    campaign = {
        "edges": {
            "docs": [
                {"to": "bugs", "if": "code_bug_findings > 0"},
                {"to": "tests", "if": "always"},
            ],
            "bugs": [{"to": "tests", "if": "always"}],
            "tests": [],
        }
    }
    assert pick_next_node(campaign, "docs", DOC_SYNC_OUTCOME) == "tests"


def test_pick_next_docs_if_bugs_includes_bug_batch():
    outcome = {
        **DOC_SYNC_OUTCOME,
        "metrics": {"drift_open": 0, "code_bug_findings": 2},
    }
    campaign = {
        "edges": {
            "docs": [
                {"to": "bugs", "if": "code_bug_findings > 0"},
                {"to": "tests", "if": "always"},
            ],
        }
    }
    assert pick_next_node(campaign, "docs", outcome) == "bugs"


def test_validate_outcome_requires_metrics():
    errors = validate_outcome({"mission": "doc-sync", "status": "done"})
    assert any("metrics" in e for e in errors)


def test_eval_ordering_coerces_string_and_float_metrics():
    """EVAL-05: ordering ops coerce defensively instead of raising TypeError."""
    outcome = {"metrics": {"coverage": 79.5}}
    assert eval_edge("coverage > 79.5", outcome) is False
    assert eval_edge("coverage > 79", outcome) is True
    assert eval_edge("coverage > 79.4", outcome) is True

    str_metric = {"metrics": {"coverage": "80"}}
    assert eval_edge("coverage > 79", str_metric) is True

    float_vs_str = {"metrics": {"coverage": 80}}
    assert eval_edge("coverage > 79.5", float_vs_str) is True


def test_eval_ordering_invalid_types_raise_value_error():
    """EVAL-05: non-numeric operands surface a named ValueError."""
    with pytest.raises(ValueError, match="cannot compare metric values numerically"):
        eval_edge("coverage > banana", {"metrics": {"coverage": 79.5}})
    with pytest.raises(ValueError, match="cannot compare metric values numerically"):
        eval_edge("coverage > 0", {"metrics": {"coverage": "not-a-number"}})


def test_eval_status_quoted_operand():
    """EVAL-07: status comparisons strip quotes via generic dispatch."""
    outcome = {**DOC_SYNC_OUTCOME, "status": "done"}
    assert eval_edge('status == "done"', outcome) is True
    assert eval_edge("status == done", outcome) is True
    assert eval_edge('status != "blocked"', outcome) is True


def test_eval_missing_metric_raises():
    """EVAL-07: absent metrics raise instead of returning False for == and !=."""
    outcome = {"status": "done", "metrics": {}}
    with pytest.raises(ValueError, match="metric 'missing_key' not found"):
        eval_edge("missing_key == 0", outcome)
    with pytest.raises(ValueError, match="metric 'missing_key' not found"):
        eval_edge("missing_key != 0", outcome)


def test_validate_outcome_rejects_invalid_types_and_enums():
    """VALIDATE-06: type/enum checks and unknown mission warnings."""
    base = {
        "mission": "doc-sync",
        "repo": "/tmp",
        "base_branch": "main",
        "metrics": {"drift_open": 0, "code_bug_findings": 0},
        "deferred_missions": [],
    }
    errors = validate_outcome({**base, "status": "banana", "prs_merged": 1})
    assert any("invalid status" in e for e in errors)

    errors = validate_outcome({**base, "status": "done", "prs_merged": "not-a-number"})
    assert any("prs_merged must be int" in e for e in errors)

    errors = validate_outcome(
        {
            **base,
            "status": "done",
            "prs_merged": 1,
            "metrics": {"drift_open": "zero", "code_bug_findings": 0},
        }
    )
    assert any("metric 'drift_open' must be numeric or bool" in e for e in errors)

    errors = validate_outcome({**base, "status": "done", "prs_merged": 1, "mission": "doc-snyc"})
    assert any("unknown mission" in e for e in errors)


def test_split_frontmatter_leading_blank_line():
    """FM-15: leading blank lines and BOM do not block frontmatter parsing."""
    text = "\n\n---\nmission: doc-sync\n---\n# body\n"
    fm, body = split_frontmatter(text)
    assert fm is not None
    assert "mission: doc-sync" in fm
    assert body.startswith("# body")

    bom_text = "\ufeff---\nkey: val\n---\ncontent"
    fm_bom, _ = split_frontmatter(bom_text)
    assert fm_bom is not None
    assert "key: val" in fm_bom


def test_split_frontmatter_crlf_line_endings(tmp_path: Path):
    """FM-15: CRLF line endings are normalized; frontmatter is not treated as missing."""
    crlf_text = (
        "---\r\n"
        "fleet-outcome:\r\n"
        "  mission: doc-sync\r\n"
        "  status: done\r\n"
        "---\r\n"
        "# body\r\n"
    )
    fm, body = split_frontmatter(crlf_text)
    assert fm is not None
    assert "mission: doc-sync" in fm
    assert body.startswith("# body")

    doc = tmp_path / "crlf-readiness.md"
    doc.write_bytes(crlf_text.encode("utf-8"))
    outcome = parse_readiness(doc)
    assert outcome["mission"] == "doc-sync"
    assert outcome["status"] == "done"


def test_eval_deferred_contains_bare_string_and_dotted_id():
    """DEFER-16: bare-string items and dotted mission ids match to end-of-string."""
    outcome = {
        **DOC_SYNC_OUTCOME,
        "deferred_missions": ["test.coverage", {"id": "bug.batch", "reason": "x"}],
    }
    assert eval_edge("deferred_missions contains test.coverage", outcome) is True
    assert eval_edge("deferred_missions contains bug.batch", outcome) is True
    assert eval_edge("deferred_missions contains test", outcome) is False


def test_eval_deferred_contains_strips_quotes_and_keeps_bare(tmp_path: Path):
    """M3a: deferred_missions contains strips matching surrounding quotes from the
    operand and still accepts bare unquoted operands, so YAML edge expressions can
    be written either way consistently with the == path (which already strips)."""
    outcome = {
        **DOC_SYNC_OUTCOME,
        "deferred_missions": ["bug-batch"],
    }
    # Double-quoted operand should match.
    assert eval_edge('deferred_missions contains "bug-batch"', outcome) is True
    # Single-quoted operand should match.
    assert eval_edge("deferred_missions contains 'bug-batch'", outcome) is True
    # Quoted operand that is NOT in the list returns False (not an error).
    assert eval_edge('deferred_missions contains "nope"', outcome) is False
    assert eval_edge("deferred_missions contains 'nope'", outcome) is False
    # Bare unquoted operand still works (regression guard).
    assert eval_edge("deferred_missions contains bug-batch", outcome) is True
    assert eval_edge("deferred_missions contains nope", outcome) is False
    # Dict-shaped deferred_missions entries with id also match a quoted operand.
    dict_outcome = {
        **DOC_SYNC_OUTCOME,
        "deferred_missions": [{"id": "bug-batch", "reason": "x"}],
    }
    assert eval_edge('deferred_missions contains "bug-batch"', dict_outcome) is True
    assert eval_edge("deferred_missions contains 'bug-batch'", dict_outcome) is True


def test_pick_next_node_terminal_all_false_returns_none():
    """M3b: a node whose edges all evaluate False yields None (terminal)."""
    campaign = {
        "edges": {
            "docs": [
                {"to": "bugs", "if": "code_bug_findings > 0"},
                {"to": "rare", "if": "drift_open > 999"},
            ],
        }
    }
    # DOC_SYNC_OUTCOME has code_bug_findings == 0 and drift_open == 0; both edges
    # evaluate False, so pick_next_node returns None instead of falling through
    # to a default.
    assert pick_next_node(campaign, "docs", DOC_SYNC_OUTCOME) is None


def test_pick_next_node_missing_edges_key_returns_none():
    """M3b: when the campaign has no edges entry for the node, return None."""
    # Campaign has no 'edges' key at all.
    assert pick_next_node({}, "docs", DOC_SYNC_OUTCOME) is None
    # Campaign has 'edges' but no entry for this node.
    campaign = {"edges": {"other": [{"to": "x", "if": "always"}]}}
    assert pick_next_node(campaign, "docs", DOC_SYNC_OUTCOME) is None
    # Campaign edge list explicitly null for this node.
    campaign_null = {"edges": {"docs": None}}
    assert pick_next_node(campaign_null, "docs", DOC_SYNC_OUTCOME) is None


def test_pick_next_node_skips_malformed_non_dict_edges():
    """M3b: non-dict edge entries are skipped without raising."""
    campaign = {
        "edges": {
            "docs": [
                "not-a-dict",
                123,
                None,
                {"to": "tests", "if": "always"},
            ],
        }
    }
    # The first three entries are skipped; the dict entry wins.
    assert pick_next_node(campaign, "docs", DOC_SYNC_OUTCOME) == "tests"


def test_pick_next_node_matched_edge_missing_to_raises():
    """F4: a matched edge with no 'to' is a misconfigured campaign, not a terminal node.
    It now FAILS LOUDLY (raises) instead of returning None (which read as 'campaign done')."""
    campaign = {
        "edges": {
            "docs": [
                {"if": "always"},  # missing 'to' -> misconfiguration
                {"to": "tests", "if": "always"},
            ],
        }
    }
    with pytest.raises(ValueError):
        pick_next_node(campaign, "docs", DOC_SYNC_OUTCOME)


def test_parse_fixture_readiness(tmp_path: Path):
    doc = tmp_path / "doc-sync-readiness.md"
    doc.write_text(
        """---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: /x
  base_branch: fleet/b
  prs_merged: 0
  metrics:
    drift_open: 0
    code_bug_findings: 0
  deferred_missions: []
---
# body
""",
        encoding="utf-8",
    )
    outcome = parse_readiness(doc)
    assert outcome["mission"] == "doc-sync"
    assert validate_outcome(outcome, doc) == []