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


def test_skips_vendor_dirs_and_root_package_init(tmp_path: Path):
    cg = _load()
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "vendored.py").write_text("import kept\n")
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "kept.py").write_text("VALUE = 1\n")

    files = {path.relative_to(tmp_path).as_posix() for path in cg.iter_source_files(tmp_path)}
    index = cg._py_module_to_paths(tmp_path)

    assert ".venv/vendored.py" not in files
    assert "kept.py" in files
    assert "vendored" not in index
    assert "" not in index
    assert index["kept"] == tmp_path / "kept.py"


def test_syntax_error_python_file_is_kept_but_imports_are_skipped(tmp_path: Path):
    cg = _load()
    (tmp_path / "bad.py").write_text("def nope(:\n")
    (tmp_path / "target.py").write_text("VALUE = 1\n")

    adj = cg.build_graph(tmp_path)

    assert "bad.py" in adj
    assert adj["bad.py"] == []


def test_non_package_relative_import_does_not_create_false_edge(tmp_path: Path):
    cg = _load()
    (tmp_path / "caller.py").write_text("from ..shared import value\n")
    (tmp_path / "shared.py").write_text("value = 1\n")

    adj = cg.build_graph(tmp_path)

    assert adj["caller.py"] == []


def test_star_import_resolves_to_imported_module(tmp_path: Path):
    cg = _load()
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "tools.py").write_text("THING = 1\n")
    (tmp_path / "consumer.py").write_text("from pkg.tools import *\n")

    adj = cg.build_graph(tmp_path)

    assert adj["consumer.py"] == ["pkg/tools.py"]


def test_js_unique_basename_fallback_and_ambiguous_miss(tmp_path: Path):
    cg = _load()
    (tmp_path / "src").mkdir()
    (tmp_path / "components").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "src" / "app.ts").write_text("import { x } from './button';\n")
    (tmp_path / "components" / "button.tsx").write_text("export const x = 1;\n")
    (tmp_path / "src" / "ambiguous.ts").write_text("import { y } from './dupe';\n")
    (tmp_path / "components" / "dupe.tsx").write_text("export const y = 1;\n")
    (tmp_path / "other" / "dupe.ts").write_text("export const y = 2;\n")

    adj = cg.build_graph(tmp_path)

    assert adj["src/app.ts"] == ["components/button.tsx"]
    assert adj["src/ambiguous.ts"] == []


def test_human_summary_prints_hub_rows(tmp_path: Path, monkeypatch, capsys):
    cg = _load()
    root = _fixture(tmp_path)
    monkeypatch.setattr(
        "sys.argv", ["cg", str(root), "--hub-threshold", "3"]
    )

    assert cg.main() == 0
    out = capsys.readouterr().out

    assert "hubs (serialize-always, in-degree >= 3): 1" in out
    assert "hub.py  <- 3 importers" in out
