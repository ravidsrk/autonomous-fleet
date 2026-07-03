"""List and validate exploratory mission SKILL.md trees under docs/exploratory/missions/."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def exploratory_missions_root(repo_root: Path) -> Path:
    return repo_root / "docs" / "exploratory" / "missions"


def list_exploratory_mission_dirs(repo_root: Path) -> list[Path]:
    root = exploratory_missions_root(repo_root)
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


EXPLORATORY_FLAG = "status: exploratory"
EXPLORATORY_BANNER = "> **Status: exploratory.**"


def missing_exploratory_markers(mission_dir: Path) -> list[str]:
    """Both load-bearing exploratory markers, per docs/exploratory/missions/README.md.

    The frontmatter flag is what skill-discovery layers read; the banner is
    what humans read. Three demoted missions shipped with neither and were
    indistinguishable from first-class missions to frontmatter scanners
    (issue #95) — this makes the README's 'load-bearing' claim enforced.
    """
    try:
        text = (mission_dir / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return ["SKILL.md unreadable"]
    missing: list[str] = []
    end = text.find("\n---", 3) if text.startswith("---") else -1
    frontmatter = text[: end + 4] if end >= 0 else ""
    if EXPLORATORY_FLAG not in frontmatter:
        missing.append(f"frontmatter missing '{EXPLORATORY_FLAG}'")
    if EXPLORATORY_BANNER not in text:
        missing.append(f"body missing banner '{EXPLORATORY_BANNER}'")
    return missing


def lint_exploratory_missions(repo_root: Path, skill_lint: Path | None = None) -> tuple[int, list[str]]:
    """Run skill_lint.py + exploratory-marker checks on every exploratory mission."""
    lint = skill_lint or repo_root / "scripts" / "lib" / "skill_lint.py"
    lines: list[str] = []
    errors = 0
    for mission_dir in list_exploratory_mission_dirs(repo_root):
        name = mission_dir.name
        proc = subprocess.run(
            [sys.executable, str(lint), str(mission_dir)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        problems: list[str] = []
        if proc.returncode != 0:
            problems.append(proc.stderr.strip() or proc.stdout.strip())
        problems.extend(missing_exploratory_markers(mission_dir))
        if problems:
            errors += 1
            lines.append(f"FAIL exploratory/{name}: {'; '.join(problems)}")
        else:
            lines.append(f"OK   exploratory/{name}")
    return errors, lines