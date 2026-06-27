#!/usr/bin/env python3
"""Validate exploratory mission SKILL.md structure (skill_lint mission contract)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.exploratory_missions import lint_exploratory_missions, list_exploratory_mission_dirs  # noqa: E402


def main() -> int:
    missions = list_exploratory_mission_dirs(ROOT)
    if not missions:
        print("validate-exploratory-missions: no missions found", file=sys.stderr)
        return 2
    errors, lines = lint_exploratory_missions(ROOT)
    for line in lines:
        print(line)
    print("")
    if errors:
        print(f"{errors} exploratory mission(s) failed validation.", file=sys.stderr)
        return 1
    print(f"All {len(missions)} exploratory missions passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())