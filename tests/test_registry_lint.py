"""Registry-lint rules (issue #90: version-literal guard)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_version_literal_lint_flags_and_exempts(tmp_path) -> None:
    """Issue #90: skill-version literals in tests fail; schema_version is a
    pinned contract and exempt."""
    from lib.registry_lint import lint_no_skill_version_literals_in_tests

    import json as _json
    import shutil as _shutil

    tests = tmp_path / "tests"
    tests.mkdir()
    _shutil.copy2(ROOT / "skills-lock.json", tmp_path / "skills-lock.json")
    lock = _json.loads((tmp_path / "skills-lock.json").read_text(encoding="utf-8"))
    a_current = next(iter(lock["skills"].values()))["version"]
    (tests / "test_bad.py").write_text(
        f'assert v == \'version: "{a_current}"\'\n', encoding="utf-8"
    )
    (tests / "test_ok.py").write_text(
        'assert \'schema_version: "1.0"\' in trace\n'
        'fixture = \'version: "0.0.1"\'\n', encoding="utf-8"
    )
    errors = lint_no_skill_version_literals_in_tests(tmp_path)
    assert len(errors) == 1
    assert "test_bad.py:1" in errors[0]
    assert lint_no_skill_version_literals_in_tests(tmp_path / "nope") == []


def test_real_repo_has_no_version_literals_in_tests() -> None:
    from pathlib import Path
    from lib.registry_lint import lint_no_skill_version_literals_in_tests

    assert lint_no_skill_version_literals_in_tests(Path(__file__).resolve().parents[1]) == []


def test_version_literal_lint_skips_on_lock_errors(tmp_path) -> None:
    """Lock problems are lint_skills_lock's job — this rule stays quiet."""
    from lib.registry_lint import lint_no_skill_version_literals_in_tests

    (tmp_path / "tests").mkdir()
    (tmp_path / "skills-lock.json").write_text("{not json", encoding="utf-8")
    assert lint_no_skill_version_literals_in_tests(tmp_path) == []


def test_mission_state_lint_clean_on_repo_and_catches_unmarked(tmp_path) -> None:
    """Issue #92: routing docs presenting an exploratory mission without a
    marker fail; the real repo is clean."""
    import shutil
    from lib.registry_lint import lint_mission_state_docs

    assert lint_mission_state_docs(ROOT) == []

    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copytree(ROOT / "scripts" / "lib", repo / "scripts" / "lib")
    doc = repo / "skills" / "autonomous-fleet" / "references"
    doc.mkdir(parents=True)
    (doc / "missions.md").write_text(
        "# catalog\n\n| intent | mission |\n|---|---|\n| find bugs | `bug-batch` |\n",
        encoding="utf-8",
    )
    errors = lint_mission_state_docs(repo)
    assert any("bug-batch" in e and "missions.md:5" in e for e in errors)
    # shipped-mission catalog check also fires on this minimal repo
    assert any("shipped mission" in e for e in errors)


def test_adapter_contract_single_source_lint(tmp_path) -> None:
    """Issue #89: adapters must point at adapter-contract.md; a re-inlined
    canonical span fails."""
    import shutil
    from lib.registry_lint import lint_adapter_contract_single_source

    assert lint_adapter_contract_single_source(ROOT) == []

    repo = tmp_path / "repo"
    canon_src = ROOT / "skills/autonomous-fleet-core/references/adapter-contract.md"
    canon_dst = repo / "skills/autonomous-fleet-core/references/adapter-contract.md"
    canon_dst.parent.mkdir(parents=True)
    shutil.copy2(canon_src, canon_dst)
    bad = repo / "skills/autonomous-fleet-adapter-demo"
    bad.mkdir(parents=True)
    (bad / "SKILL.md").write_text(canon_src.read_text(encoding="utf-8"), encoding="utf-8")
    errors = lint_adapter_contract_single_source(repo)
    assert any("re-inlines" in e for e in errors)
    nobind = repo / "skills/autonomous-fleet-adapter-nobind"
    nobind.mkdir(parents=True)
    (nobind / "SKILL.md").write_text("see references/adapter-contract.md\n", encoding="utf-8")
    errors = lint_adapter_contract_single_source(repo)
    assert any("CONTINUE_WORKER binding" in e and "nobind" in e for e in errors)

    good = repo / "skills/autonomous-fleet-adapter-good"
    good.mkdir(parents=True)
    (good / "SKILL.md").write_text(
        "see references/adapter-contract.md\nCONTINUE_WORKER binding: none -> ALIAS\n",
        encoding="utf-8",
    )
    errors = lint_adapter_contract_single_source(repo)
    assert not any("adapter-good" in e for e in errors)
    canon_dst.unlink()
    assert lint_adapter_contract_single_source(repo) == [
        "skills/autonomous-fleet-core/references/adapter-contract.md: missing canonical adapter contract"
    ]


