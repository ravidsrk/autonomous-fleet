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
