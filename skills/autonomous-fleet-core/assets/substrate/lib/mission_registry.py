"""Mission id → ledger and readiness doc paths under docs/.

`MISSION_DOCS` is the schema-level registry: every documented mission, including
the ones demoted to `docs/exploratory/missions/` in Commit D (2026-06-23). Their
`fleet-outcome` shape is still valid; only their shipped status changed.

`SHIPPED_MISSIONS` is the subset of `MISSION_DOCS` whose SKILL.md actually lives
under `skills/<mission>/`. Tests that read a mission's SKILL.md from `skills/`
(e.g. the role-topology guard) iterate this set, not `MISSION_DOCS`, so they
don't false-fail on missions in the exploratory bucket. To promote a mission
back, add its id here AFTER `git mv`-ing the SKILL.md back to `skills/`.
"""

from __future__ import annotations

import os

from .fleet_registry import MISSIONS


def run_short_suffix() -> str:
    """Per-run ledger key (issue #96). When the coordinator exports
    FLEET_RUN_SHORT (the run_id's 6-hex tail) at SELF-ORIENTATION, ledger
    filenames carry it — two concurrent same-mission runs stop sharing a
    write target. Names keep the `*-progress.md`/`*-readiness.md` shape so
    every validator glob still matches."""
    import re as _re

    val = os.environ.get("FLEET_RUN_SHORT", "").strip()
    if val and _re.fullmatch(r"[0-9a-f]{6}", val):
        return f"-{val}"
    return ""


def ledger_dir() -> str:
    """Directory fleet ledgers/readiness docs live under (issue #101).

    Default `docs`. Repos whose docs/ is a published docs-site tree (Docusaurus,
    Sphinx, MkDocs, Starlight) set `FLEET_LEDGER_DIR=.fleet/docs` (recorded by
    setup-autonomous-fleet as LEDGER_DIR in fleet-config.md) so fleet files
    never break or publish through the site build. Trailing slashes stripped.
    """
    return os.environ.get("FLEET_LEDGER_DIR", "docs").rstrip("/") or "docs"

SHIPPED_MISSIONS: frozenset[str] = frozenset(
    mission_id for mission_id, row in MISSIONS.items() if row["shipped"] is True
)

MISSION_DOCS: dict[str, dict[str, str]] = {
    mission_id: {
        "progress": str(row["progress_doc"]),
        "readiness": str(row["readiness_doc"]),
    }
    for mission_id, row in MISSIONS.items()
}


def resolve_readiness_file(mission: str, repo_root: str = ".") -> str:
    """Post-run readiness discovery (issue #96/#129 round-2): a run-keyed run
    writes `<mission>-<run_short>-readiness.md`, but campaign drivers resolve
    the path BEFORE any run_id exists. Return the newest on-disk match of
    `<mission>*-readiness.md` under the ledger dir (keyed or unkeyed);
    fall back to the exact (possibly keyed-by-env) registry path when
    nothing exists yet."""
    from pathlib import Path as _Path

    base = MISSION_DOCS.get(mission, {}).get(
        "readiness", f"{mission}-readiness.md"
    )
    stem = base.replace("-readiness.md", "")
    root = _Path(repo_root) / ledger_dir()
    matches = sorted(
        root.glob(f"{stem}*-readiness.md"),
        key=lambda q: q.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return str(matches[0].relative_to(_Path(repo_root)))
    return readiness_path(mission)


def readiness_path(mission: str) -> str:
    if mission not in MISSION_DOCS:
        return f"{ledger_dir()}/{mission}{run_short_suffix()}-readiness.md"
    doc = MISSION_DOCS[mission]["readiness"]
    suffix = run_short_suffix()
    if suffix:
        doc = doc.replace("-readiness.md", f"{suffix}-readiness.md")
    return f"{ledger_dir()}/{doc}"


def progress_path(mission: str) -> str:
    if mission not in MISSION_DOCS:
        return f"{ledger_dir()}/{mission}{run_short_suffix()}-progress.md"
    doc = MISSION_DOCS[mission]["progress"]
    suffix = run_short_suffix()
    if suffix:
        doc = doc.replace("-progress.md", f"{suffix}-progress.md")
    return f"{ledger_dir()}/{doc}"


def headless_emit_mission(mission: str) -> str:
    """Map shell mission names to the slug used for headless dry-run trace emission."""
    if mission == "fleet-program":
        return "doc-sync"
    return mission
