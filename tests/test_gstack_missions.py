"""gstack-derived exploratory missions and research doc."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs" / "gstack-missions-research.md"
GSTACK_SLUGS = (
    "product-framing",
    "browser-qa-fix",
    "security-cso-audit",
    "devex-audit",
    "release-document",
    "incident-investigate",
)


def test_gstack_research_doc_exists_and_names_missions() -> None:
    assert RESEARCH.is_file()
    text = RESEARCH.read_text(encoding="utf-8")
    assert "gstack architecture" in text.lower() or "gstack architecture (observed)" in text
    for slug in GSTACK_SLUGS:
        assert slug in text
    assert "(deferred)" not in text
    assert "all six" in text.lower() or "all **six**" in text


def test_gstack_mission_dirs_have_skill_and_banner() -> None:
    for slug in GSTACK_SLUGS:
        base = ROOT / "docs" / "exploratory" / "missions" / slug
        skill = base / "SKILL.md"
        assert skill.is_file(), slug
        body = skill.read_text(encoding="utf-8")
        assert "status: exploratory" in body
        assert "fleet-component: \"mission\"" in body or 'fleet-component: "mission"' in body
        assert "## GOAL" in body
        assert "## ROLE PIPELINE" in body
        assert "## LEDGER" in body
        assert "## TASK STRUCTURE" in body
        assert "## DONE" in body
        assert "## DECISION DEFAULTS" in body
        assert "fleet-outcome" in body.lower()
        assert (base / "assets" / "banner.png").is_file()
        assert (base / "assets" / "banner-prompt.txt").is_file()


def test_gstack_missions_lint_clean() -> None:
    for slug in GSTACK_SLUGS:
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "lib" / "skill_lint.py"), str(
                ROOT / "docs" / "exploratory" / "missions" / slug
            )],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, f"{slug}: {r.stderr}"


def test_catalog_references_gstack_missions() -> None:
    umbrella = (ROOT / "skills" / "autonomous-fleet" / "SKILL.md").read_text(encoding="utf-8")
    catalog = (ROOT / "skills" / "autonomous-fleet" / "references" / "missions.md").read_text(
        encoding="utf-8"
    )
    for slug in GSTACK_SLUGS:
        assert slug in umbrella, slug
        assert slug in catalog, slug


@pytest.mark.parametrize("slug", GSTACK_SLUGS)
def test_gstack_mission_not_promotion_ready(slug: str) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.mission_promotion import assess_promotion

    report = assess_promotion(ROOT, slug)
    assert not report.ready
    assert report.missing