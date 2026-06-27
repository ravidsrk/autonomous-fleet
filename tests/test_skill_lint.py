"""Tests for the structural autonomous-fleet SKILL.md linter."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import skill_lint as sl  # noqa: E402
from lib.mission_registry import SHIPPED_MISSIONS  # noqa: E402


ADAPTERS = sorted((ROOT / "skills").glob("autonomous-fleet-adapter-*"))
MISSIONS = [ROOT / "skills" / mission for mission in sorted(SHIPPED_MISSIONS)]


def _copy_skill(source: Path, target: Path) -> Path:
    target.mkdir()
    skill = target / "SKILL.md"
    skill.write_text((source / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
    return target


@pytest.mark.parametrize("adapter", ADAPTERS, ids=lambda path: path.name)
def test_real_adapters_pass_structural_lint(adapter: Path) -> None:
    sl.lint_adapter(adapter)


@pytest.mark.parametrize("mission", MISSIONS, ids=lambda path: path.name)
def test_real_shipped_missions_pass_structural_lint(mission: Path) -> None:
    sl.lint_mission(mission)


def test_acceptance_missing_orca_sync_task_state_fails(tmp_path: Path) -> None:
    skill = _copy_skill(
        ROOT / "skills" / "autonomous-fleet-adapter-orca",
        tmp_path / "autonomous-fleet-adapter-orca",
    )
    path = skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("### SYNC_TASK_STATE(task, status)\n", ""), encoding="utf-8")

    with pytest.raises(sl.SkillLintError) as excinfo:
        sl.lint_adapter(skill)

    assert "SYNC_TASK_STATE" in str(excinfo.value)


def test_acceptance_missing_worker_skills_fails(tmp_path: Path) -> None:
    skill = _copy_skill(ROOT / "skills" / "doc-sync", tmp_path / "doc-sync")
    path = skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("## Worker skills\n", ""), encoding="utf-8")

    with pytest.raises(sl.SkillLintError) as excinfo:
        sl.lint_mission(skill)

    assert "Worker skills" in str(excinfo.value)


def test_template_requires_non_negotiables(tmp_path: Path) -> None:
    skill = _copy_skill(
        ROOT / "skills" / "autonomous-fleet-adapter-template",
        tmp_path / "autonomous-fleet-adapter-template",
    )
    path = skill / "SKILL.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "## NON-NEGOTIABLES THAT DO NOT CHANGE PER TOOL\n", ""
        ),
        encoding="utf-8",
    )

    with pytest.raises(sl.SkillLintError) as excinfo:
        sl.lint_adapter(skill)

    assert "NON-NEGOTIABLES" in str(excinfo.value)


def test_adapter_frontmatter_contract_is_enforced(tmp_path: Path) -> None:
    skill = _copy_skill(ROOT / "skills" / "autonomous-fleet-adapter-codex", tmp_path / "bad")
    path = skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("name: autonomous-fleet-adapter-codex", "name: wrong-name")
    text = text.replace("license: MIT\n", "")
    text = text.replace('fleet-component: "adapter"', 'fleet-component: "mission"')
    path.write_text(text, encoding="utf-8")

    with pytest.raises(sl.SkillLintError) as excinfo:
        sl.lint_adapter(skill)

    message = str(excinfo.value)
    assert "frontmatter name must match directory" in message
    assert "missing frontmatter license" in message
    assert "metadata.fleet-component must be one of" in message


def test_frontmatter_shape_errors_are_reported(tmp_path: Path) -> None:
    missing = tmp_path / "missing-fm.md"
    missing.write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(sl.SkillLintError, match="missing YAML frontmatter"):
        sl.lint_skill(missing)

    scalar = tmp_path / "scalar.md"
    scalar.write_text("---\njust-a-string\n---\n", encoding="utf-8")
    with pytest.raises(sl.SkillLintError, match="frontmatter must be a mapping"):
        sl.lint_skill(scalar)

    invalid = tmp_path / "invalid.md"
    invalid.write_text("---\nmetadata: [\n---\n", encoding="utf-8")
    with pytest.raises(sl.SkillLintError, match="invalid YAML frontmatter"):
        sl.lint_skill(invalid)


def test_adapter_missing_metadata_is_reported(tmp_path: Path) -> None:
    skill = _copy_skill(
        ROOT / "skills" / "autonomous-fleet-adapter-codex",
        tmp_path / "autonomous-fleet-adapter-codex",
    )
    path = skill / "SKILL.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'metadata:\n'
            '  author: "ravidsrk"\n'
            '  version: "1.1.0"\n'
            '  fleet-component: "adapter"\n',
            "",
        ),
        encoding="utf-8",
    )

    with pytest.raises(sl.SkillLintError) as excinfo:
        sl.lint_adapter(skill)

    assert "metadata.fleet-component" in str(excinfo.value)


def test_mission_missing_fleet_outcome_yaml_reference_fails(tmp_path: Path) -> None:
    skill = _copy_skill(ROOT / "skills" / "doc-sync", tmp_path / "doc-sync")
    path = skill / "SKILL.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("**`fleet-outcome` YAML**", "readiness data"),
        encoding="utf-8",
    )

    with pytest.raises(sl.SkillLintError) as excinfo:
        sl.lint_mission(skill)

    assert "fleet-outcome YAML" in str(excinfo.value)


def test_missing_skill_md_is_reported(tmp_path: Path) -> None:
    with pytest.raises(sl.SkillLintError, match="missing SKILL.md"):
        sl.lint_skill(tmp_path / "no-such-skill")


def test_lint_skill_dispatches_and_skips_non_structural_components() -> None:
    sl.lint_skill(ROOT / "skills" / "autonomous-fleet-adapter-codex")
    sl.lint_skill(ROOT / "skills" / "doc-sync")
    sl.lint_skill(ROOT / "skills" / "autonomous-fleet-core")


def test_main_reports_failures_and_success(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert sl.main([str(ROOT / "skills" / "doc-sync")]) == 0
    assert capsys.readouterr().err == ""

    bad = tmp_path / "bad-skill"
    bad.mkdir()
    (bad / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
    assert sl.main([str(bad)]) == 1
    assert "FAIL" in capsys.readouterr().err


# --- lock/version sync rule (finding 66) ------------------------------------

import json  # noqa: E402

from lib import registry_lint as rl  # noqa: E402


def _versioned_skill(root: Path, name: str, version: str, body: str = "body\n") -> Path:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\nmetadata:\n  version: \"{version}\"\n---\n{body}",
        encoding="utf-8",
    )
    return skill_dir


def _write_lock(root: Path, rows: dict) -> Path:
    lock = root / "skills-lock.json"
    lock.write_text(json.dumps({"version": 1, "skills": rows}), encoding="utf-8")
    return lock


def test_real_repo_lock_version_sync_passes() -> None:
    lock = ROOT / "skills-lock.json"
    for skill_dir in sorted((ROOT / "skills").glob("*/SKILL.md")):
        sl.lint_lock_version_sync(skill_dir.parent, lock)


def test_content_hash_matches_registry_lint_implementation() -> None:
    # skill_lint inlines content_hash so it stays importable as a standalone
    # script; this parity check guards the duplicate against silent drift.
    assert sl.LOCAL_LOCK_SOURCE == rl.LOCAL_LOCK_SOURCE
    for skill_dir in sorted((ROOT / "skills").glob("*/SKILL.md")):
        assert sl.content_hash(skill_dir.parent) == rl.content_hash(skill_dir.parent)


def test_frontmatter_version_extraction() -> None:
    assert sl._frontmatter_version({"metadata": {"version": "1.2.3"}}) == "1.2.3"
    assert sl._frontmatter_version({"metadata": {"version": 7}}) is None
    assert sl._frontmatter_version({"metadata": "scalar"}) is None
    assert sl._frontmatter_version({}) is None


def test_lock_version_sync_in_sync_passes(tmp_path: Path) -> None:
    skill = _versioned_skill(tmp_path, "doc-sync", "1.0.0")
    lock = _write_lock(
        tmp_path,
        {
            "doc-sync": {
                "source": rl.LOCAL_LOCK_SOURCE,
                "version": "1.0.0",
                "computedHash": rl.content_hash(skill),
            }
        },
    )
    # Accepts a SKILL.md file path too (covers the not-a-dir normalisation).
    sl.lint_lock_version_sync(skill / "SKILL.md", lock)


def test_lock_version_sync_body_changed_without_bump_fails(tmp_path: Path) -> None:
    skill = _versioned_skill(tmp_path, "doc-sync", "1.0.0")
    stale_hash = rl.content_hash(skill)
    (skill / "SKILL.md").write_text(
        "---\nname: doc-sync\nmetadata:\n  version: \"1.0.0\"\n---\nMUTATED BODY\n",
        encoding="utf-8",
    )
    lock = _write_lock(
        tmp_path,
        {"doc-sync": {"source": rl.LOCAL_LOCK_SOURCE, "version": "1.0.0", "computedHash": stale_hash}},
    )
    with pytest.raises(sl.SkillLintError) as excinfo:
        sl.lint_lock_version_sync(skill, lock)
    msg = str(excinfo.value)
    assert "metadata.version is still '1.0.0'" in msg
    assert "bump the version" in msg


def test_lock_version_sync_stale_lock_after_bump_fails(tmp_path: Path) -> None:
    skill = _versioned_skill(tmp_path, "doc-sync", "1.0.0")
    stale_hash = rl.content_hash(skill)
    # Author bumped the version (and thus changed the body) but did not refresh the lock.
    (skill / "SKILL.md").write_text(
        "---\nname: doc-sync\nmetadata:\n  version: \"1.1.0\"\n---\nbody\n",
        encoding="utf-8",
    )
    lock = _write_lock(
        tmp_path,
        {"doc-sync": {"source": rl.LOCAL_LOCK_SOURCE, "version": "1.0.0", "computedHash": stale_hash}},
    )
    with pytest.raises(sl.SkillLintError) as excinfo:
        sl.lint_lock_version_sync(skill, lock)
    msg = str(excinfo.value)
    assert "content hash drifted" in msg
    assert "locked version '1.0.0'" in msg
    assert "frontmatter version '1.1.0'" in msg


def test_lock_version_sync_skips_unlocked_and_external(tmp_path: Path) -> None:
    skill = _versioned_skill(tmp_path, "doc-sync", "1.0.0")
    (skill / "SKILL.md").write_text(
        "---\nname: doc-sync\nmetadata:\n  version: \"1.0.0\"\n---\nCHANGED\n",
        encoding="utf-8",
    )
    # Absent row -> ignored.
    lock = _write_lock(tmp_path, {"other": {"source": rl.LOCAL_LOCK_SOURCE}})
    sl.lint_lock_version_sync(skill, lock)
    # Bare-string row -> not a dict -> ignored.
    lock = _write_lock(tmp_path, {"doc-sync": "local-row"})
    sl.lint_lock_version_sync(skill, lock)
    # External source -> ignored even though hash differs.
    lock = _write_lock(
        tmp_path,
        {"doc-sync": {"source": "anthropics/skills", "computedHash": "0" * 64}},
    )
    sl.lint_lock_version_sync(skill, lock)


def test_lock_version_sync_no_locked_hash_is_ignored(tmp_path: Path) -> None:
    skill = _versioned_skill(tmp_path, "doc-sync", "1.0.0")
    lock = _write_lock(
        tmp_path, {"doc-sync": {"source": rl.LOCAL_LOCK_SOURCE, "version": "1.0.0"}}
    )
    sl.lint_lock_version_sync(skill, lock)


def test_lock_version_sync_load_errors_raise(tmp_path: Path) -> None:
    skill = _versioned_skill(tmp_path, "doc-sync", "1.0.0")

    with pytest.raises(sl.SkillLintError, match="missing skills-lock.json"):
        sl.lint_lock_version_sync(skill, tmp_path / "nope.json")

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(sl.SkillLintError, match="invalid JSON"):
        sl.lint_lock_version_sync(skill, bad)

    notmap = tmp_path / "notmap.json"
    notmap.write_text("[]", encoding="utf-8")
    with pytest.raises(sl.SkillLintError, match="missing skills mapping"):
        sl.lint_lock_version_sync(skill, notmap)
