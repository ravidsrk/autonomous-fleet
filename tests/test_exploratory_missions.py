"""Exploratory mission validation helper and banner checks."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GSTACK_SLUGS = ("product-framing", "browser-qa-fix", "security-cso-audit")
DESIGN_INTEGRATION_BANNER = (
    ROOT / "docs" / "exploratory" / "missions" / "design-integration" / "assets" / "banner.png"
)


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_list_exploratory_mission_dirs_includes_gstack_missions() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.exploratory_missions import list_exploratory_mission_dirs

    names = {p.name for p in list_exploratory_mission_dirs(ROOT)}
    for slug in GSTACK_SLUGS:
        assert slug in names


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
    for slug in GSTACK_SLUGS:
        assert f"exploratory/{slug}" in r.stdout


def test_gstack_banners_differ_from_design_integration() -> None:
    ref = _md5(DESIGN_INTEGRATION_BANNER)
    digests = {_md5(ROOT / "docs/exploratory/missions" / s / "assets" / "banner.png") for s in GSTACK_SLUGS}
    assert ref not in digests
    assert len(digests) == 3


@pytest.mark.parametrize("slug,label", [
    ("product-framing", "skills/product-framing"),
    ("browser-qa-fix", "skills/browser-qa-fix"),
    ("security-cso-audit", "skills/security-cso-audit"),
])
def test_banner_prompt_declares_skill_label(slug: str, label: str) -> None:
    prompt = (
        ROOT / "docs" / "exploratory/missions" / slug / "assets" / "banner-prompt.txt"
    ).read_text(encoding="utf-8")
    assert label in prompt


def test_lint_exploratory_missions_zero_errors() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.exploratory_missions import lint_exploratory_missions

    errors, lines = lint_exploratory_missions(ROOT)
    assert errors == 0
    assert any("exploratory/product-framing" in ln for ln in lines)


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