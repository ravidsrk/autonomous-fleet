"""Structural linter for autonomous-fleet SKILL.md files.

This linter enforces the parts of adapter and shipped-mission SKILL.md files
that are load-bearing for autonomous-fleet orchestration. It intentionally
matches headings by stable tokens instead of full heading text so authors can
revise explanatory wording without weakening the contract.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml

ADAPTER_COMPONENTS = frozenset({"adapter", "adapter-template"})

ADAPTER_REQUIRED_HEADINGS: tuple[tuple[str, str, str], ...] = (
    ("##", "PRECONDITIONS", "PRECONDITIONS"),
    ("###", "PLACE(kind)", "PLACE(kind)"),
    ("###", "SPAWN_WORKER", "SPAWN_WORKER"),
    ("###", "DISPATCH", "DISPATCH"),
    ("###", "WAIT", "WAIT"),
    ("###", "INSPECT", "INSPECT"),
    ("###", "WORKER_DONE", "WORKER_DONE"),
    ("###", "ASK / REPLY", "ASK / REPLY"),
    ("###", "OPEN_PR", "OPEN_PR"),
    ("###", "SYNC_TASK_STATE", "SYNC_TASK_STATE"),
    ("##|###", "GOAL", "GOAL"),
)
TEMPLATE_ONLY_HEADINGS: tuple[tuple[str, str, str], ...] = (
    ("##", "NON-NEGOTIABLES", "NON-NEGOTIABLES"),
)
MISSION_REQUIRED_HEADINGS: tuple[tuple[str, str, str], ...] = (
    ("##", "Required skills", "Required skills"),
    ("##", "Optional skills", "Optional skills"),
    ("##", "Worker skills", "Worker skills"),
    ("##", "Deferred missions", "Deferred missions"),
    ("##", "ROLE PIPELINE", "ROLE PIPELINE"),
)

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.S)
FLEET_OUTCOME_YAML_RE = re.compile(r"`?fleet-outcome`?\s+YAML", re.I)


class SkillLintError(AssertionError):
    """Raised when a SKILL.md fails structural linting."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def _skill_md_path(path: Path | str) -> Path:
    skill_path = Path(path)
    if skill_path.is_dir():
        skill_path = skill_path / "SKILL.md"
    if not skill_path.is_file():
        raise SkillLintError([f"{skill_path}: missing SKILL.md"])
    return skill_path


def _read_skill(path: Path | str) -> tuple[Path, str]:
    skill_path = _skill_md_path(path)
    return skill_path, skill_path.read_text(encoding="utf-8")


def _frontmatter(text: str, skill_path: Path) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise SkillLintError([f"{skill_path}: missing YAML frontmatter"])
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise SkillLintError([f"{skill_path}: invalid YAML frontmatter: {exc}"]) from exc
    if not isinstance(data, dict):
        raise SkillLintError([f"{skill_path}: YAML frontmatter must be a mapping"])
    return data


def _fleet_component(data: dict[str, Any]) -> str | None:
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    component = metadata.get("fleet-component")
    return component if isinstance(component, str) else None


def _has_heading(text: str, hashes: str, token: str) -> bool:
    pattern = re.compile(rf"^(?:{hashes})\s+.*{re.escape(token)}.*$", re.I | re.M)
    return pattern.search(text) is not None


def _missing_heading_errors(
    text: str,
    skill_path: Path,
    requirements: tuple[tuple[str, str, str], ...],
) -> list[str]:
    errors: list[str] = []
    for hashes, label, token in requirements:
        if not _has_heading(text, hashes, token):
            errors.append(f"{skill_path}: missing {hashes} heading containing {label!r}")
    return errors


def lint_adapter(path: Path | str) -> None:
    """Assert that an adapter SKILL.md has the required frontmatter and headings."""
    skill_path, text = _read_skill(path)
    data = _frontmatter(text, skill_path)

    errors: list[str] = []
    name = data.get("name")
    if name != skill_path.parent.name:
        errors.append(
            f"{skill_path}: frontmatter name must match directory {skill_path.parent.name!r}"
        )
    if not data.get("license"):
        errors.append(f"{skill_path}: missing frontmatter license")

    component = _fleet_component(data)
    if component not in ADAPTER_COMPONENTS:
        allowed = ", ".join(sorted(ADAPTER_COMPONENTS))
        errors.append(f"{skill_path}: metadata.fleet-component must be one of {allowed}")

    errors.extend(_missing_heading_errors(text, skill_path, ADAPTER_REQUIRED_HEADINGS))
    if component == "adapter-template":
        errors.extend(_missing_heading_errors(text, skill_path, TEMPLATE_ONLY_HEADINGS))

    if errors:
        raise SkillLintError(errors)


def lint_mission(path: Path | str) -> None:
    """Assert that a shipped mission SKILL.md has required orchestration sections."""
    skill_path, text = _read_skill(path)
    errors = _missing_heading_errors(text, skill_path, MISSION_REQUIRED_HEADINGS)
    if not FLEET_OUTCOME_YAML_RE.search(text):
        errors.append(f"{skill_path}: missing fleet-outcome YAML readiness reference")
    if errors:
        raise SkillLintError(errors)


def lint_skill(path: Path | str) -> None:
    """Lint adapters and missions; other autonomous-fleet skill types are ignored."""
    skill_path, text = _read_skill(path)
    data = _frontmatter(text, skill_path)
    component = _fleet_component(data)
    if component in ADAPTER_COMPONENTS:
        lint_adapter(skill_path)
    elif component == "mission":
        lint_mission(skill_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint autonomous-fleet SKILL.md structure.")
    parser.add_argument("paths", nargs="+", type=Path, help="Skill directories or SKILL.md files.")
    args = parser.parse_args(argv)

    errors: list[str] = []
    for path in args.paths:
        try:
            lint_skill(path)
        except SkillLintError as exc:
            errors.extend(exc.errors)

    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
