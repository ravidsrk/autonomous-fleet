"""Guard README.md metrics against pytest/skill-count drift."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
MISSIONS_DIR = ROOT / "docs" / "exploratory" / "missions"

# Numbers we treat as plausible exploratory-mission counts when scanning the
# README for an internal contradiction. Kept small and explicit so a stray
# unrelated number (e.g. "Node.js >= 18") in a *different* context is never
# matched: we only ever look at "<N> exploratory" / "<N> ... missions" phrasings.
_CANDIDATE_COUNTS = range(2, 100)


def _pytest_collect_count() -> int:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    m = re.search(r"(\d+) tests collected", r.stdout)
    assert m, f"could not parse pytest collect output: {r.stdout!r}"
    return int(m.group(1))


def _exploratory_mission_count() -> int:
    """Source of truth: number of ACTIVE mission subdirectories on disk.

    ``archive/`` holds parked missions (see its README) and is not a mission,
    so it is excluded from the canonical count.
    """
    return sum(
        1 for p in MISSIONS_DIR.iterdir() if p.is_dir() and p.name != "archive"
    )


def _mission_counts_stated_in_readme(readme: str) -> set[int]:
    """Every integer the README attaches to an exploratory-mission phrasing.

    Matches both "N exploratory ..." and "N (more) mission(s)" so the test can
    catch an internal 12-vs-18 contradiction regardless of which phrasing drifts.
    Restricted to mission contexts so unrelated numbers (versions, Node.js
    requirements, test counts) are ignored.
    """
    found: set[int] = set()
    patterns = (
        r"(\d+)\s+exploratory",
        r"(\d+)\s+(?:more\s+)?missions?\b",
    )
    for pat in patterns:
        for m in re.finditer(pat, readme):
            value = int(m.group(1))
            if value in _CANDIDATE_COUNTS:
                found.add(value)
    return found


def _project_version_sources() -> dict[str, str]:
    """version as declared by each independent source of truth."""
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert m, "pyproject.toml has no [project] version line"
    pyproject_version = m.group(1)

    plugin = (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    m = re.search(r'"version"\s*:\s*"([^"]+)"', plugin)
    assert m, "plugin.json has no version field"
    plugin_version = m.group(1)

    return {
        "VERSION": version,
        "pyproject.toml": pyproject_version,
        "plugin.json": plugin_version,
    }


def test_version_is_consistent_across_all_sources() -> None:
    """VERSION == README badge == pyproject.toml == plugin.json (all equal)."""
    sources = _project_version_sources()
    version = sources["VERSION"]
    readme = README.read_text(encoding="utf-8")

    # README badge carries the version twice: the shields path and the alt text.
    assert f"version-{version}" in readme, f"README badge must show version-{version}"
    assert f"Version {version}" in readme, f"README must show 'Version {version}'"

    for name, value in sources.items():
        assert value == version, (
            f"{name} version {value!r} != VERSION {version!r}; "
            "all version sources must agree"
        )


def test_readme_exploratory_count_matches_filesystem() -> None:
    """README states exactly the on-disk mission count and no other count."""
    expected = _exploratory_mission_count()
    readme = README.read_text(encoding="utf-8")

    assert f"{expected} exploratory" in readme, (
        f"README must state '{expected} exploratory' (mission subdirs on disk)"
    )

    stated = _mission_counts_stated_in_readme(readme)
    assert expected in stated, (
        f"README does not attach the on-disk count {expected} to any mission phrasing; "
        f"found {sorted(stated)}"
    )
    contradictions = stated - {expected}
    assert not contradictions, (
        f"README states conflicting exploratory-mission counts {sorted(contradictions)} "
        f"alongside the canonical {expected}"
    )


def test_readme_test_count_matches_pytest() -> None:
    count = _pytest_collect_count()
    readme = README.read_text(encoding="utf-8")
    assert f"{count} tests" in readme, f"README must mention {count} tests"


def test_readme_test_file_count_matches_tree() -> None:
    file_count = len(list((ROOT / "tests").glob("test_*.py")))
    readme = README.read_text(encoding="utf-8")
    assert f"{file_count} test files" in readme, (
        f"README must mention {file_count} test files"
    )


def test_readme_lists_shipped_and_exploratory_layout() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "3 shipped missions" in readme
    assert "docs/exploratory/missions/" in readme
