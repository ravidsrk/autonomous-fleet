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


def lint_exploratory_missions(repo_root: Path, skill_lint: Path | None = None) -> tuple[int, list[str]]:
    """Run skill_lint.py on every exploratory mission. Returns (error_count, lines)."""
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
        if proc.returncode != 0:
            errors += 1
            lines.append(f"FAIL exploratory/{name}: {proc.stderr.strip() or proc.stdout.strip()}")
        else:
            lines.append(f"OK   exploratory/{name}")
    return errors, lines