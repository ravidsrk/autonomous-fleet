#!/usr/bin/env python3
"""CLI wrapper for the hermetic recovery scanner."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.recovery_scan import scan_recovery  # noqa: E402


def _run_stdout(argv: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{' '.join(argv)} failed: {detail}")
    return result.stdout


def _worktree_text(repo: Path) -> str:
    raw = _run_stdout(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    lines: list[str] = []
    current_worktree: str | None = None
    has_clean_signal = False

    def append_dirty_signal() -> None:
        if current_worktree is None or has_clean_signal:
            return
        try:
            status = _run_stdout(
                ["git", "-C", current_worktree, "status", "--porcelain"],
                cwd=repo,
            )
        except RuntimeError:
            lines.append("dirty true")
            return
        lines.append("dirty true" if status.strip() else "dirty false")

    for line in raw.splitlines():
        if not line.strip():
            append_dirty_signal()
            lines.append(line)
            current_worktree = None
            has_clean_signal = False
            continue
        key = line.split(" ", 1)[0]
        if key == "worktree":
            current_worktree = line.split(" ", 1)[1]
            has_clean_signal = False
        elif key in {"dirty", "uncommitted", "clean"}:
            has_clean_signal = True
        lines.append(line)
    append_dirty_signal()
    return "\n".join(lines) + ("\n" if raw.endswith("\n") else "")


def _pr_list_text(base: str | None, repo: Path) -> str:
    argv = ["gh", "pr", "list", "--state", "all", "--json", "number,headRefName,state,mergedAt"]
    if base:
        argv.extend(["--base", base])
    return _run_stdout(argv, cwd=repo)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify fleet ledger rows against git worktrees and GitHub PR state."
    )
    parser.add_argument("ledger", type=Path, help="Progress ledger to scan.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--base", help="Optional gh PR base branch filter.")
    parser.add_argument("--branch-prefix", default="fleet/", help="Branch prefix for orphan sweep.")
    args = parser.parse_args()

    try:
        ledger_text = args.ledger.read_text(encoding="utf-8")
        worktree_text = _worktree_text(args.repo)
        pr_text = _pr_list_text(args.base, args.repo)
        report = scan_recovery(
            ledger_text,
            worktree_text,
            pr_text,
            branch_prefix=args.branch_prefix,
        )
    except (OSError, RuntimeError, json.JSONDecodeError, ValueError) as exc:
        print(f"recovery-scan: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
