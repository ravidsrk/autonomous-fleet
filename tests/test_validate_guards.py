"""Guard tests for validators (H2a, H2b)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE_OUTCOME = ROOT / "scripts" / "validate-fleet-outcome.sh"
VALIDATE_SKILLS = ROOT / "scripts" / "validate-skills.sh"


def test_validate_fleet_outcome_named_missing_path_fails():
    """H2a: an explicitly-named missing path must fail (non-zero exit)."""
    r = subprocess.run(
        [str(VALIDATE_OUTCOME), "/does/not/exist/foo.md"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0, (r.stdout, r.stderr)


def test_validate_skills_missing_creator_fails():
    """H2b: validator absent + no opt-out → exit non-zero.

    Forces the absent path via SKILL_CREATOR_DIR so the test is deterministic
    whether or not skill-creator is installed (CI installs it; local does not).
    """
    env = os.environ.copy()
    env.pop("VALIDATE_SKILLS_OPTIONAL", None)
    env["SKILL_CREATOR_DIR"] = "/nonexistent/skill-creator"
    r = subprocess.run(
        [str(VALIDATE_SKILLS)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert r.returncode != 0, (r.stdout, r.stderr)


def test_validate_skills_optional_flag_skips():
    """H2b: VALIDATE_SKILLS_OPTIONAL=1 preserves WARN + exit 0 even when the validator is absent."""
    env = os.environ.copy()
    env["VALIDATE_SKILLS_OPTIONAL"] = "1"
    env["SKILL_CREATOR_DIR"] = "/nonexistent/skill-creator"
    r = subprocess.run(
        [str(VALIDATE_SKILLS)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
