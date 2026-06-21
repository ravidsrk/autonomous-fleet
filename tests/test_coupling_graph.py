"""Tests for scripts/coupling-graph.py (move #5 decomposition tooling)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "coupling_graph", ROOT / "scripts" / "coupling-graph.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _fixture(tmp_path: Path) -> Path:
    """A tiny repo: a python hub imported by two callers + a coupled JS pair."""
    (tmp_path / "hub.py").write_text("VALUE = 1\n")
    (tmp_path / "a.py").write_text("from hub import VALUE\nimport b\n")
    (tmp_path / "b.py").write_text("import hub\n")
    (tmp_path / "c.py").write_text("import hub\n")  # third hub importer
    (tmp_path / "front.ts").write_text("import { x } from './util';\n")
    (tmp_path / "util.ts").write_text("export const x = 1;\n")
    (tmp_path / "lonely.py").write_text("x = 1\n")  # isolated, no edges
    return tmp_path


def test_analyze_clusters_and_hubs(tmp_path: Path):
    cg = _load()
    result = cg.analyze(_fixture(tmp_path), hub_threshold=3)

    # hub.py is imported by a.py, b.py, c.py -> in-degree 3 -> a serialize-always hub.
    hub_files = {h["file"] for h in result["hubs"]}
    assert "hub.py" in hub_files
    assert next(h for h in result["hubs"] if h["file"] == "hub.py")["in_degree"] == 3

    # The python files form one weakly-connected cluster; the TS pair another.
    clustered = {f for c in result["clusters"] for f in c}
    assert {"hub.py", "a.py", "b.py", "c.py"} <= clustered
    assert {"front.ts", "util.ts"} <= clustered

    # The isolated file is in no multi-file cluster.
    assert "lonely.py" not in clustered

    # Edges are intra-repo only: no external/stdlib targets leak in.
    targets = {dst for _src, dst in result["edges"]}
    assert targets <= set(result["files"])


def test_js_relative_import_resolves(tmp_path: Path):
    cg = _load()
    _fixture(tmp_path)
    adj = cg.build_graph(tmp_path)
    assert "util.ts" in adj["front.ts"]


def test_bare_specifier_is_external(tmp_path: Path):
    cg = _load()
    (tmp_path / "app.ts").write_text("import React from 'react';\n")
    adj = cg.build_graph(tmp_path)
    # A bare (node_modules) specifier must not become an intra-repo edge.
    assert adj["app.ts"] == []
