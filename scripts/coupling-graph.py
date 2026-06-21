#!/usr/bin/env python3
"""Static import/symbol coupling graph for a repo (move #5 tooling).

A coordinator calls this during DECOMPOSITION to obey the coupling-aware
partitioning rule (Co-Coder, arXiv 2606.00953: +14% pass, -35% cost on
dependency-dense repos): cluster tightly-coupled files into ONE task, mark
hub files serialize-always (upstream of the hot-file rule). See engine.md
DECOMPOSITION.

Stdlib only: `ast` for python, regex for JS/TS. No third-party deps, no network.
The graph is intra-repo: an edge A -> B means file A imports a module that
resolves to file B inside this repo. External/stdlib imports are dropped (they
do not constrain task partitioning).

Output (JSON):
  {
    "files": [<repo-relative path>, ...],
    "edges": [[<from>, <to>], ...],
    "clusters": [[<path>, ...], ...],   # tightly-coupled, one task each
    "hubs": [{"file": <path>, "in_degree": <n>}, ...]   # serialize-always
  }
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

PY_EXT = frozenset({".py"})
JS_EXT = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"})
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".next",
        "coverage",
    }
)

# JS/TS import/require/dynamic-import specifiers. Captures the module string.
_JS_IMPORT = re.compile(
    r"""(?:
        \bimport\b [^'\"]*? from \s* ['\"]([^'\"]+)['\"]   # import x from 'm'
      | \bimport\s*\(\s*['\"]([^'\"]+)['\"]                 # import('m')
      | \bimport\s+['\"]([^'\"]+)['\"]                      # import 'm' (side effect)
      | \bexport\b [^'\"]*? from \s* ['\"]([^'\"]+)['\"]     # export ... from 'm'
      | \brequire\s*\(\s*['\"]([^'\"]+)['\"]                # require('m')
    )""",
    re.VERBOSE,
)


def iter_source_files(root: Path) -> list[Path]:
    """Repo-relative source files we know how to parse, skipping vendored dirs."""
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in PY_EXT or path.suffix in JS_EXT:
            out.append(path)
    return out


def _py_module_to_paths(root: Path) -> dict[str, Path]:
    """Map dotted python module names to repo files (package + module forms)."""
    index: dict[str, Path] = {}
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root)
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        # Index every dotted suffix so `from a.b import c` and `import b` both hit.
        for i in range(len(parts)):
            index[".".join(parts[i:])] = path
    return index


def _py_imports(path: Path) -> list[str]:
    """Top-level dotted names imported by a python file (best-effort)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    names.append(node.module)
                    names.extend(f"{node.module}.{a.name}" for a in node.names)
                else:
                    names.extend(a.name for a in node.names)
            else:
                # PEP 328 relative import (from . / from .x / from ..x). Reconstruct a best-effort
                # dotted name anchored on the file's package dir so the suffix index can resolve it,
                # instead of silently dropping the edge.
                pkg_parts = list(path.parent.parts)
                up = node.level - 1
                if up:
                    pkg_parts = pkg_parts[:-up] if up <= len(pkg_parts) else []
                base = pkg_parts[-1] if pkg_parts else ""
                mod = f"{base}.{node.module}" if base and node.module else (node.module or base)
                if mod:
                    names.append(mod)
                names.extend(f"{mod}.{a.name}" if mod else a.name for a in node.names)
    return names


def _resolve_py(name: str, index: dict[str, Path]) -> Path | None:
    """Resolve a dotted import to a repo file, longest matching prefix first."""
    if name in index:
        return index[name]
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in index:
            return index[cand]
    return None


def _js_imports(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    specs: list[str] = []
    for match in _JS_IMPORT.finditer(text):
        spec = next((g for g in match.groups() if g), None)
        if spec:
            specs.append(spec)
    return specs


def _resolve_js(spec: str, importer: Path, by_stem: dict[str, list[Path]]) -> Path | None:
    """Resolve a relative JS/TS specifier to a repo file. Bare specs are external."""
    if not spec.startswith("."):
        return None  # bare specifier -> node_modules / external, not intra-repo
    base = (importer.parent / spec).resolve()
    # Try the literal path, common extensions, and an index file in a dir.
    cands = [base]
    cands += [base.with_name(base.name + ext) for ext in sorted(JS_EXT)]
    cands += [base / f"index{ext}" for ext in sorted(JS_EXT)]
    for cand in cands:
        if cand.is_file():
            return cand
    # Fall back to a unique basename match (handles ext-rewriting bundlers).
    hits = by_stem.get(base.name, [])
    if len(hits) == 1:
        return hits[0]
    return None


def build_graph(root: Path) -> dict[str, list[str]]:
    """Adjacency: importer -> sorted list of imported repo files (relative paths)."""
    root = root.resolve()
    files = iter_source_files(root)
    py_index = _py_module_to_paths(root)
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        by_stem[f.stem].append(f)

    adj: dict[str, set[str]] = {str(f.relative_to(root)): set() for f in files}
    for path in files:
        src = str(path.relative_to(root))
        if path.suffix in PY_EXT:
            for name in _py_imports(path):
                target = _resolve_py(name, py_index)
                if target is not None and target != path:
                    adj[src].add(str(target.relative_to(root)))
        else:
            for spec in _js_imports(path):
                target = _resolve_js(spec, path, by_stem)
                if target is not None and target != path:
                    adj[src].add(str(target.relative_to(root)))
    return {k: sorted(v) for k, v in sorted(adj.items())}


def _connected_components(nodes: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    """Weakly-connected components over the (directed) coupling graph."""
    undirected: dict[str, set[str]] = {n: set() for n in nodes}
    for src, dsts in adj.items():
        for dst in dsts:
            if dst in undirected:
                undirected[src].add(dst)
                undirected[dst].add(src)
    seen: set[str] = set()
    comps: list[list[str]] = []
    for node in nodes:
        if node in seen:
            continue
        stack = [node]
        comp: list[str] = []
        seen.add(node)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nb in undirected[cur]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        comps.append(sorted(comp))
    return comps


def analyze(root: Path, hub_threshold: int = 3) -> dict[str, Any]:
    """Build the graph and derive clusters + high-in-degree hub files.

    clusters: weakly-connected components of size >= 2 (one task each); isolated
    files are their own trivial cluster and dropped from the cluster list.
    hubs: files whose in-degree (number of importers) >= hub_threshold. These are
    serialize-always: a parallel edit to a hub fans out breakage, so the
    coordinator must NOT hand two concurrent tasks the same hub.
    """
    root = root.resolve()
    adj = build_graph(root)
    nodes = list(adj.keys())

    in_degree: dict[str, int] = defaultdict(int)
    for dsts in adj.values():
        for dst in dsts:
            in_degree[dst] += 1

    comps = _connected_components(nodes, adj)
    clusters = [c for c in comps if len(c) >= 2]
    clusters.sort(key=lambda c: (-len(c), c[0]))

    hubs = [
        {"file": f, "in_degree": in_degree[f]}
        for f in nodes
        if in_degree.get(f, 0) >= hub_threshold
    ]
    hubs.sort(key=lambda h: (-h["in_degree"], h["file"]))

    edges = [[src, dst] for src, dsts in adj.items() for dst in dsts]
    return {
        "files": nodes,
        "edges": edges,
        "clusters": clusters,
        "hubs": hubs,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", type=Path, help="Repo root to analyze")
    p.add_argument(
        "--hub-threshold",
        type=int,
        default=3,
        help="Min in-degree (importers) for a file to count as a hub (default 3)",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON (default human summary)")
    args = p.parse_args()

    root = args.path
    if not root.is_dir():
        p.error(f"{root} is not a directory")

    result = analyze(root, hub_threshold=args.hub_threshold)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"files: {len(result['files'])}  edges: {len(result['edges'])}")
    print(f"clusters (>=2 coupled, one task each): {len(result['clusters'])}")
    for i, cluster in enumerate(result["clusters"], 1):
        print(f"  cluster {i} ({len(cluster)} files): {', '.join(cluster)}")
    print(f"hubs (serialize-always, in-degree >= {args.hub_threshold}): {len(result['hubs'])}")
    for hub in result["hubs"]:
        print(f"  {hub['file']}  <- {hub['in_degree']} importers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
