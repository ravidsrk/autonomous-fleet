"""Tests for the scripts/eval-campaign-edge.py CLI (was 0% covered).

Invokes main() IN-PROCESS (not subprocess) so coverage credits the CLI lines and
the behavior is exercised end to end.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str, fname: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ece = _load("eval_campaign_edge_cli", "eval-campaign-edge.py")

READINESS = """---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: /tmp/r
  base_branch: fleet/b
  prs_merged: 1
  metrics:
    drift_open: 0
    code_bug_findings: 0
---
# body
"""


def _doc(tmp_path: Path) -> Path:
    p = tmp_path / "doc-sync-readiness.md"
    p.write_text(READINESS)
    return p


def test_expr_true_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["eval", "--readiness", str(_doc(tmp_path)), "--expr", "code_bug_findings == 0"]
    )
    rc = ece.main()
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["result"] is True


def test_expr_false_returns_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["eval", "--readiness", str(_doc(tmp_path)), "--expr", "code_bug_findings > 0"]
    )
    rc = ece.main()
    assert rc != 0
    assert json.loads(capsys.readouterr().out)["result"] is False


def test_campaign_picks_next_node(tmp_path, monkeypatch, capsys):
    campaign = tmp_path / "c.yaml"
    campaign.write_text(
        "start: docs\n"
        "nodes:\n"
        "  docs: { mission: doc-sync }\n"
        "  tests: { mission: test-coverage }\n"
        "edges:\n"
        "  docs:\n"
        "    - { to: tests, if: always }\n"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["eval", "--readiness", str(_doc(tmp_path)), "--campaign", str(campaign), "--current-node", "docs"],
    )
    rc = ece.main()
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["next"] == "tests"
