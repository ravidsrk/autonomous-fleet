"""Structural linter for autonomous-fleet SKILL.md files.

This linter enforces the parts of adapter and shipped-mission SKILL.md files
that are load-bearing for autonomous-fleet orchestration. It intentionally
matches headings by stable tokens instead of full heading text so authors can
revise explanatory wording without weakening the contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Sequence

import yaml

# Source slug marking a lock row as fleet-owned (vendored from this repo). Kept in
# sync with ``registry_lint.LOCAL_LOCK_SOURCE`` by a test; duplicated rather than
# imported because this module is also run as a standalone script
# (``python3 scripts/lib/skill_lint.py <path>``), where package-relative imports of
# sibling lib modules are unavailable.
LOCAL_LOCK_SOURCE = "ravidsrk/autonomous-fleet"

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from lib.community_preflight import GSTACK_MISSION_SLUGS, has_recommends_block, load_recommends  # noqa: E402

ADAPTER_COMPONENTS = frozenset({"adapter", "adapter-template"})


def content_hash(skill_dir: Path) -> str:
    """Deterministic sha256 over a skill directory's tracked content.

    Byte-for-byte identical to ``registry_lint.content_hash`` (a parity test
    guards the two against drift); inlined so this module stays importable when
    executed as a standalone script.
    """
    digest = hashlib.sha256()
    files = sorted(p for p in skill_dir.rglob("*") if p.is_file())
    for path in files:
        rel = path.relative_to(skill_dir).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()

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


def _frontmatter_version(data: dict[str, Any]) -> str | None:
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    version = metadata.get("version")
    return version if isinstance(version, str) else None


def _load_lock_rows(lock_path: Path) -> dict[str, Any]:
    if not lock_path.is_file():
        raise SkillLintError([f"{lock_path}: missing skills-lock.json"])
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise SkillLintError([f"{lock_path}: invalid JSON: {exc.msg}"]) from exc
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, dict):
        raise SkillLintError([f"{lock_path}: missing skills mapping"])
    return skills


def lint_lock_version_sync(skill_dir: Path | str, lock_path: Path | str) -> None:
    """Flag a skill whose body changed (content hash drifted from the lock) without a version bump.

    The lock records, per local skill, the content hash AND the frontmatter
    ``metadata.version`` captured when the lock was last refreshed. If the skill
    body has since changed, :func:`content_hash` no longer matches the locked
    hash. When that happens this rule fails:

    * if ``metadata.version`` still equals the version recorded in the lock, the
      body moved silently under a stale version — the author must bump it; or
    * if the version *was* bumped, the lock itself is stale and must be
      refreshed so the recorded hash/version pair matches disk again.

    Either way the lock and the shipped body are forced to move together, so a
    content change can never slip out under an unchanged version undetected.
    Skills absent from the lock (or external, non-local rows) are ignored.
    """
    skill_path = Path(skill_dir)
    if not skill_path.is_dir():
        skill_path = skill_path.parent
    name = skill_path.name

    rows = _load_lock_rows(Path(lock_path))
    row = rows.get(name)
    if not isinstance(row, dict):
        return
    if row.get("source") not in (None, LOCAL_LOCK_SOURCE):
        return

    _, text = _read_skill(skill_path)
    data = _frontmatter(text, skill_path / "SKILL.md")
    fm_version = _frontmatter_version(data)

    locked_hash = row.get("computedHash")
    locked_version = row.get("version")
    actual_hash = content_hash(skill_path)
    if not isinstance(locked_hash, str) or actual_hash == locked_hash:
        return

    if isinstance(locked_version, str) and fm_version == locked_version:
        raise SkillLintError(
            [
                f"{skill_path}: content changed (hash drifted from skills-lock.json) but "
                f"metadata.version is still {fm_version!r}; bump the version and refresh the lock"
            ]
        )
    raise SkillLintError(
        [
            f"{skill_path}: content hash drifted from skills-lock.json; refresh the lock "
            f"(locked version {locked_version!r}, frontmatter version {fm_version!r})"
        ]
    )


def lint_gstack_mission(path: Path | str) -> None:
    """Lint gstack-derived exploratory missions (mission contract + community-recommends)."""
    skill_path, text = _read_skill(path)
    lint_mission(skill_path)
    slug = skill_path.parent.name
    if slug not in GSTACK_MISSION_SLUGS:
        return
    if not has_recommends_block(text):
        raise SkillLintError([f"{skill_path}: missing fenced community-recommends block"])
    try:
        recommends = load_recommends(skill_path.parent)
    except ValueError as exc:
        raise SkillLintError([str(exc)]) from exc
    assert recommends is not None  # fenced block present; load_recommends parses or raises
    if recommends.mode != "warn":
        raise SkillLintError([f"{skill_path}: gstack mission community-recommends mode must be warn"])
    metadata = _frontmatter(text, skill_path).get("metadata")
    if not isinstance(metadata, dict) or metadata.get("recommended-bundle") != recommends.bundle:
        raise SkillLintError(
            [f"{skill_path}: metadata.recommended-bundle must match community-recommends.bundle"]
        )


def lint_skill(path: Path | str) -> None:
    """Lint adapters and missions; other autonomous-fleet skill types are ignored."""
    skill_path, text = _read_skill(path)
    data = _frontmatter(text, skill_path)
    component = _fleet_component(data)
    if component in ADAPTER_COMPONENTS:
        lint_adapter(skill_path)
    elif component == "mission":
        if skill_path.parent.name in GSTACK_MISSION_SLUGS:
            lint_gstack_mission(skill_path)
        else:
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
