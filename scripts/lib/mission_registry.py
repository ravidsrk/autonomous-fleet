"""Mission id → ledger and readiness doc paths under docs/."""

from __future__ import annotations

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
}


def readiness_path(mission: str) -> str:
    if mission not in MISSION_DOCS:
        return f"docs/{mission}-readiness.md"
    return f"docs/{MISSION_DOCS[mission]['readiness']}"


def progress_path(mission: str) -> str:
    if mission not in MISSION_DOCS:
        return f"docs/{mission}-progress.md"
    return f"docs/{MISSION_DOCS[mission]['progress']}"