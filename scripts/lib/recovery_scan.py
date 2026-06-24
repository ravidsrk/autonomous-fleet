"""Hermetic resume-time recovery scanner for autonomous-fleet ledgers.

The scanner compares three text snapshots supplied by the caller:

* the markdown progress ledger,
* ``git worktree list --porcelain`` output, and
* ``gh pr list --json number,headRefName,state,mergedAt`` output.

It never shells out and never mutates the repository. Results are advisory
classifications that a coordinator can inspect before deciding what to do.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

CLASS_LIVE = "live"
CLASS_DEAD = "dead"
CLASS_PARTIAL = "partial"
CLASS_ORPHAN = "orphan"

ACTION_CONTINUE = "CONTINUE"
ACTION_CLEANUP_WORKTREE = "CLEANUP_WORKTREE"
ACTION_RE_DRIVE = "RE_DRIVE"
ACTION_ESCALATE = "ESCALATE_TO_DECISIONS"
ACTION_ARCHIVE_ORPHAN = "ARCHIVE_ORPHAN"

SCM_MERGED = "merged"
SCM_OPEN = "open"
SCM_CLOSED_UNMERGED = "closed_unmerged"
SCM_ABSENT = "absent"
SCM_AMBIGUOUS = "ambiguous"

_TRUE = frozenset({"1", "t", "true", "yes", "y", "x", "done", "merged", "pass"})
_FALSE = frozenset({"0", "f", "false", "no", "n", "open", "pending", "fail"})
_KV_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_#-]*)\s*(?:=|:)\s*"
    r"(?P<value>`[^`]*`|'[^']*'|\"[^\"]*\"|[^|\s]+)"
)


@dataclass(frozen=True)
class LedgerRow:
    task_id: str
    branch: str | None
    pr_number: int | None
    wt_path: str | None
    flags: dict[str, str]


@dataclass(frozen=True)
class WorktreeRecord:
    path: str
    branch: str | None
    uncommitted_changes: bool


@dataclass(frozen=True)
class PullRequest:
    number: int | None
    head_ref_name: str | None
    state: str
    merged_at: str | None


def _clean(raw: Any) -> str:
    return str(raw).strip().strip("`").strip("'\"")


def _boolish(raw: Any) -> bool | None:
    value = _clean(raw).lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    return None


def _pr_number(raw: Any) -> int | None:
    match = re.search(r"\d+", _clean(raw))
    return int(match.group(0)) if match else None


def _branch_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    branch = _clean(raw)
    prefix = "refs/heads/"
    return branch[len(prefix) :] if branch.startswith(prefix) else branch


def _parse_kv(text: str) -> dict[str, str]:
    return {m.group("key").upper(): _clean(m.group("value")) for m in _KV_RE.finditer(text)}


def _row_from_parts(task_id: str, values: dict[str, str]) -> LedgerRow:
    branch = values.get("BRANCH") or values.get("HEAD_REF") or values.get("REF")
    wt_path = (
        values.get("WT")
        or values.get("WT_PATH")
        or values.get("WORKTREE")
        or values.get("WORKTREE_PATH")
    )
    pr_number = None
    for key in ("PR", "PR#", "PR_NUMBER", "PR_NUM", "PULL_REQUEST"):
        if key in values:
            pr_number = _pr_number(values[key])
            break

    metadata_keys = {
        "TASK",
        "ID",
        "BRANCH",
        "HEAD_REF",
        "REF",
        "WT",
        "WT_PATH",
        "WORKTREE",
        "WORKTREE_PATH",
        "PR",
        "PR#",
        "PR_NUMBER",
        "PR_NUM",
        "PULL_REQUEST",
    }
    flags = {key: value for key, value in values.items() if key not in metadata_keys}
    return LedgerRow(task_id=task_id, branch=branch, pr_number=pr_number, wt_path=wt_path, flags=flags)


def _parse_task_pipe_rows(text: str) -> list[LedgerRow]:
    rows: list[LedgerRow] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("TASK ") and "|" in stripped:
            cells = [cell.strip() for cell in stripped.split("|")]
            task_id = cells[0][len("TASK ") :].strip("`* ")
            values: dict[str, str] = {}
            for cell in cells[1:]:
                values.update(_parse_kv(cell))
            rows.append(_row_from_parts(task_id, values))
    return rows


def _parse_task_table_rows(text: str) -> list[LedgerRow]:
    rows: list[LedgerRow] = []
    header: list[str] | None = None
    for line in text.splitlines():
        if "|" not in line:
            header = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        upper = [cell.upper() for cell in cells]
        if header is None:
            if ("TASK" in upper or "ID" in upper) and ("BRANCH" in upper or "WT" in upper):
                header = upper
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) != len(header):
            continue
        values = dict(zip(header, (_clean(cell) for cell in cells)))
        task_id = values.get("TASK") or values.get("ID") or ""
        if task_id:
            rows.append(_row_from_parts(task_id, values))
    return rows


def parse_ledger_rows(text: str) -> list[LedgerRow]:
    """Parse supported markdown ledger task rows."""
    return _parse_task_pipe_rows(text) + _parse_task_table_rows(text)


def parse_worktrees(text: str) -> list[WorktreeRecord]:
    """Parse ``git worktree list --porcelain`` records.

    The optional ``dirty``/``uncommitted``/``clean`` keys are accepted so tests
    and future CLIs can feed an explicit local-change signal without changing
    the scanner's public input shape.
    """
    records: list[WorktreeRecord] = []
    current: dict[str, str] = {}

    def flush() -> None:
        if "worktree" not in current:
            return
        dirty = _boolish(current.get("dirty", "false")) is True
        uncommitted = _boolish(current.get("uncommitted", "false")) is True
        clean = _boolish(current.get("clean", "true")) is not False
        records.append(
            WorktreeRecord(
                path=current["worktree"],
                branch=_branch_name(current.get("branch")),
                uncommitted_changes=dirty or uncommitted or not clean,
            )
        )

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            current = {}
            continue
        if " " in stripped:
            key, value = stripped.split(" ", 1)
            current[key] = value
        else:
            current[stripped] = "true"
    flush()
    return records


def parse_pr_list(text: str) -> list[PullRequest]:
    """Parse ``gh pr list`` JSON."""
    if not text.strip():
        return []
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("pr list JSON must be a list")
    prs: list[PullRequest] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        prs.append(
            PullRequest(
                number=number if isinstance(number, int) else _pr_number(number),
                head_ref_name=_branch_name(item.get("headRefName")),
                state=_clean(item.get("state", "")).upper(),
                merged_at=item.get("mergedAt") if isinstance(item.get("mergedAt"), str) else None,
            )
        )
    return prs


def _branch_matches(row_branch: str | None, pr_branch: str | None) -> bool:
    if not row_branch or not pr_branch:
        return False
    return row_branch == pr_branch or row_branch.rsplit("/", 1)[-1] == pr_branch


def _matching_prs(row: LedgerRow, prs: list[PullRequest]) -> list[PullRequest]:
    by_number = [pr for pr in prs if row.pr_number is not None and pr.number == row.pr_number]
    if by_number:
        return by_number
    return [pr for pr in prs if _branch_matches(row.branch, pr.head_ref_name)]


def _matching_prs_for_branch(branch: str, prs: list[PullRequest]) -> list[PullRequest]:
    return [pr for pr in prs if _branch_matches(branch, pr.head_ref_name)]


def _scm_state(matches: list[PullRequest]) -> str:
    states = {
        SCM_MERGED
        if pr.state == "MERGED" or pr.merged_at
        else SCM_OPEN
        if pr.state == "OPEN"
        else SCM_CLOSED_UNMERGED
        if pr.state == "CLOSED"
        else SCM_AMBIGUOUS
        for pr in matches
    }
    if not states:
        return SCM_ABSENT
    return states.pop() if len(states) == 1 else SCM_AMBIGUOUS


def _worktree_for_row(row: LedgerRow, worktrees: list[WorktreeRecord]) -> WorktreeRecord | None:
    for wt in worktrees:
        if (row.branch and wt.branch == row.branch) or (row.wt_path and wt.path == row.wt_path):
            return wt
    return None


def classify_row(row: LedgerRow, worktrees: list[WorktreeRecord], prs: list[PullRequest]) -> dict[str, Any]:
    """Classify one ledger row from ledger, worktree, and SCM signals."""
    ledger_merged = _boolish(row.flags.get("MERGED") or row.flags.get("DONE"))
    wt = _worktree_for_row(row, worktrees)
    scm_state = _scm_state(_matching_prs(row, prs))
    signals = {
        "ledger_flag": "merged" if ledger_merged is True else "not_merged" if ledger_merged is False else "unknown",
        "worktree_present": wt is not None,
        "scm_state": scm_state,
    }

    if scm_state == SCM_MERGED and ledger_merged is not True:
        return {"classification": CLASS_PARTIAL, "action": ACTION_ESCALATE, "signals": signals}
    if ledger_merged is True and scm_state in {SCM_OPEN, SCM_CLOSED_UNMERGED, SCM_AMBIGUOUS}:
        return {"classification": CLASS_PARTIAL, "action": ACTION_ESCALATE, "signals": signals}
    if ledger_merged is True and scm_state == SCM_MERGED:
        return {"classification": CLASS_DEAD, "action": ACTION_CLEANUP_WORKTREE, "signals": signals}
    if scm_state == SCM_CLOSED_UNMERGED:
        return {"classification": CLASS_PARTIAL, "action": ACTION_RE_DRIVE, "signals": signals}
    if wt is not None or scm_state == SCM_OPEN:
        return {"classification": CLASS_LIVE, "action": ACTION_CONTINUE, "signals": signals}
    return {"classification": CLASS_PARTIAL, "action": ACTION_ESCALATE, "signals": signals}


def _orphan_entry(wt: WorktreeRecord, prs: list[PullRequest]) -> dict[str, Any]:
    scm_state = _scm_state(_matching_prs_for_branch(wt.branch or "", prs))
    archive_ok = scm_state == SCM_MERGED and not wt.uncommitted_changes
    return {
        "kind": "orphan",
        "task_id": None,
        "branch": wt.branch,
        "pr_number": None,
        "wt_path": wt.path,
        "flags": {},
        "signals": {
            "ledger_flag": "missing",
            "worktree_present": True,
            "scm_state": scm_state,
            "uncommitted_changes": wt.uncommitted_changes,
        },
        "classification": CLASS_ORPHAN,
        "action": ACTION_ARCHIVE_ORPHAN if archive_ok else ACTION_ESCALATE,
    }


def scan_recovery(
    ledger_text: str,
    worktree_text: str,
    pr_list_text: str,
    branch_prefix: str = "fleet/",
) -> dict[str, Any]:
    """Return a JSON-serializable recovery scan report."""
    ledger_rows = parse_ledger_rows(ledger_text)
    worktrees = parse_worktrees(worktree_text)
    prs = parse_pr_list(pr_list_text)

    entries: list[dict[str, Any]] = []
    ledger_branches = {row.branch for row in ledger_rows if row.branch}
    for row in ledger_rows:
        classified = classify_row(row, worktrees, prs)
        entries.append({"kind": "ledger", **asdict(row), **classified})

    for wt in worktrees:
        if wt.branch and wt.branch.startswith(branch_prefix) and wt.branch not in ledger_branches:
            entries.append(_orphan_entry(wt, prs))

    summary = {name: 0 for name in (CLASS_LIVE, CLASS_DEAD, CLASS_PARTIAL, CLASS_ORPHAN)}
    for entry in entries:
        summary[entry["classification"]] += 1
    return {"rows": entries, "summary": summary}
