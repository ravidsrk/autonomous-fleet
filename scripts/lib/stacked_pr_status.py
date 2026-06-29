"""Stacked-PR status aggregation (Agent Orchestrator ``status.go`` port).

Pure functions for worst-wins PR pipeline status and stacked-child suppression.
No I/O.
"""
from __future__ import annotations

from typing import Any

PRFacts = dict[str, Any]

_STATUS_SEVERITY = {
    "ci_failed": 0,
    "changes_requested": 1,
    "draft": 2,
    "review_pending": 3,
    "pr_open": 4,
    "approved": 5,
    "mergeable": 6,
    "idle": 7,
}


def build_stacks(prs: list[PRFacts]) -> dict[str, dict[str, bool]]:
    """Derive stack position per PR URL from source/target branch columns."""
    open_sources = {
        p["source_branch"]
        for p in prs
        if not p.get("merged") and not p.get("closed") and p.get("source_branch")
    }
    stacks: dict[str, dict[str, bool]] = {}
    for pr in prs:
        target = pr.get("target_branch") or ""
        blocked = bool(target and target in open_sources)
        stacks[pr["url"]] = {"blocked": blocked, "bottom_of_stack": not blocked}
    return stacks


def pr_pipeline_status(pr: PRFacts) -> str:
    """Map one PR fact row to a pipeline status string."""
    if pr.get("ci") == "failing":
        return "ci_failed"
    if pr.get("draft"):
        return "draft"
    if pr.get("review") == "changes_requested" or pr.get("review_comments"):
        return "changes_requested"
    if pr.get("mergeability") == "mergeable":
        return "mergeable"
    if pr.get("review") == "approved":
        return "approved"
    if pr.get("review") == "required":
        return "review_pending"
    return "pr_open"


def is_actionable_child_signal(status: str) -> bool:
    """Child stacked on open parent: only problem signals stay visible."""
    return status in {"ci_failed", "draft", "changes_requested"}


def aggregate_pr_status(prs: list[PRFacts]) -> str:
    """Worst-wins reduction across open PRs with stacked-child suppression."""
    open_prs = [p for p in prs if not p.get("merged") and not p.get("closed")]
    if not open_prs:
        if any(p.get("merged") for p in prs):
            return "merged"
        return "idle"

    stacks = build_stacks(open_prs)
    candidates: list[str] = []
    for pr in open_prs:
        status = pr_pipeline_status(pr)
        if stacks[pr["url"]]["blocked"] and not is_actionable_child_signal(status):
            continue
        candidates.append(status)

    if not candidates:
        candidates = [pr_pipeline_status(p) for p in open_prs]

    worst = candidates[0]
    for status in candidates[1:]:
        if _STATUS_SEVERITY.get(status, 99) < _STATUS_SEVERITY.get(worst, 99):
            worst = status
    return worst


def should_nudge_merge_conflict(pr: PRFacts, stacks: dict[str, dict[str, bool]]) -> bool:
    """Merge-conflict nudges only fire for the bottom of a stack."""
    if pr.get("mergeability") != "conflicting":
        return False
    return stacks.get(pr["url"], {}).get("bottom_of_stack", True)


def validate_pr_snapshot(prs: Any, label: str = "pr-snapshot") -> list[str]:
    """Return schema errors for a PR snapshot list."""
    if not isinstance(prs, list):
        return [f"{label}: must be an array"]

    errors: list[str] = []
    for idx, pr in enumerate(prs):
        if not isinstance(pr, dict):
            errors.append(f"{label}[{idx}]: must be an object")
            continue
        for field in ("url", "source_branch", "target_branch"):
            if field not in pr:
                errors.append(f"{label}[{idx}]: missing required field '{field}'")
        url = pr.get("url")
        if url is not None and (not isinstance(url, str) or not url.strip()):
            errors.append(f"{label}[{idx}]: url must be a non-empty string")
    return errors


def verify_stacked_pr_consistency(prs: list[PRFacts]) -> list[str]:
    """Return errors when stacked rules are violated in a snapshot."""
    errors: list[str] = []
    schema_errors = validate_pr_snapshot(prs)
    if schema_errors:
        return schema_errors

    stacks = build_stacks(prs)
    session_status = aggregate_pr_status(prs)

    for pr in prs:
        if pr.get("mergeability") != "conflicting":
            continue
        if not should_nudge_merge_conflict(pr, stacks):
            continue
        if pr.get("nudge_merge_conflict") is False:
            errors.append(
                f"{pr['url']}: merge conflict at stack bottom requires nudge_merge_conflict=true"
            )

    suppressed = [
        pr["url"]
        for pr in prs
        if stacks[pr["url"]]["blocked"]
        and pr_pipeline_status(pr) in {"mergeable", "approved", "review_pending", "pr_open"}
        and pr.get("reported_session_status") == pr_pipeline_status(pr)
    ]
    for url in suppressed:
        errors.append(
            f"{url}: blocked stacked child must not drive session status "
            f"(session_status={session_status!r})"
        )

    return errors