def test_archived_missions_are_not_active_exploratory() -> None:
    from lib.registry_lint import active_exploratory_missions, archived_missions

    missions = {
        "doc-sync": {"shipped": True},
        "bug-batch": {"shipped": False},
        "legacy-rebuild": {"shipped": False, "archived": True},
    }

    assert set(active_exploratory_missions(missions)) == {"bug-batch"}
    assert set(archived_missions(missions)) == {"legacy-rebuild"}


def test_archived_mission_dirs_clean_on_real_repo() -> None:
    from lib.registry_lint import lint_archived_mission_dirs

    assert lint_archived_mission_dirs(ROOT) == []


def test_archived_true_missing_archive_dir_fails(tmp_path) -> None:
    from lib.registry_lint import lint_archived_mission_dirs

    missions = {"legacy-rebuild": {"shipped": False, "archived": True}}

    errors = lint_archived_mission_dirs(tmp_path, missions)

    assert errors == [
        "legacy-rebuild: archived:true but no "
        "docs/exploratory/missions/archive/legacy-rebuild/ on disk"
    ]


def test_archive_dir_without_archived_registry_row_fails(tmp_path) -> None:
    from lib.registry_lint import lint_archived_mission_dirs, lint_registry

    archived = tmp_path / "docs" / "exploratory" / "missions" / "archive" / "orphan"
    archived.mkdir(parents=True)
    (archived / "SKILL.md").write_text("# Orphan\n", encoding="utf-8")

    errors = lint_archived_mission_dirs(tmp_path, {})

    assert errors == [
        "docs/exploratory/missions/archive/orphan/ exists but has no "
        "archived:true registry row"
    ]
    assert any(
        "docs/exploratory/missions/archive/orphan/ exists but has no "
        "archived:true registry row" in error
        for error in lint_registry(tmp_path, {})
    )


def test_parked_marker_marks_unshipped_mission_references(tmp_path) -> None:
    from lib.registry_lint import lint_mission_state_docs

    doc = tmp_path / "skills" / "autonomous-fleet" / "references"
    doc.mkdir(parents=True)
    (doc / "missions.md").write_text(
        "# Mission routing\n\n`legacy-rebuild` is parked while evidence is rebuilt.\n",
        encoding="utf-8",
    )
    missions = {"legacy-rebuild": {"shipped": False, "archived": True}}

    assert lint_mission_state_docs(tmp_path, missions) == []


def test_shipped_catalog_and_lock_lints_report_registry_drift(tmp_path) -> None:
    import json
    from lib import registry_lint

    def write_skill(name: str, text: str = "fleet-component: mission\n") -> Path:
        skill = tmp_path / "skills" / name
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(text, encoding="utf-8")
        return skill

    local = write_skill("local")
    (local / "nested.txt").write_text("payload", encoding="utf-8")
    original_hash = registry_lint.content_hash(local)
    (local / "nested.txt").rename(local / "renamed.txt")
    assert registry_lint.content_hash(local) != original_hash
    locked_hash = registry_lint.content_hash(local)
    drift = write_skill("drift")
    write_skill("unregistered")

    shipped_errors = registry_lint.lint_shipped_mission_dirs(
        tmp_path,
        {"ghost": {"shipped": True, "skill_dir": "ghost"}},
    )
    assert "ghost: shipped:true points to missing skills/ghost/SKILL.md" in shipped_errors
    assert (
        "skills/unregistered/SKILL.md is a mission skill but has no shipped:true registry row"
        in shipped_errors
    )

    (tmp_path / "README.md").write_text("local\n", encoding="utf-8")
    catalog = tmp_path / "skills" / "autonomous-fleet"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "SKILL.md").write_text("local\n", encoding="utf-8")
    catalog_errors = registry_lint.lint_catalog_mentions(
        tmp_path,
        {
            "local": {"shipped": True, "skill_dir": "local"},
            "missing-catalog": {"shipped": True, "skill_dir": "missing-catalog"},
        },
    )
    assert "README.md: missing shipped mission missing-catalog" in catalog_errors
    assert "skills/autonomous-fleet/SKILL.md: missing shipped mission missing-catalog" in catalog_errors

    (tmp_path / "skills-lock.json").write_text(json.dumps({"skills": []}), encoding="utf-8")
    assert registry_lint.lint_skills_lock(tmp_path) == [
        "skills-lock.json: missing skills mapping"
    ]

    lock = {
        "skills": {
            "local": {
                "source": registry_lint.LOCAL_LOCK_SOURCE,
                "computedHash": locked_hash,
            },
            "drift": {
                "source": registry_lint.LOCAL_LOCK_SOURCE,
                "computedHash": "0" * 64,
            },
            "missing-dir": {
                "source": registry_lint.LOCAL_LOCK_SOURCE,
                "computedHash": "1" * 64,
            },
            "stale": {"source": registry_lint.LOCAL_LOCK_SOURCE},
            "external-unpinned": {"source": "anthropics/skills"},
            "external-placeholder": {
                "source": "anthropics/skills",
                "ref": "TODO-pin-me",
            },
            "external-pinned": {"source": "anthropics/skills", "commit": "abc123"},
            "not-a-row": "bad",
        }
    }
    (tmp_path / "skills-lock.json").write_text(json.dumps(lock), encoding="utf-8")

    lock_errors = registry_lint.lint_skills_lock(tmp_path)
    assert any("missing shipped skill dirs: autonomous-fleet" in e for e in lock_errors), lock_errors
    assert any("stale skill dirs not on disk" in e and "stale" in e for e in lock_errors), lock_errors

    hash_errors = registry_lint.lint_lock_hashes(tmp_path)
    assert any("missing-dir has computedHash but no skills/missing-dir/" in e for e in hash_errors)
    assert any("drift computedHash mismatch" in e for e in hash_errors)

    pin_errors = registry_lint.lint_external_source_pins(tmp_path)
    assert any("external source 'anthropics/skills' for external-unpinned is not pinned" in e for e in pin_errors)
    assert any("uses placeholder pin 'TODO-pin-me'" in e for e in pin_errors)


