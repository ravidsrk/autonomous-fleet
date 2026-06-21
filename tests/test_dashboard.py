"""Tests for scripts/render-dashboard.py (move #8 read-only dashboard)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "render_dashboard", ROOT / "scripts" / "render-dashboard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _fixture(tmp_path: Path) -> Path:
    """A tiny repo/docs tree exercising both ledger formats + a readiness doc."""
    docs = tmp_path / "docs"
    docs.mkdir()
    # Pipe-row progress ledger (arch-build style): one of each zone.
    (docs / "alpha-progress.md").write_text(
        "# alpha\n\n"
        "TASK build-one | WAVE=1 | CODED=t PR_OPEN=f REVIEWED=f MERGED=f ACCEPT=f | NOTE=in flight\n"
        "TASK build-two | WAVE=1 | CODED=t PR_OPEN=t REVIEWED=f MERGED=f ACCEPT=f | NOTE=awaiting review\n"
        "TASK build-three | WAVE=1 | CODED=t PR_OPEN=t REVIEWED=t MERGED=f ACCEPT=f | NOTE=clean\n"
        "TASK build-four | WAVE=1 | CODED=t PR_OPEN=t REVIEWED=t MERGED=t ACCEPT=t | NOTE=shipped\n"
        "TASK build-stuck | WAVE=1 | CODED=t PR_OPEN=t REVIEWED=f MERGED=f ACCEPT=f | NOTE=BLOCKED max-rounds\n"
    )
    # Table-flag progress ledger (review-fix style).
    (docs / "beta-progress.md").write_text(
        "# beta\n\n"
        "| TASK | SEV | FILE | CLOSES | CODED | PR_OPEN | REVIEWED | MERGED | ACCEPT | NOTE |\n"
        "|------|-----|------|--------|-------|---------|----------|--------|--------|------|\n"
        "| fix-x | H | indep | X1 | t | t | t | t | t | merged |\n"
        "| fix-y | M | indep | Y1 | t | t | f | f | f | open |\n"
    )
    # Readiness doc with fleet-outcome frontmatter.
    (docs / "alpha-readiness.md").write_text(
        "---\n"
        "fleet-outcome:\n"
        "  mission: doc-sync\n"
        "  status: done\n"
        "  repo: owner/repo\n"
        "  base_branch: fleet/alpha\n"
        "  prs_merged: 4\n"
        "  cost_estimate: 1.25\n"
        "  metrics:\n"
        "    drift_open: 0\n"
        "    code_bug_findings: 0\n"
        "---\n\n# alpha readiness\n"
    )
    return tmp_path


def test_zone_for_flag_combinations():
    rd = _load()

    def task(note="", **flags):
        return {"flags": flags, "note": note, "source": "x", "name": "t"}

    assert rd.zone_for(task(CODED="t")) == "Working"
    assert rd.zone_for(task(CODED="t", PR_OPEN="t")) == "In review"
    assert rd.zone_for(task(CODED="t", PR_OPEN="t", REVIEWED="t")) == "Ready to merge"
    assert rd.zone_for(task(CODED="t", PR_OPEN="t", REVIEWED="t", MERGED="t")) == "Done"
    assert rd.zone_for(task(note="BLOCKED max-rounds", CODED="t", PR_OPEN="t")) == "Needs you"


def test_build_model_parses_both_ledger_formats(tmp_path: Path):
    rd = _load()
    model = rd.build_model(_fixture(tmp_path))

    # Pipe-row ledger: one task per active zone, one merged (done).
    names = {t["name"] for z in model["zones"].values() for t in z}
    assert {"build-one", "build-two", "build-three", "build-stuck"} <= names
    assert {t["name"] for z in [model["done"]] for t in z} >= {"build-four", "fix-x"}

    # Zones placed correctly.
    assert any(t["name"] == "build-one" for t in model["zones"]["Working"])
    assert any(t["name"] == "build-two" for t in model["zones"]["In review"])
    assert any(t["name"] == "build-three" for t in model["zones"]["Ready to merge"])
    assert any(t["name"] == "build-stuck" for t in model["zones"]["Needs you"])

    # Table-flag ledger parsed too.
    assert any(t["name"] == "fix-y" for t in model["zones"]["In review"])

    # Readiness outcome parsed.
    assert len(model["outcomes"]) == 1
    assert model["outcomes"][0]["mission"] == "doc-sync"


def test_render_html_is_self_contained(tmp_path: Path):
    rd = _load()
    model = rd.build_model(_fixture(tmp_path))
    out = rd.render_html(model)
    assert out.lstrip().startswith("<!doctype html>")
    for zone in rd.ZONES:
        assert zone in out
    # Self-contained: no external scripts or stylesheet/font links.
    assert "<script" not in out
    assert "http://" not in out and "https://" not in out
    # Renders a real task and the readiness mission.
    assert "build-three" in out
    assert "doc-sync" in out
