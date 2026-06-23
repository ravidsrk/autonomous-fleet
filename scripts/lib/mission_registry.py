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

SHIPPED_MISSIONS: frozenset[str] = frozenset(
    {
        "doc-sync",
        "test-coverage",
        "adversarial-review-and-fix",
    }
)

MISSION_DOCS: dict[str, dict[str, str]] = {
    "doc-sync": {"progress": "doc-sync-progress.md", "readiness": "doc-sync-readiness.md"},
    "test-coverage": {
        "progress": "test-coverage-progress.md",
        "readiness": "test-coverage-readiness.md",
    },
    "dependency-update": {
        "progress": "dependency-update-progress.md",
        "readiness": "dependency-update-readiness.md",
    },
    "cleanup": {"progress": "cleanup-progress.md", "readiness": "cleanup-readiness.md"},
    "bug-batch": {"progress": "bug-batch-progress.md", "readiness": "bug-batch-readiness.md"},
    "adversarial-review-and-fix": {
        "progress": "arch-build-progress.md",
        "readiness": "arch-build-readiness.md",
    },
    "targeted-migration": {
        "progress": "migration-progress.md",
        "readiness": "migration-readiness.md",
    },
    "design-integration": {
        "progress": "parity-progress.md",
        "readiness": "parity-readiness.md",
    },
    "landing-page-convergence": {
        "progress": "landing-progress.md",
        "readiness": "landing-readiness.md",
    },
    "legacy-rebuild": {
        "progress": "rebuild-progress.md",
        "readiness": "rebuild-readiness.md",
    },
    "take-product-to-completion": {
        "progress": "completion-progress.md",
        "readiness": "completion-readiness.md",
    },
    "inference-cost": {
        "progress": "inference-cost-progress.md",
        "readiness": "inference-cost-readiness.md",
    },
}


def readiness_path(mission: str) -> str:
    if mission not in MISSION_DOCS:
        return f"docs/{mission}-readiness.md"
    return f"docs/{MISSION_DOCS[mission]['readiness']}"


def progress_path(mission: str) -> str:
    if mission not in MISSION_DOCS:
        return f"docs/{mission}-progress.md"
    return f"docs/{MISSION_DOCS[mission]['progress']}"
