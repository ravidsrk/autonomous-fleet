"""Pure reviewer-role sandbox manifest verifier.

Reviewer placement is enforced live by ``scripts/run-sandboxed.sh --role
reviewer``. This module is the audit-side companion: it checks run-archive
manifests for reviewer producer slugs that are attributed patch-writing
artifacts.

The library is intentionally side-effect free. Callers pass a parsed manifest
dict plus optional reviewer producer slugs and candidate branch metadata; the
thin CLI handles filesystem and JSON loading.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

ALLOWED_REVIEWER_KINDS = frozenset({"blind_fix", "findings", "verify_summary"})
WRITE_ATTRIBUTION_KINDS = frozenset({"diff", "commit"})
_BRANCH_FIELDS = ("candidate_branch", "branch", "head_branch", "headRefName")


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalise_producers(producers: Iterable[str] | None) -> frozenset[str]:
    if producers is None:
        return frozenset()
    return frozenset(p.strip() for p in producers if isinstance(p, str) and p.strip())


def detect_reviewer_producers(manifest: Mapping[str, Any]) -> frozenset[str]:
    """Return producer slugs that look like reviewer producers."""
    files = manifest.get("files")
    if not isinstance(files, list):
        return frozenset()

    producers: set[str] = set()
    for entry in files:
        if not isinstance(entry, Mapping):
            continue
        producer = _clean_str(entry.get("producer"))
        if producer and "reviewer" in producer.lower():
            producers.add(producer)
    return frozenset(sorted(producers))


def _manifest_candidate_branch(
    manifest: Mapping[str, Any], override: str | None
) -> str | None:
    explicit = _clean_str(override)
    if explicit:
        return explicit
    for field in _BRANCH_FIELDS:
        branch = _clean_str(manifest.get(field))
        if branch:
            return branch
    return None


def _entry_branch(entry: Mapping[str, Any]) -> str | None:
    for field in _BRANCH_FIELDS:
        branch = _clean_str(entry.get(field))
        if branch:
            return branch
    return None


def _on_candidate_branch(
    entry: Mapping[str, Any],
    candidate_branch: str | None,
) -> bool:
    if candidate_branch is None:
        return False
    entry_branch = _entry_branch(entry)
    return entry_branch is None or entry_branch == candidate_branch


def verify_reviewer_sandbox_manifest(
    manifest: Any,
    *,
    reviewer_producers: Iterable[str] | None = None,
    candidate_branch: str | None = None,
    label: str = "manifest",
) -> dict[str, Any]:
    """Verify reviewer producer slugs only emitted reviewer-safe artifacts.

    Returns a summary dict. ``ok`` is false when a reviewer producer emitted a
    non-review artifact kind, especially ``diff`` or ``commit`` on the candidate
    branch.
    """
    if not isinstance(manifest, Mapping):
        violation = {
            "path": label,
            "producer": "",
            "kind": "",
            "message": f"{label}: manifest must be an object",
        }
        return {
            "ok": False,
            "reviewer_producers": [],
            "candidate_branch": candidate_branch,
            "checked_files": 0,
            "violations": [violation],
        }

    files = manifest.get("files")
    if not isinstance(files, list):
        violation = {
            "path": label,
            "producer": "",
            "kind": "",
            "message": f"{label}: files must be a list",
        }
        return {
            "ok": False,
            "reviewer_producers": [],
            "candidate_branch": _manifest_candidate_branch(manifest, candidate_branch),
            "checked_files": 0,
            "violations": [violation],
        }

    explicit_reviewers = _normalise_producers(reviewer_producers)
    reviewers = explicit_reviewers or detect_reviewer_producers(manifest)
    branch = _manifest_candidate_branch(manifest, candidate_branch)
    violations: list[dict[str, Any]] = []
    checked = 0

    for idx, entry in enumerate(files):
        if not isinstance(entry, Mapping):
            continue
        producer = _clean_str(entry.get("producer"))
        if producer not in reviewers:
            continue
        checked += 1
        kind = _clean_str(entry.get("kind")) or ""
        path = _clean_str(entry.get("path")) or f"files[{idx}]"
        where = f"{label}.files[{idx}]"

        if kind in WRITE_ATTRIBUTION_KINDS and _on_candidate_branch(entry, branch):
            violations.append(
                {
                    "path": path,
                    "producer": producer,
                    "kind": kind,
                    "message": (
                        f"{where}: reviewer producer {producer!r} is attributed "
                        f"{kind!r} on candidate branch {branch!r}"
                    ),
                }
            )
            continue

        if kind not in ALLOWED_REVIEWER_KINDS:
            violations.append(
                {
                    "path": path,
                    "producer": producer,
                    "kind": kind,
                    "message": (
                        f"{where}: reviewer producer {producer!r} emitted forbidden "
                        f"kind {kind!r}; allowed reviewer kinds are "
                        f"{sorted(ALLOWED_REVIEWER_KINDS)}"
                    ),
                }
            )

    return {
        "ok": not violations,
        "reviewer_producers": sorted(reviewers),
        "candidate_branch": branch,
        "checked_files": checked,
        "violations": violations,
    }


__all__ = [
    "ALLOWED_REVIEWER_KINDS",
    "WRITE_ATTRIBUTION_KINDS",
    "detect_reviewer_producers",
    "verify_reviewer_sandbox_manifest",
]
