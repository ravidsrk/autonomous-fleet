"""Registry drift guards for shipped missions and lock-file rows."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import fleet_registry, registry_lint  # noqa: E402
from lib.fleet_outcome import MISSION_METRICS  # noqa: E402
from lib.mission_registry import MISSION_DOCS, SHIPPED_MISSIONS  # noqa: E402


EXPECTED_MISSION_DOCS = {
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

EXPECTED_MISSION_METRICS = {
    "doc-sync": frozenset({"drift_open", "code_bug_findings"}),
    "test-coverage": frozenset({"gaps_open", "coverage_regressed"}),
    "dependency-update": frozenset({"advisories_open", "majors_deferred"}),
    "cleanup": frozenset({"cleanup_items_open"}),
    "bug-batch": frozenset({"bugs_open", "bugs_skipped"}),
    "adversarial-review-and-fix": frozenset(
        {"p0_open", "p1_open", "findings_open", "ops_queue_count"}
    ),
    "targeted-migration": frozenset({"migration_items_open", "old_axis_removed"}),
    "design-integration": frozenset({"parity_items_open", "regressions"}),
    "landing-page-convergence": frozenset({"divergences_open"}),
    "legacy-rebuild": frozenset({"units_open", "floor_preserved", "e2e_verified"}),
    "take-product-to-completion": frozenset(
        {"in_items_open", "roadmap_count", "stubs_remaining", "e2e_verified"}
    ),
    "inference-cost": frozenset(
        {"cost_regressed", "quality_regressed", "levers_open"}
    ),
}


def _write_skill(root: Path, name: str, component: str) -> None:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\nmetadata:\n  fleet-component: {component}\n---\n{name}\n",
        encoding="utf-8",
    )


def _write_lock(root: Path, rows: dict[str, dict[str, str] | str]) -> None:
    (root / "skills-lock.json").write_text(
        json.dumps({"version": 1, "skills": rows}),
        encoding="utf-8",
    )


def _local_row() -> dict[str, str]:
    return {"source": registry_lint.LOCAL_LOCK_SOURCE}


def test_registry_derives_existing_public_values_exactly() -> None:
    assert fleet_registry.RUNTIME_ADAPTERS == (
        "autonomous-fleet-adapter-orca",
        "autonomous-fleet-adapter-claude-code",
        "autonomous-fleet-adapter-grok",
        "autonomous-fleet-adapter-codex",
    )
    assert SHIPPED_MISSIONS == frozenset(
        {"doc-sync", "test-coverage", "adversarial-review-and-fix"}
    )
    assert MISSION_DOCS == EXPECTED_MISSION_DOCS
    assert MISSION_METRICS == EXPECTED_MISSION_METRICS
    assert registry_lint.shipped_missions(fleet_registry.MISSIONS).keys() == SHIPPED_MISSIONS


def test_shipped_true_missing_skill_dir_fails(tmp_path: Path) -> None:
    missions = {
        "ghost-mission": {
            "shipped": True,
            "skill_dir": "ghost-mission",
        }
    }

    errors = registry_lint.lint_shipped_mission_dirs(tmp_path, missions)

    assert errors == [
        "ghost-mission: shipped:true points to missing skills/ghost-mission/SKILL.md"
    ]


def test_mission_skill_without_shipped_registry_row_fails(tmp_path: Path) -> None:
    _write_skill(tmp_path, "unregistered", "mission")

    errors = registry_lint.lint_shipped_mission_dirs(tmp_path, {})

    assert errors == [
        "skills/unregistered/SKILL.md is a mission skill but has no shipped:true registry row"
    ]


def test_catalogs_must_name_each_shipped_mission(tmp_path: Path) -> None:
    _write_skill(tmp_path, "autonomous-fleet", "umbrella")
    (tmp_path / "README.md").write_text("doc-sync\n", encoding="utf-8")
    missions = {
        "doc-sync": {"shipped": True, "skill_dir": "doc-sync"},
        "test-coverage": {"shipped": True, "skill_dir": "test-coverage"},
    }

    errors = registry_lint.lint_catalog_mentions(tmp_path, missions)

    assert errors == [
        "README.md: missing shipped mission test-coverage",
        "skills/autonomous-fleet/SKILL.md: missing shipped mission doc-sync",
        "skills/autonomous-fleet/SKILL.md: missing shipped mission test-coverage",
    ]


def test_missing_catalog_file_reports_error(tmp_path: Path) -> None:
    errors = registry_lint.lint_catalog_mentions(tmp_path, {})

    assert errors == [
        "README.md: missing catalog file",
        "skills/autonomous-fleet/SKILL.md: missing catalog file",
    ]


def test_stale_bug_batch_row_in_skills_lock_fails(tmp_path: Path) -> None:
    _write_skill(tmp_path, "doc-sync", "mission")
    _write_lock(
        tmp_path,
        {
            "bug-batch": _local_row(),
            "doc-sync": _local_row(),
            "skill-creator": {"source": "anthropics/skills"},
        },
    )

    errors = registry_lint.lint_skills_lock(tmp_path)

    assert errors == ["skills-lock.json: stale skill dirs not on disk: bug-batch"]


def test_skills_lock_missing_disk_skill_fails(tmp_path: Path) -> None:
    _write_skill(tmp_path, "doc-sync", "mission")
    _write_lock(tmp_path, {})

    errors = registry_lint.lint_skills_lock(tmp_path)

    assert errors == ["skills-lock.json: missing shipped skill dirs: doc-sync"]


def test_skills_lock_shape_errors_are_reported(tmp_path: Path) -> None:
    assert registry_lint.lint_skills_lock(tmp_path) == ["skills-lock.json: missing"]

    (tmp_path / "skills-lock.json").write_text("{not json", encoding="utf-8")
    assert registry_lint.lint_skills_lock(tmp_path) == [
        "skills-lock.json: invalid JSON: Expecting property name enclosed in double quotes"
    ]

    (tmp_path / "skills-lock.json").write_text("[]", encoding="utf-8")
    assert registry_lint.lint_skills_lock(tmp_path) == [
        "skills-lock.json: missing skills mapping"
    ]


def test_consistent_registry_fixture_passes(tmp_path: Path) -> None:
    _write_skill(tmp_path, "autonomous-fleet", "umbrella")
    _write_skill(tmp_path, "doc-sync", "mission")
    (tmp_path / "README.md").write_text("doc-sync\n", encoding="utf-8")
    (tmp_path / "skills" / "autonomous-fleet" / "SKILL.md").write_text(
        "---\nname: autonomous-fleet\nmetadata:\n  fleet-component: umbrella\n---\ndoc-sync\n",
        encoding="utf-8",
    )
    _write_lock(tmp_path, {"autonomous-fleet": _local_row(), "doc-sync": "local-row"})
    missions = {"doc-sync": {"shipped": True, "skill_dir": "doc-sync"}}

    assert registry_lint.lint_registry(tmp_path, missions) == []


def test_lint_campaign_missions_rejects_unshipped(tmp_path: Path) -> None:
    campaigns = tmp_path / "scripts" / "campaigns"
    campaigns.mkdir(parents=True)
    (campaigns / "bad.yaml").write_text(
        "campaign: bad\nnodes:\n  tidy: { mission: cleanup }\n",
        encoding="utf-8",
    )
    missions = {
        "doc-sync": {"shipped": True, "skill_dir": "doc-sync"},
        "cleanup": {"shipped": False, "skill_dir": "cleanup"},
    }
    errors = registry_lint.lint_campaign_missions(tmp_path, missions)
    assert len(errors) == 1
    assert "unshipped mission 'cleanup'" in errors[0]


def test_lint_campaign_missions_skips_archived(tmp_path: Path) -> None:
    campaigns = tmp_path / "scripts" / "campaigns"
    campaigns.mkdir(parents=True)
    (campaigns / "archived.yaml").write_text(
        "campaign: secure-ship\nstatus: archived-pending-exploratory-promotion\n",
        encoding="utf-8",
    )
    missions = {"dependency-update": {"shipped": False, "skill_dir": "dependency-update"}}
    assert registry_lint.lint_campaign_missions(tmp_path, missions) == []


def test_lint_campaign_missions_invalid_yaml(tmp_path: Path) -> None:
    campaigns = tmp_path / "scripts" / "campaigns"
    campaigns.mkdir(parents=True)
    (campaigns / "broken.yaml").write_text("nodes: [\n", encoding="utf-8")
    errors = registry_lint.lint_campaign_missions(tmp_path, {})
    assert len(errors) == 1
    assert "invalid YAML" in errors[0]


def test_lint_campaign_missions_unknown_mission(tmp_path: Path) -> None:
    campaigns = tmp_path / "scripts" / "campaigns"
    campaigns.mkdir(parents=True)
    (campaigns / "bad.yaml").write_text(
        "campaign: bad\nnodes:\n  x: { mission: no-such-mission }\n",
        encoding="utf-8",
    )
    errors = registry_lint.lint_campaign_missions(tmp_path, {"doc-sync": {"shipped": True}})
    assert len(errors) == 1
    assert "unknown mission" in errors[0]


def test_lint_campaign_missions_skips_malformed_nodes(tmp_path: Path) -> None:
    campaigns = tmp_path / "scripts" / "campaigns"
    campaigns.mkdir(parents=True)
    (campaigns / "null-doc.yaml").write_text("---\n", encoding="utf-8")
    (campaigns / "scalar.yaml").write_text("campaign: x\nnodes: not-a-map\n", encoding="utf-8")
    (campaigns / "list-nodes.yaml").write_text("campaign: z\nnodes: []\n", encoding="utf-8")
    (campaigns / "empty-node.yaml").write_text(
        "campaign: y\nnodes:\n  a: not-a-dict\n  b: { mission: '' }\n",
        encoding="utf-8",
    )
    assert registry_lint.lint_campaign_missions(tmp_path, {}) == []
