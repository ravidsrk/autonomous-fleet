"""Exploratory mission validation helper and banner checks."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARKED_SLUGS = (
    "release-document",
    "devex-audit",
    "landing-page-convergence",
    "product-framing",
    "security-cso-audit",
    "legacy-rebuild",
)
ACTIVE_GSTACK_SLUGS = ("browser-qa-fix", "incident-investigate")
ARCHIVED_GSTACK_SLUGS = (
    "product-framing",
    "security-cso-audit",
    "devex-audit",
    "release-document",
)
ALL_GSTACK_SLUGS = ARCHIVED_GSTACK_SLUGS + ACTIVE_GSTACK_SLUGS
DESIGN_INTEGRATION_BANNER = (
    ROOT / "docs" / "exploratory" / "missions" / "design-integration" / "assets" / "banner.png"
)


def _mission_dir(slug: str) -> Path:
    base = ROOT / "docs" / "exploratory" / "missions"
    return base / "archive" / slug if slug in PARKED_SLUGS else base / slug


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_list_exploratory_mission_dirs_splits_active_from_archive() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.exploratory_missions import (
        list_archived_mission_dirs,
        list_exploratory_mission_dirs,
    )

    names = {p.name for p in list_exploratory_mission_dirs(ROOT)}
    archived = {p.name for p in list_archived_mission_dirs(ROOT)}
    for slug in ACTIVE_GSTACK_SLUGS:
        assert slug in names
    assert names.isdisjoint(PARKED_SLUGS)
    assert archived == set(PARKED_SLUGS)


def test_validate_exploratory_missions_cli_exits_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_exploratory_missions.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "exploratory missions passed validation" in r.stdout
    for slug in ACTIVE_GSTACK_SLUGS:
        assert f"exploratory/{slug}" in r.stdout
    for slug in PARKED_SLUGS:
        assert f"exploratory/{slug}" not in r.stdout


def test_gstack_banners_differ_from_design_integration() -> None:
    ref = _md5(DESIGN_INTEGRATION_BANNER)
    digests = {_md5(_mission_dir(s) / "assets" / "banner.png") for s in ALL_GSTACK_SLUGS}
    assert ref not in digests
    assert len(digests) == len(ALL_GSTACK_SLUGS)


def test_gstack_banners_are_png_1200x600() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import png_dimensions

    for slug in ALL_GSTACK_SLUGS:
        path = _mission_dir(slug) / "assets" / "banner.png"
        assert path.read_bytes()[:4] == b"\x89PNG", f"{slug}: expected PNG magic"
        assert png_dimensions(path) == (1200, 600), slug


def test_gstack_new_mission_banners_are_schematic_not_placeholders() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import (
        MIN_BANNER_BYTES,
        banner_has_label_ink,
        is_placeholder_banner,
        png_unique_color_count,
    )

    new_slugs = ("devex-audit", "release-document", "incident-investigate")
    for slug in new_slugs:
        path = _mission_dir(slug) / "assets" / "banner.png"
        assert path.stat().st_size >= MIN_BANNER_BYTES, f"{slug}: banner too small"
        assert png_unique_color_count(path, sample=4) >= 10, f"{slug}: too few colors"
        assert not is_placeholder_banner(path), f"{slug}: still placeholder"
        assert banner_has_label_ink(path), f"{slug}: missing top-left label ink"


def test_sniff_and_normalize_banner_script() -> None:
    sniff = ROOT / "scripts" / "banner" / "sniff_and_normalize_banner.sh"
    assert sniff.is_file()
    # Drive real entry point on a shipped PNG reference (already valid PNG).
    ref = DESIGN_INTEGRATION_BANNER
    tmp_out = ROOT / "tests" / "_banner_sniff_tmp.png"
    try:
        r = subprocess.run(
            [str(sniff), str(ref), str(tmp_out)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, r.stderr
        assert "PNG" in r.stderr
        assert "xxd" not in r.stderr
        assert tmp_out.read_bytes()[:4] == b"\x89PNG"
    finally:
        if tmp_out.exists():
            tmp_out.unlink()


def test_sniff_script_uses_python_magic_probe_not_xxd() -> None:
    sniff = ROOT / "scripts" / "banner" / "sniff_and_normalize_banner.sh"
    text = sniff.read_text(encoding="utf-8")
    assert "xxd" not in text
    assert "png_banner.py" in text
    assert 'magic "$1"' in text or "magic \"$1\"" in text


@pytest.mark.parametrize("slug", ALL_GSTACK_SLUGS)
def test_banner_prompt_declares_skill_label(slug: str) -> None:
    prompt = (_mission_dir(slug) / "assets" / "banner-prompt.txt").read_text(
        encoding="utf-8"
    )
    assert f"skills/{slug}" in prompt


def test_lint_exploratory_missions_zero_errors() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.exploratory_missions import lint_exploratory_missions

    errors, lines = lint_exploratory_missions(ROOT)
    assert errors == 0
    assert any("exploratory/browser-qa-fix" in ln for ln in lines)
    assert not any("exploratory/product-framing" in ln for ln in lines)


def test_validate_exploratory_missions_main_import() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import validate_exploratory_missions as mod

    assert mod.main() == 0


def test_exploratory_missions_empty_root(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.exploratory_missions import list_exploratory_mission_dirs

    assert list_exploratory_mission_dirs(tmp_path) == []


def test_validate_exploratory_missions_no_missions(tmp_path: Path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import validate_exploratory_missions as mod

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.main() == 2


def test_validate_exploratory_missions_errors(monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import validate_exploratory_missions as mod

    monkeypatch.setattr(mod, "lint_exploratory_missions", lambda _r: (1, ["FAIL exploratory/x: bad"]))
    assert mod.main() == 1


def test_lint_exploratory_missions_failure(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.exploratory_missions import lint_exploratory_missions

    missions = tmp_path / "docs" / "exploratory" / "missions" / "bad-mission"
    missions.mkdir(parents=True)
    (missions / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
    fake_lint = tmp_path / "fake_lint.py"
    fake_lint.write_text("import sys; sys.exit(1)\n", encoding="utf-8")
    errors, lines = lint_exploratory_missions(tmp_path, skill_lint=fake_lint)
    assert errors == 1
    assert lines[0].startswith("FAIL exploratory/bad-mission")


def test_validate_exploratory_missions_dunder_main() -> None:
    import runpy

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(
            str(ROOT / "scripts" / "validate_exploratory_missions.py"),
            run_name="__main__",
        )
    assert exc.value.code == 0

# --- exploratory markers are enforced, not advisory (issue #95) -------------


def test_all_exploratory_missions_carry_both_markers() -> None:
    from lib.exploratory_missions import (
        list_exploratory_mission_dirs,
        missing_exploratory_markers,
    )

    for mission_dir in list_exploratory_mission_dirs(ROOT):
        assert missing_exploratory_markers(mission_dir) == [], mission_dir.name


def test_archived_missions_still_pass_lint() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.exploratory_missions import (
        list_archived_mission_dirs,
        missing_exploratory_markers,
    )
    from lib.skill_lint import lint_mission

    for mission_dir in list_archived_mission_dirs(ROOT):
        assert missing_exploratory_markers(mission_dir) == [], mission_dir.name
        lint_mission(mission_dir)


def test_missing_flag_and_banner_detected(tmp_path) -> None:
    from lib.exploratory_missions import missing_exploratory_markers

    mission = tmp_path / "demo-mission"
    mission.mkdir()
    (mission / "SKILL.md").write_text(
        "---\nname: demo-mission\nmetadata:\n  version: \"1.0.0\"\n---\n\n# demo\n",
        encoding="utf-8",
    )
    missing = missing_exploratory_markers(mission)
    assert any("status: exploratory" in m for m in missing)
    assert any("banner" in m for m in missing)


def test_flag_in_body_does_not_satisfy_frontmatter_requirement(tmp_path) -> None:
    """The flag must be IN the frontmatter (what discovery layers parse), not
    merely mentioned in prose."""
    from lib.exploratory_missions import missing_exploratory_markers

    mission = tmp_path / "demo-mission"
    mission.mkdir()
    (mission / "SKILL.md").write_text(
        "---\nname: demo-mission\n---\n\n> **Status: exploratory.** banner ok\n\n"
        "prose mentioning status: exploratory does not count\n",
        encoding="utf-8",
    )
    missing = missing_exploratory_markers(mission)
    assert any("frontmatter" in m for m in missing)
    assert not any("banner" in m for m in missing)


def test_unreadable_skill_md_reported(tmp_path) -> None:
    from lib.exploratory_missions import missing_exploratory_markers

    mission = tmp_path / "demo-mission"
    mission.mkdir()
    (mission / "SKILL.md").mkdir()  # read_text -> IsADirectoryError (OSError)
    assert missing_exploratory_markers(mission) == ["SKILL.md unreadable"]


def test_lint_fails_mission_missing_markers(tmp_path) -> None:
    """End-to-end through lint_exploratory_missions: a marker-less mission FAILs
    even when skill_lint's structural checks pass."""
    import shutil
    from lib.exploratory_missions import lint_exploratory_missions

    repo = tmp_path / "repo"
    dest = repo / "docs" / "exploratory" / "missions" / "bug-batch"
    dest.parent.mkdir(parents=True)
    shutil.copytree(ROOT / "docs" / "exploratory" / "missions" / "bug-batch", dest)
    text = (dest / "SKILL.md").read_text(encoding="utf-8")
    text = text.replace("status: exploratory\n", "").replace("> **Status: exploratory.**", "> note:")
    (dest / "SKILL.md").write_text(text, encoding="utf-8")
    errors, lines = lint_exploratory_missions(repo)
    assert errors == 1
    assert any("FAIL exploratory/bug-batch" in line and "frontmatter" in line for line in lines)


def test_malformed_yaml_frontmatter_reported_as_missing_flag(tmp_path) -> None:
    """Covers the yaml.YAMLError branch: unparseable frontmatter cannot carry
    the flag, so it must report the frontmatter marker as missing."""
    from lib.exploratory_missions import missing_exploratory_markers

    mission = tmp_path / "demo-mission"
    mission.mkdir()
    (mission / "SKILL.md").write_text(
        "---\nname: [unclosed\n---\n\n> **Status: exploratory.** banner ok\n",
        encoding="utf-8",
    )
    missing = missing_exploratory_markers(mission)
    assert any("frontmatter" in m for m in missing)
