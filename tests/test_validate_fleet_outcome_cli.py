"""Tests for the scripts/validate_fleet_outcome.py CLI (was 22% covered).

Invokes main() IN-PROCESS so coverage credits the CLI lines.
"""

from __future__ import annotations

import importlib.util
import sys
import pytest
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
  reviewer_mode: cross-vendor-structural
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
  reviewer_mode: cross-vendor-structural
  metrics:
    drift_open: 0
    code_bug_findings: 0
---
# bad
"""


REVIEWER_MODE_VALID = """---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: /tmp/r
  base_branch: fleet/b
  prs_merged: 1
  reviewer_mode: same-vendor-instructed
  metrics:
    drift_open: 0
    code_bug_findings: 0
---
# ok
"""

REVIEWER_MODE_INVALID = """---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: /tmp/r
  base_branch: fleet/b
  prs_merged: 1
  reviewer_mode: solo
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


def test_reviewer_mode_present_valid_returns_zero(tmp_path, monkeypatch, capsys):
    doc = tmp_path / "doc-sync-readiness.md"
    doc.write_text(REVIEWER_MODE_VALID)
    monkeypatch.setattr(sys, "argv", ["validate", str(doc)])
    rc = vfo.main()
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_reviewer_mode_present_invalid_returns_one_with_fail(
    tmp_path, monkeypatch, capsys
):
    doc = tmp_path / "doc-sync-readiness.md"
    doc.write_text(REVIEWER_MODE_INVALID)
    monkeypatch.setattr(sys, "argv", ["validate", str(doc)])
    rc = vfo.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "invalid reviewer_mode 'solo'" in out
    assert "cross-vendor-structural, same-vendor-instructed, single-process-instructed" in out


def test_reviewer_mode_absent_still_validates(tmp_path, monkeypatch, capsys):
    # Historical archives without reviewer_mode still pass, but new runs must record topology.
    doc = tmp_path / "doc-sync-readiness.md"
    doc.write_text(VALID.replace("  reviewer_mode: cross-vendor-structural\n", ""))
    monkeypatch.setattr(sys, "argv", ["validate", str(doc)])
    with pytest.warns(
        UserWarning,
        match="reviewer_mode missing — recording the review topology is required for new runs",
    ):
        rc = vfo.main()
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_default_scan_with_no_docs_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["validate"])
    monkeypatch.setattr(vfo, "collect_readiness_paths", lambda _root: [])

    rc = vfo.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert out == "No readiness docs found.\n"


def test_default_scan_skips_paths_that_disappear(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "gone-readiness.md"
    monkeypatch.setattr(sys, "argv", ["validate"])
    monkeypatch.setattr(vfo, "collect_readiness_paths", lambda _root: [missing])

    rc = vfo.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert f"SKIP {missing} (not found)" in out
    assert "All readiness docs passed fleet-outcome validation." in out
