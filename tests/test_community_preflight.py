"""Tests for community skill recommends preflight."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.community_preflight import (  # noqa: E402
    GSTACK_MISSION_SLUGS,
    check,
    install_hint_line,
    load_recommends,
    mission_skill_path,
    probe_skill_installed,
    recommendation_line,
    resolve_probe_home,
)


def test_gstack_slugs_count() -> None:
    assert len(GSTACK_MISSION_SLUGS) == 6


@pytest.mark.parametrize("slug", sorted(GSTACK_MISSION_SLUGS))
def test_load_recommends_from_gstack_missions(slug: str) -> None:
    mission_dir = ROOT / "docs" / "exploratory" / "missions" / slug
    recommends = load_recommends(mission_dir)
    assert recommends is not None
    assert recommends.mode == "warn"
    assert recommends.bundle
    assert recommends.skills


def test_check_warn_mode_returns_warnings_not_failures(tmp_path: Path) -> None:
    from lib.community_preflight import CommunityRecommends

    recommends = CommunityRecommends(
        bundle="gstack-browser",
        skills=("browse", "qa"),
        mode="warn",
    )
    result = check(recommends, home=str(tmp_path))
    assert result.warnings
    assert not result.failures
    assert "install-community.sh gstack-browser" in result.warnings[0]


def test_check_fail_mode_returns_failures(tmp_path: Path) -> None:
    from lib.community_preflight import CommunityRecommends

    recommends = CommunityRecommends(
        bundle="gstack-framing",
        skills=("office-hours",),
        mode="fail",
    )
    result = check(recommends, home=str(tmp_path))
    assert result.failures
    assert not result.warnings


def test_probe_skill_installed_finds_skill_under_home(tmp_path: Path) -> None:
    skill_root = tmp_path / ".claude" / "skills" / "gstack" / "qa"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("---\nname: qa\n---\n", encoding="utf-8")
    assert probe_skill_installed("qa", home=str(tmp_path))


def test_mission_skill_path_resolves_exploratory() -> None:
    path = mission_skill_path(ROOT, "product-framing")
    assert path is not None
    assert path.name == "product-framing"
    assert (path / "SKILL.md").is_file()


def test_product_framing_load_and_check_integration() -> None:
    mission_dir = mission_skill_path(ROOT, "product-framing")
    assert mission_dir is not None
    recommends = load_recommends(mission_dir)
    assert recommends is not None
    result = check(recommends, home="/nonexistent-empty-home-for-test")
    assert result.mode == "warn"
    assert result.warnings
    assert "install-community.sh" in result.warnings[0]
    assert result.recommended_line
    assert "recommended community bundle" in result.recommended_line
    assert result.install_hint == install_hint_line(recommends.bundle)


def test_skill_md_path_errors(tmp_path: Path) -> None:
    from lib.community_preflight import _skill_md_path

    with pytest.raises(ValueError, match="missing SKILL.md"):
        _skill_md_path(tmp_path / "missing")


def test_parse_recommends_mapping_validation() -> None:
    from lib.community_preflight import _parse_recommends_mapping

    with pytest.raises(ValueError, match="non-empty bundle"):
        _parse_recommends_mapping({}, "src")
    with pytest.raises(ValueError, match="non-empty skills"):
        _parse_recommends_mapping({"bundle": "x"}, "src")
    with pytest.raises(ValueError, match="skills list is empty"):
        _parse_recommends_mapping({"bundle": "x", "skills": ["  "]}, "src")
    with pytest.raises(ValueError, match="mode must be warn"):
        _parse_recommends_mapping({"bundle": "x", "skills": ["a"], "mode": "bogus"}, "src")


def test_load_recommends_frontmatter_and_off_mode(tmp_path: Path) -> None:
    mission = tmp_path / "demo"
    mission.mkdir()
    (mission / "SKILL.md").write_text(
        "---\nname: demo\nmetadata:\n  community-recommends:\n"
        "    bundle: gstack-browser\n    skills: [browse]\n    mode: off\n---\n",
        encoding="utf-8",
    )
    recommends = load_recommends(mission)
    assert recommends is not None
    assert recommends.mode == "off"
    result = check(recommends)
    assert result.bundle is None


def test_load_recommends_invalid_block(tmp_path: Path) -> None:
    mission = tmp_path / "demo"
    mission.mkdir()
    (mission / "SKILL.md").write_text(
        "---\nname: demo\n---\n```yaml community-recommends\n- scalar\n```\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be a mapping"):
        load_recommends(mission)


def test_has_recommends_block_and_probe_helpers(tmp_path: Path) -> None:
    from lib.community_preflight import has_recommends_block, skill_probe_roots

    assert not has_recommends_block("no block")
    assert has_recommends_block("```yaml community-recommends\nbundle: x\nskills: [a]\n```")
    assert skill_probe_roots(str(tmp_path))
    assert not probe_skill_installed("", home=str(tmp_path))
    extra = tmp_path / "custom" / "qa"
    extra.mkdir(parents=True)
    (extra / "SKILL.md").write_text("---\nname: qa\n---\n", encoding="utf-8")
    assert probe_skill_installed("qa", home=str(tmp_path), extra_roots=[extra])


def test_check_all_skills_present_returns_empty_warnings(tmp_path: Path) -> None:
    from lib.community_preflight import CommunityRecommends

    root = tmp_path / ".claude" / "skills" / "gstack" / "browse"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text("---\nname: browse\n---\n", encoding="utf-8")
    recommends = CommunityRecommends(bundle="gstack-browser", skills=("browse",), mode="warn")
    result = check(recommends, home=str(tmp_path))
    assert not result.warnings
    assert not result.failures
    assert result.recommended_line == recommendation_line(recommends)
    assert result.install_hint == install_hint_line("gstack-browser")


def test_resolve_probe_home_reads_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("COMMUNITY_PROBE_HOME", raising=False)
    assert resolve_probe_home() is None
    monkeypatch.setenv("COMMUNITY_PROBE_HOME", str(tmp_path))
    assert resolve_probe_home() == str(tmp_path)
    assert resolve_probe_home("/explicit") == "/explicit"


def test_load_recommends_no_frontmatter_returns_none(tmp_path: Path) -> None:
    mission = tmp_path / "no-fm"
    mission.mkdir()
    (mission / "SKILL.md").write_text("# body only\n", encoding="utf-8")
    assert load_recommends(mission) is None


def test_load_recommends_list_frontmatter_returns_none(tmp_path: Path) -> None:
    mission = tmp_path / "list-fm"
    mission.mkdir()
    (mission / "SKILL.md").write_text("---\n- only\n- list\n---\n\n# body\n", encoding="utf-8")
    assert load_recommends(mission) is None


def test_load_recommends_returns_none_without_metadata_block(tmp_path: Path) -> None:
    mission = tmp_path / "plain"
    mission.mkdir()
    (mission / "SKILL.md").write_text("---\nname: plain\n---\nbody\n", encoding="utf-8")
    assert load_recommends(mission) is None

    (mission / "SKILL.md").write_text("---\nscalar\n---\n", encoding="utf-8")
    assert load_recommends(mission) is None

    (mission / "SKILL.md").write_text("---\n- list\n---\nbody\n", encoding="utf-8")
    assert load_recommends(mission) is None

    (mission / "SKILL.md").write_text(
        "---\nname: plain\nmetadata: scalar\n---\n",
        encoding="utf-8",
    )
    assert load_recommends(mission) is None

    (mission / "SKILL.md").write_text(
        "---\nname: plain\nmetadata:\n  community-recommends: scalar\n---\n",
        encoding="utf-8",
    )
    assert load_recommends(mission) is None


def test_mission_skill_path_shipped(tmp_path: Path) -> None:
    shipped = tmp_path / "skills" / "doc-sync"
    shipped.mkdir(parents=True)
    (shipped / "SKILL.md").write_text("---\nname: doc-sync\n---\n", encoding="utf-8")
    assert mission_skill_path(tmp_path, "doc-sync") == shipped
    assert mission_skill_path(tmp_path, "missing") is None