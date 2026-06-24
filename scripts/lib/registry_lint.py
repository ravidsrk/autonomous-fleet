"""Consistency checks for the fleet mission registry and shipped skill catalogs."""

from __future__ import annotations

import json
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Mapping

from .fleet_registry import MISSIONS

LOCAL_LOCK_SOURCE = "ravidsrk/autonomous-fleet"
_MISSION_COMPONENT_RE = re.compile(r"fleet-component:\s*[\"']?mission[\"']?")


def shipped_missions(
    missions: Mapping[str, Mapping[str, Any]] = MISSIONS,
) -> dict[str, Mapping[str, Any]]:
    return {
        mission_id: row
        for mission_id, row in missions.items()
        if row.get("shipped") is True
    }


def _skill_dirs_on_disk(root: Path) -> set[str]:
    return {path.parent.name for path in (root / "skills").glob("*/SKILL.md")}


def _mission_skill_dirs_on_disk(root: Path) -> set[str]:
    dirs: set[str] = set()
    for skill_path in sorted((root / "skills").glob("*/SKILL.md")):
        text = skill_path.read_text(encoding="utf-8")
        if _MISSION_COMPONENT_RE.search(text):
            dirs.add(skill_path.parent.name)
    return dirs


def lint_shipped_mission_dirs(
    root: Path, missions: Mapping[str, Mapping[str, Any]] = MISSIONS
) -> list[str]:
    errors: list[str] = []
    shipped = shipped_missions(missions)
    shipped_dirs = {str(row["skill_dir"]) for row in shipped.values()}

    for mission_id, row in shipped.items():
        skill_dir = str(row["skill_dir"])
        skill_file = root / "skills" / skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(
                f"{mission_id}: shipped:true points to missing skills/{skill_dir}/SKILL.md"
            )

    for skill_dir in sorted(_mission_skill_dirs_on_disk(root) - shipped_dirs):
        errors.append(
            f"skills/{skill_dir}/SKILL.md is a mission skill but has no shipped:true registry row"
        )

    return errors


def lint_catalog_mentions(
    root: Path, missions: Mapping[str, Mapping[str, Any]] = MISSIONS
) -> list[str]:
    errors: list[str] = []
    catalogs = {
        "README.md": root / "README.md",
        "skills/autonomous-fleet/SKILL.md": root / "skills" / "autonomous-fleet" / "SKILL.md",
    }

    for label, path in catalogs.items():
        if not path.is_file():
            errors.append(f"{label}: missing catalog file")
            continue
        text = path.read_text(encoding="utf-8")
        for mission_id in sorted(shipped_missions(missions)):
            if mission_id not in text:
                errors.append(f"{label}: missing shipped mission {mission_id}")

    return errors


def _load_lock_skills(root: Path) -> tuple[dict[str, Any], list[str]]:
    lock_path = root / "skills-lock.json"
    if not lock_path.is_file():
        return {}, ["skills-lock.json: missing"]
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        return {}, [f"skills-lock.json: invalid JSON: {exc.msg}"]
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, dict):
        return {}, ["skills-lock.json: missing skills mapping"]
    return skills, []


def _local_lock_skill_dirs(skills: Mapping[str, Any]) -> set[str]:
    dirs: set[str] = set()
    for name, row in skills.items():
        source = row.get("source") if isinstance(row, dict) else None
        if source in (None, LOCAL_LOCK_SOURCE):
            dirs.add(name)
    return dirs


def lint_skills_lock(root: Path) -> list[str]:
    skills, errors = _load_lock_skills(root)
    if errors:
        return errors

    expected = _skill_dirs_on_disk(root)
    actual = _local_lock_skill_dirs(skills)
    missing = sorted(expected - actual)
    stale = sorted(actual - expected)

    if missing:
        errors.append(f"skills-lock.json: missing shipped skill dirs: {', '.join(missing)}")
    if stale:
        errors.append(f"skills-lock.json: stale skill dirs not on disk: {', '.join(stale)}")

    return errors


def lint_registry(
    root: Path, missions: Mapping[str, Mapping[str, Any]] = MISSIONS
) -> list[str]:
    return (
        lint_shipped_mission_dirs(root, missions)
        + lint_catalog_mentions(root, missions)
        + lint_skills_lock(root)
    )
