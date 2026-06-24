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

from .fleet_registry import MISSIONS

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


def readiness_path(mission: str) -> str:
    if mission not in MISSION_DOCS:
        return f"docs/{mission}-readiness.md"
    return f"docs/{MISSION_DOCS[mission]['readiness']}"


def progress_path(mission: str) -> str:
    if mission not in MISSION_DOCS:
        return f"docs/{mission}-progress.md"
    return f"docs/{MISSION_DOCS[mission]['progress']}"
