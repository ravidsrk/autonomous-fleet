"""Tests for scripts/lib/analyze_cost.py and scripts/analyze_cost.py."""
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

from lib.analyze_cost import (  # noqa: E402
    aggregate,
    discover_readiness,
    per_run,
)


_MISSING = object()


def _readiness(
    docs: Path,
    name: str,
    *,
    mission: str = "doc-sync",
    status: str = "done",
    cost: float | None | object = _MISSING,
) -> Path:
    docs.mkdir(parents=True, exist_ok=True)
    metrics = {
        "doc-sync": "    drift_open: 0\n    code_bug_findings: 0\n",
        "test-coverage": "    gaps_open: 0\n    coverage_regressed: false\n",
        "cleanup": "    cleanup_items_open: 0\n",
    }[mission]
    if cost is _MISSING:
        cost_line = ""
    elif cost is None:
        cost_line = "  cost_estimate:\n"
    else:
        cost_line = f"  cost_estimate: {cost}\n"
    path = docs / name
    path.write_text(
        "---\n"
        "fleet-outcome:\n"
        f"  mission: {mission}\n"
        f"  status: {status}\n"
        "  repo: /tmp/repo\n"
        "  base_branch: fleet/base\n"
        "  prs_merged: 1\n"
        "  metrics:\n"
        f"{metrics}"
        "  deferred_missions: []\n"
        f"{cost_line}"
        "---\n"
        "\n"
        "# readiness\n",
        encoding="utf-8",
    )
    return path


def test_per_run_rows_correct_and_missing_cost_is_none(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    a = _readiness(docs, "a-readiness.md", mission="doc-sync", cost=1.25)
    b = _readiness(
        docs,
        "b-readiness.md",
        mission="test-coverage",
        status="partial",
    )

    assert per_run([a, b]) == [
        {
            "source": str(a),
            "mission": "doc-sync",
            "cost_estimate": 1.25,
            "status": "done",
        },
        {
            "source": str(b),
            "mission": "test-coverage",
            "cost_estimate": None,
            "status": "partial",
        },
    ]


def test_per_run_null_cost_estimate_is_counted_missing(tmp_path: Path) -> None:
    doc = _readiness(tmp_path / "docs", "null-readiness.md", cost=None)

    rows = per_run([doc])

    assert rows[0]["cost_estimate"] is None
    assert aggregate(rows)["missing_cost"] == 1


def test_aggregate_total_by_mission_and_missing_values() -> None:
    result = aggregate(
        [
            {"mission": "doc-sync", "cost_estimate": 1.0},
            {"mission": "doc-sync", "cost_estimate": 2.25},
            {"mission": "test-coverage", "cost_estimate": 0.75},
            {"mission": "cleanup", "cost_estimate": None},
            {"mission": "cleanup", "cost_estimate": "bad"},
        ]
    )

    assert result == {
        "total_cost": 4.0,
        "by_mission": {"doc-sync": 3.25, "test-coverage": 0.75},
        "runs": 5,
        "missing_cost": 2,
    }


def test_discover_readiness_sorted_and_missing_root(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    b = _readiness(docs, "b-readiness.md")
    a = _readiness(docs, "a-readiness.md")
    (docs / "readiness-notes.md").write_text("# no\n", encoding="utf-8")

    assert discover_readiness(docs) == [a, b]
    assert discover_readiness(tmp_path / "missing") == []


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "analyze_cost_cli",
        REPO_ROOT / "scripts" / "analyze_cost.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(monkeypatch: pytest.MonkeyPatch, *argv: str) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "argv", ["analyze_cost.py", *argv])
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main()
    return rc, out.getvalue(), err.getvalue()


def test_cli_bad_root(monkeypatch: pytest.MonkeyPatch) -> None:
    rc, _, err = _run_cli(
        monkeypatch,
        "--docs-root",
        "/this/path/does/not/exist",
        "per-run",
    )

    assert rc == 2
    assert "not a directory" in err


def test_cli_no_readiness_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc, _, err = _run_cli(monkeypatch, "--docs-root", str(tmp_path), "per-run")

    assert rc == 1
    assert "no readiness docs" in err


def test_cli_per_run_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _readiness(tmp_path, "a-readiness.md", mission="doc-sync", cost=1.0)

    rc, out, _ = _run_cli(
        monkeypatch, "--docs-root", str(tmp_path), "--json", "per-run"
    )

    assert rc == 0
    data = json.loads(out)
    assert data[0]["mission"] == "doc-sync"
    assert data[0]["cost_estimate"] == 1.0


def test_cli_per_run_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _readiness(tmp_path, "a-readiness.md", mission="doc-sync", cost=1.0)
    _readiness(tmp_path, "b-readiness.md", mission="cleanup")

    rc, out, _ = _run_cli(monkeypatch, "--docs-root", str(tmp_path), "per-run")

    assert rc == 0
    assert "source" in out
    assert "doc-sync" in out
    assert "MISSING" in out


def test_cli_aggregate_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _readiness(tmp_path, "a-readiness.md", mission="doc-sync", cost=1.0)
    _readiness(tmp_path, "b-readiness.md", mission="test-coverage", cost=0.5)

    rc, out, _ = _run_cli(
        monkeypatch, "--docs-root", str(tmp_path), "--json", "aggregate"
    )

    assert rc == 0
    data = json.loads(out)
    assert data["runs"] == 2
    assert data["total_cost"] == 1.5
    assert data["by_mission"] == {"doc-sync": 1.0, "test-coverage": 0.5}


def test_cli_aggregate_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _readiness(tmp_path, "a-readiness.md", mission="doc-sync", cost=1.0)
    _readiness(tmp_path, "b-readiness.md", mission="cleanup")

    rc, out, _ = _run_cli(monkeypatch, "--docs-root", str(tmp_path), "aggregate")

    assert rc == 0
    assert "runs: 2" in out
    assert "missing_cost: 1" in out
    assert "total_cost: 1.00" in out
    assert "  doc-sync: 1.00" in out
