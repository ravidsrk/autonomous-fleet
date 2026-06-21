"""Coverage for this session's new code via IN-PROCESS main() invocation.

The CLIs are exercised elsewhere via subprocess, which coverage.py cannot see (separate process).
These call main() in-process with monkeypatched argv so the CLI bodies + error paths are covered AND
behaviour is asserted (not coverage padding).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str, fname: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cg = _load("coupling_graph_cov", "coupling-graph.py")
rd = _load("render_dashboard_cov", "render-dashboard.py")
vfo = _load("vfo_cov", "validate_fleet_outcome.py")


def _pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from . import b\nfrom .b import thing\nimport os\n")
    (pkg / "b.py").write_text("thing = 1\n")
    return tmp_path


# --- coupling-graph.py: the CLI main() (json + human summary + bad path) ---

def test_coupling_main_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cg", str(_pkg(tmp_path)), "--json"])
    assert cg.main() == 0
    data = json.loads(capsys.readouterr().out)
    assert "clusters" in data and "hubs" in data and "files" in data
    assert data["edges"], data
    assert ["pkg/a.py", "pkg/__init__.py"] in data["edges"]
    assert ["pkg/a.py", "pkg/b.py"] in data["edges"]

    expected_cluster = {"pkg/__init__.py", "pkg/a.py", "pkg/b.py"}
    assert any(expected_cluster <= set(cluster) and len(cluster) >= 3 for cluster in data["clusters"])


def test_coupling_main_human_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cg", str(_pkg(tmp_path))])
    assert cg.main() == 0
    out = capsys.readouterr().out
    assert "files:" in out and "clusters" in out and "hubs" in out


def test_coupling_main_rejects_non_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cg", str(tmp_path / "does-not-exist")])
    with pytest.raises(SystemExit):  # argparse p.error -> SystemExit
        cg.main()


# --- render-dashboard.py: the CLI main() writes the HTML ---

def test_dashboard_main_writes_html(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x-progress.md").write_text("# x\nPHASE: DONE\n")
    out = tmp_path / "o.html"
    monkeypatch.setattr(sys, "argv", ["rd", "--repo", str(tmp_path), "-o", str(out)])
    assert rd.main() == 0
    assert out.exists() and out.read_text().strip()


# --- validate_fleet_outcome.py: the error paths added this session ---

def test_validate_main_malformed_yaml_path(tmp_path, monkeypatch, capsys):
    # exercises the (ValueError, yaml.YAMLError) except added in the close-gaps work (F3 fix)
    doc = tmp_path / "bad-readiness.md"
    doc.write_text("---\nfleet-outcome:\n  m: [unclosed\n---\n")
    monkeypatch.setattr(sys, "argv", ["v", str(doc)])
    rc = vfo.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out and "invalid" in out


def test_validate_main_not_found_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["v", str(tmp_path / "missing-readiness.md")])
    rc = vfo.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out
