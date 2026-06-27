"""Guard README.md metrics against pytest/skill-count drift."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


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


def test_version_file_matches_readme_badge() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    readme = README.read_text(encoding="utf-8")
    assert f"version-{version}" in readme, f"README badge must show version-{version}"
    assert f"Version {version}" in readme


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


def test_readme_lists_twelve_skills_in_layout() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "3 shipped missions" in readme
    assert "docs/exploratory/missions/" in readme
    assert (
        "15 exploratory" in readme
        or "12 demoted missions" in readme
        or "12 exploratory" in readme
    )