def test_campaign_lint_reports_yaml_and_mission_state_errors(tmp_path) -> None:
    from lib.registry_lint import lint_campaign_missions

    campaigns = tmp_path / "scripts" / "campaigns"
    campaigns.mkdir(parents=True)
    (campaigns / "invalid.yaml").write_text("nodes: [\n", encoding="utf-8")
    (campaigns / "list.yaml").write_text("- not a mapping\n", encoding="utf-8")
    (campaigns / "archived.yaml").write_text(
        "status: archived\nnodes:\n  unknown: { mission: no-such }\n",
        encoding="utf-8",
    )
    (campaigns / "empty.yaml").write_text("nodes: []\n", encoding="utf-8")
    (campaigns / "main.yaml").write_text(
        "campaign: main\n"
        "nodes:\n"
        "  not_mapping: just-a-string\n"
        "  no_mission: { mission: 123 }\n"
        "  unknown: { mission: no-such }\n"
        "  archived: { mission: legacy-rebuild }\n"
        "  exploratory_blocked: { mission: bug-batch }\n"
        "  shipped: { mission: doc-sync }\n",
        encoding="utf-8",
    )

    dogfood = tmp_path / "docs" / "external-dogfood"
    dogfood.mkdir(parents=True)
    (dogfood / "dogfood-campaign.yaml").write_text(
        "campaign: dogfood\n"
        "exploratory: true\n"
        "nodes:\n"
        "  missing_doc: { mission: bug-batch }\n"
        "  has_doc: { mission: targeted-migration }\n",
        encoding="utf-8",
    )
    exploratory_doc = tmp_path / "docs" / "exploratory" / "missions" / "targeted-migration"
    exploratory_doc.mkdir(parents=True)
    (exploratory_doc / "SKILL.md").write_text("# Targeted migration\n", encoding="utf-8")

    (tmp_path / "docs" / "composition-e2e-campaign.yaml").write_text(
        "campaign: top\nallow_exploratory_nodes: true\nnodes:\n  ok: { mission: targeted-migration }\n",
        encoding="utf-8",
    )

    missions = {
        "doc-sync": {"shipped": True},
        "bug-batch": {"shipped": False},
        "targeted-migration": {"shipped": False},
        "legacy-rebuild": {"shipped": False, "archived": True},
    }

    errors = lint_campaign_missions(tmp_path, missions)

    assert any("invalid.yaml: invalid YAML" in e for e in errors), errors
    assert any("main.yaml: node 'unknown' references unknown mission 'no-such'" in e for e in errors), errors
    assert any("main.yaml: node 'archived' references archived mission 'legacy-rebuild'" in e for e in errors), errors
    assert any("main.yaml: node 'exploratory_blocked' references unshipped mission 'bug-batch'" in e for e in errors), errors
    assert any("dogfood-campaign.yaml: node 'missing_doc' references exploratory mission 'bug-batch'" in e for e in errors), errors
    assert not any("has_doc" in e or "composition-e2e-campaign.yaml" in e for e in errors), errors


def test_archived_campaign_nodes_are_rejected_even_with_exploratory_opt_in(tmp_path) -> None:
    from lib.registry_lint import lint_campaign_missions

    campaigns = tmp_path / "scripts" / "campaigns"
    campaigns.mkdir(parents=True)
    (campaigns / "archived-node.yaml").write_text(
        "campaign: archived-node\n"
        "allow_exploratory_nodes: true\n"
        "nodes:\n  rebuild: { mission: legacy-rebuild }\n"
        "edges:\n  rebuild: []\n",
        encoding="utf-8",
    )
    missions = {"legacy-rebuild": {"shipped": False, "archived": True}}

    errors = lint_campaign_missions(tmp_path, missions)

    assert len(errors) == 1
    assert "archived mission 'legacy-rebuild'" in errors[0]
