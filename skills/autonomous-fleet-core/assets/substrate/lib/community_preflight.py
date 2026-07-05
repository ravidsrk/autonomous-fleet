"""Community skill recommends-block loader and warn-tier preflight checks."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

_RECOMMENDS_BLOCK_RE = re.compile(
    r"```(?:yaml|yml)\s+community-recommends\s*\n(?P<body>.*?)^```",
    re.MULTILINE | re.DOTALL,
)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.S)

GSTACK_MISSION_SLUGS: frozenset[str] = frozenset(
    {
        "browser-qa-fix",
        "incident-investigate",
    }
)

# Host-agnostic skill roots probed in order (first match wins).
_SKILL_ROOT_TEMPLATES: tuple[str, ...] = (
    "{home}/.claude/skills/gstack/{skill}",
    "{home}/.claude/skills/{skill}",
    "{home}/.cursor/skills/gstack/{skill}",
    "{home}/.cursor/skills/{skill}",
    "{home}/.grok/skills/{skill}",
    "{home}/.agents/skills/{skill}",
)


@dataclass(frozen=True)
class CommunityRecommends:
    bundle: str
    skills: tuple[str, ...]
    mode: str = "warn"

    @property
    def is_fail_mode(self) -> bool:
        return self.mode == "fail"


@dataclass(frozen=True)
class CommunityCheckResult:
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    missing_skills: tuple[str, ...]
    bundle: str | None
    mode: str | None
    recommended_line: str | None = None
    install_hint: str | None = None


def resolve_probe_home(explicit: str | None = None) -> str | None:
    """Return probe home from explicit arg or ``COMMUNITY_PROBE_HOME`` env."""
    if explicit is not None:
        return explicit
    env = os.environ.get("COMMUNITY_PROBE_HOME", "").strip()
    return env or None


def recommendation_line(recommends: CommunityRecommends) -> str:
    """Human-readable summary of the recommended community bundle."""
    return (
        f"recommended community bundle {recommends.bundle!r} "
        f"skills: {', '.join(recommends.skills)}"
    )


def install_hint_line(bundle: str) -> str:
    """Opt-in install command for a community bundle."""
    return f"install: ./scripts/install-community.sh {bundle}"


def _skill_md_path(path: Path | str) -> Path:
    skill_path = Path(path)
    if skill_path.is_dir():
        skill_path = skill_path / "SKILL.md"
    if not skill_path.is_file():
        raise ValueError(f"{skill_path}: missing SKILL.md")
    return skill_path


def _parse_recommends_mapping(data: Mapping[str, Any], source: str) -> CommunityRecommends:
    bundle = data.get("bundle")
    if not isinstance(bundle, str) or not bundle.strip():
        raise ValueError(f"{source}: community-recommends requires non-empty bundle")
    skills_raw = data.get("skills")
    if not isinstance(skills_raw, list) or not skills_raw:
        raise ValueError(f"{source}: community-recommends requires non-empty skills list")
    skills = tuple(str(s).strip() for s in skills_raw if str(s).strip())
    if not skills:
        raise ValueError(f"{source}: community-recommends skills list is empty")
    raw_mode = data.get("mode", "warn")
    if raw_mode is False:
        mode = "off"
    else:
        mode = str(raw_mode).strip().lower()
    if mode not in {"warn", "fail", "off"}:
        raise ValueError(f"{source}: community-recommends mode must be warn, fail, or off")
    return CommunityRecommends(bundle=bundle.strip(), skills=skills, mode=mode)


def has_recommends_block(text: str) -> bool:
    """Return True when SKILL.md body contains a fenced community-recommends block."""
    return _RECOMMENDS_BLOCK_RE.search(text) is not None


def load_recommends(mission_dir: Path | str) -> CommunityRecommends | None:
    """Load ``community-recommends`` from fenced block or frontmatter metadata."""
    skill_path = _skill_md_path(mission_dir)
    text = skill_path.read_text(encoding="utf-8")

    match = _RECOMMENDS_BLOCK_RE.search(text)
    if match:
        data = yaml.safe_load(match.group("body")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{skill_path}: community-recommends block must be a mapping")
        return _parse_recommends_mapping(data, str(skill_path))

    fm_match = _FRONTMATTER_RE.match(text)
    if not fm_match:
        return None
    frontmatter = yaml.safe_load(fm_match.group(1)) or {}
    if not isinstance(frontmatter, dict):
        return None
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        return None
    nested = metadata.get("community-recommends")
    if isinstance(nested, dict):
        return _parse_recommends_mapping(nested, f"{skill_path} frontmatter")
    return None


def skill_probe_roots(home: str | None = None) -> list[Path]:
    """Return concrete probe directories for a skill id lookup."""
    base = Path(home or os.path.expanduser("~"))
    return [Path(t.format(home=base, skill="")) for t in _SKILL_ROOT_TEMPLATES]


def probe_skill_installed(
    skill_id: str,
    *,
    home: str | None = None,
    extra_roots: Sequence[Path] = (),
) -> bool:
    """Best-effort check that a community skill is present on disk."""
    skill = skill_id.strip()
    if not skill:
        return False
    home_path = Path(home or os.path.expanduser("~"))
    candidates: list[Path] = []
    for template in _SKILL_ROOT_TEMPLATES:
        candidates.append(Path(template.format(home=home_path, skill=skill)))
    candidates.extend(extra_roots)
    for root in candidates:
        if (root / "SKILL.md").is_file():
            return True
    return False


def check(
    recommends: CommunityRecommends | None,
    *,
    home: str | None = None,
    extra_roots: Sequence[Path] = (),
    probe: Any = probe_skill_installed,
) -> CommunityCheckResult:
    """Return warnings/failures for missing recommended community skills."""
    if recommends is None or recommends.mode == "off":
        return CommunityCheckResult((), (), (), None, None)

    probe_home = resolve_probe_home(home)
    rec_line = recommendation_line(recommends)
    install_line = install_hint_line(recommends.bundle)

    missing = tuple(
        skill
        for skill in recommends.skills
        if not probe(skill, home=probe_home, extra_roots=extra_roots)
    )
    if not missing:
        return CommunityCheckResult(
            (),
            (),
            (),
            recommends.bundle,
            recommends.mode,
            recommended_line=rec_line,
            install_hint=install_line,
        )

    hint = (
        f"recommended community bundle {recommends.bundle!r} missing skills: "
        f"{', '.join(missing)} — {install_line}"
    )
    if recommends.is_fail_mode:
        return CommunityCheckResult(
            (),
            (hint,),
            missing,
            recommends.bundle,
            recommends.mode,
            recommended_line=rec_line,
            install_hint=install_line,
        )
    return CommunityCheckResult(
        (hint,),
        (),
        missing,
        recommends.bundle,
        recommends.mode,
        recommended_line=rec_line,
        install_hint=install_line,
    )


def mission_skill_path(repo_root: Path, mission: str) -> Path | None:
    """Resolve SKILL.md for shipped or exploratory missions."""
    shipped = repo_root / "skills" / mission / "SKILL.md"
    if shipped.is_file():
        return shipped.parent
    exploratory = repo_root / "docs" / "exploratory" / "missions" / mission / "SKILL.md"
    if exploratory.is_file():
        return exploratory.parent
    return None