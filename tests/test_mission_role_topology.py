"""Regression guard for per-mission role topology.

The framework's defining rule (`engine.md` cross-vendor reviewer) is that the PR
reviewer must be a DIFFERENT vendor than the builder, and the README pins the
canonical staffing: @codex builds (@grok for design missions), a fresh
build-blind @claude reviews, @claude integrates.

Two earlier fix commits missed drift across the corpus (a same-vendor
self-review in legacy-rebuild, builder/reviewer contradictions in
targeted-migration and take-product-to-completion, six missions staffing the
mirror topology). This test makes the invariant enforceable so it cannot
silently regress again. It reads only the `## ROLE PIPELINE` section of each
mission SKILL.md — the canonical declaration.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.mission_registry import MISSION_DOCS  # noqa: E402

MISSIONS = sorted(MISSION_DOCS)

# A handle DIRECTLY assigned a code-build action: "@codex builds", "@codex (per bug) writes",
# "@grok rebuilds". Actor-adjacency avoids false hits on negations ("the reviewer @claude never
# writes code") and on the builder-choice callout ("Flipping to @codex.").
BUILDER = re.compile(
    r"@(codex|claude|grok)\s+(?:\([^)]*\)\s+)?(?:builds?|codes?|writes?|rebuilds?|implements?|performs?|migrates?)\b",
    re.I,
)
# The PR-review bullet: "@<handle> reviews each ... PR".
REVIEWER = re.compile(r"@(codex|claude|grok)\s+reviews\s+each\b", re.I)


def _role_pipeline(mission: str) -> str:
    text = (ROOT / "skills" / mission / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^## ROLE PIPELINE\b(.*?)(?=^## )", text, re.S | re.M)
    assert m, f"{mission}: no '## ROLE PIPELINE' section"
    return m.group(1)


@pytest.mark.parametrize("mission", MISSIONS)
def test_reviewer_is_fresh_build_blind_claude(mission: str):
    block = _role_pipeline(mission)
    reviewers = {h.lower() for h in REVIEWER.findall(block)}
    assert reviewers == {"claude"}, (
        f"{mission}: PR reviewer(s) {reviewers or '{none}'} — the canonical reviewer is @claude"
    )
    for line in block.splitlines():
        if REVIEWER.search(line):
            low = line.lower()
            assert "fresh" in low and "build-blind" in low, (
                f"{mission}: reviewer bullet must declare structural build-blindness "
                f"('fresh', 'build-blind'): {line.strip()}"
            )


@pytest.mark.parametrize("mission", MISSIONS)
def test_builder_is_cross_vendor(mission: str):
    block = _role_pipeline(mission)
    builders = {h.lower() for h in BUILDER.findall(block)}
    assert builders, f"{mission}: no builder role found in ROLE PIPELINE"
    assert builders <= {"codex", "grok"}, (
        f"{mission}: builder(s) {builders} — must be @codex (or @grok for design missions)"
    )
    assert "claude" not in builders, (
        f"{mission}: @claude is both builder and reviewer — same-vendor self-review "
        f"(violates engine.md cross-vendor rule)"
    )


# The `## Worker skills` table is INJECTED into each worker on DISPATCH, so a stale vendor here
# launches a worker in the wrong role even when ROLE PIPELINE is correct. Guard it too.
BUILD_WORD = re.compile(
    r"\b(build|builds|code|codes|write|writes|fix|fixes|bump|bumps|implement|implements|rebuild|rebuilds|migrate|migrates|clean)\b",
    re.I,
)
REVIEW_WORD = re.compile(r"\breview", re.I)
ROW_CELL = re.compile(r"^\|\s*([^|]+?)\s*\|", re.M)  # first column of each table row
HANDLE = re.compile(r"@(codex|claude|grok)\b", re.I)


def _worker_skills(mission: str) -> str:
    text = (ROOT / "skills" / mission / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^## Worker skills\b(.*?)(?=^## )", text, re.S | re.M)
    assert m, f"{mission}: no '## Worker skills' section"
    return m.group(1)


@pytest.mark.parametrize("mission", MISSIONS)
def test_worker_skills_roles_are_cross_vendor(mission: str):
    block = _worker_skills(mission)
    builders: set[str] = set()
    reviewers: set[str] = set()
    for cell in ROW_CELL.findall(block):
        handles = {h.lower() for h in HANDLE.findall(cell)}
        if not handles:
            continue  # header / separator row
        if REVIEW_WORD.search(cell):  # a reviewer row is not a builder (handles "build-blind reviewer")
            reviewers |= handles
        elif BUILD_WORD.search(cell):
            builders |= handles
    assert builders <= {"codex", "grok"}, (
        f"{mission}: Worker-skills builder(s) {builders} — must be @codex (or @grok for design)"
    )
    assert reviewers <= {"claude"}, (
        f"{mission}: Worker-skills reviewer(s) {reviewers} — must be @claude"
    )
    assert not (builders & reviewers), (
        f"{mission}: Worker-skills assigns build and review to the same vendor "
        f"{builders & reviewers} — same-vendor self-review"
    )
