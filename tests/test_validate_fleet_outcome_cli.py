"""Tests for the scripts/validate_fleet_outcome.py CLI (was 22% covered).

Invokes main() IN-PROCESS so coverage credits the CLI lines.
"""

from __future__ import annotations

import importlib.util
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


vfo = _load("validate_fleet_outcome_cli", "validate_fleet_outcome.py")

VALID = """---
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
# ok
"""

INVALID_STATUS = """---
fleet-outcome:
  mission: doc-sync
  status: banana
  repo: /tmp/r
  base_branch: fleet/b
  prs_merged: 1
  metrics:
    drift_open: 0
    code_bug_findings: 0
---
# bad
"""


def test_valid_readiness_doc_returns_zero(tmp_path, monkeypatch, capsys):
    doc = tmp_path / "doc-sync-readiness.md"
    doc.write_text(VALID)
    monkeypatch.setattr(sys, "argv", ["validate", str(doc)])
    rc = vfo.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "mission=doc-sync" in out


def test_invalid_status_returns_one_with_fail(tmp_path, monkeypatch, capsys):
    doc = tmp_path / "doc-sync-readiness.md"
    doc.write_text(INVALID_STATUS)
    monkeypatch.setattr(sys, "argv", ["validate", str(doc)])
    rc = vfo.main()
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out
