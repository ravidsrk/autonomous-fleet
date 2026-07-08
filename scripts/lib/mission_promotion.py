"""Validate exploratory mission promotion readiness (archive triple).

A demoted mission may move from ``docs/exploratory/missions/<slug>/`` back to
``skills/<slug>/`` only when progress, readiness, and external archive
evidence all exist. See ``docs/exploratory/missions/README.md``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .mission_registry import MISSION_DOCS, ledger_dir

_PROGRESS_RE = re.compile(r"PHASE:\s*(DONE|BLOCKED)", re.IGNORECASE)
_ARCHIVE_RUN_ID_RE = re.compile(
    r"[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*[a-z0-9]-[0-9a-f]{6}"
)
# A dogfood doc carrying this marker describes a quarantined/withdrawn archive
# (e.g. .fleet/fixtures/first-substrate-8358f1) and must not count as evidence.
_EVIDENCE_EXCLUDE_MARKER = "<!-- promotion-evidence: exclude -->"


@dataclass(frozen=True)
class PromotionReport:
    mission: str
    progress_path: Path | None
    readiness_path: Path | None
    archive_refs: list[str]
    ready: bool
    missing: tuple[str, ...]


def _fleet_outcome_valid(readiness: Path) -> bool:
    try:
        text = readiness.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end < 0:
        return False
    try:
        block = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return False
    if not isinstance(block, dict):
        return False
    fo = block.get("fleet-outcome")
    if not isinstance(fo, dict):
        return False
    status = fo.get("status")
    return status in {"done", "partial"}


def _progress_substantive(progress: Path) -> bool:
    try:
        text = progress.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if not _PROGRESS_RE.search(text):
        return False
    if "TASK" not in text and "task" not in text.lower():
        return False
    return True



def _canonical_registry_doc(
    repo_root: Path, mission: str, key: str, suffix: str
) -> Path:
    doc = MISSION_DOCS.get(mission, {}).get(key, f"{mission}-{suffix}.md")
    return repo_root / ledger_dir() / doc


def _promotion_readiness_path(repo_root: Path, mission: str) -> Path:
    readiness = _canonical_registry_doc(repo_root, mission, "readiness", "readiness")
    if readiness.is_file():
        return readiness
    stem = readiness.name.removesuffix("-readiness.md")
    matches = sorted(
        readiness.parent.glob(f"{stem}*-readiness.md"),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    return matches[0] if matches else readiness


def _archive_evidence(repo_root: Path, mission: str) -> list[str]:
    refs: list[str] = []
    runs = repo_root / ".fleet" / "runs"
    if runs.is_dir():
        for child in sorted(runs.iterdir()):
            if not child.is_dir():
                continue
            manifest = child / "manifest.json"
            if manifest.is_file():
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    data = {}
                if isinstance(data, dict) and data.get("mission") == mission:
                    refs.append(str(child.relative_to(repo_root)))
                    continue
            if mission.replace("_", "-") in child.name:
                refs.append(str(child.relative_to(repo_root)))

    dogfood = repo_root / "docs" / "external-dogfood"
    if dogfood.is_dir():
        for md in dogfood.rglob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            if _EVIDENCE_EXCLUDE_MARKER in text:
                continue
            if mission not in text and mission.replace("-", "_") not in text:
                continue
            if _ARCHIVE_RUN_ID_RE.search(text) or ".fleet/runs/" in text:
                refs.append(str(md.relative_to(repo_root)))

    return sorted(set(refs))


def assess_promotion(repo_root: Path, mission: str) -> PromotionReport:
    """Return promotion readiness for one exploratory mission slug."""
    repo_root = Path(repo_root)
    progress = _canonical_registry_doc(repo_root, mission, "progress", "progress")
    readiness = _promotion_readiness_path(repo_root, mission)
    missing: list[str] = []

    progress_ok = progress.is_file() and _progress_substantive(progress)
    if not progress_ok:
        missing.append("progress")

    readiness_ok = readiness.is_file() and _fleet_outcome_valid(readiness)
    if not readiness_ok:
        missing.append("readiness")

    archives = _archive_evidence(repo_root, mission)
    if not archives:
        missing.append("archive")

    return PromotionReport(
        mission=mission,
        progress_path=progress if progress.is_file() else None,
        readiness_path=readiness if readiness.is_file() else None,
        archive_refs=archives,
        ready=not missing,
        missing=tuple(missing),
    )


def list_exploratory_missions(repo_root: Path) -> list[str]:
    root = Path(repo_root) / "docs" / "exploratory" / "missions"
    if not root.is_dir():
        return []
    out: list[str] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            out.append(child.name)
    return out


def assess_all_exploratory(repo_root: Path) -> list[PromotionReport]:
    return [assess_promotion(repo_root, m) for m in list_exploratory_missions(repo_root)]