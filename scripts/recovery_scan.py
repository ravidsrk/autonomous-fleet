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
    return _run_stdout(["git", "-C", str(repo), "worktree", "list", "--porcelain"])


def _pr_list_text(base: str | None) -> str:
    argv = ["gh", "pr", "list", "--state", "all", "--json", "number,headRefName,state,mergedAt"]
    if base:
        argv.extend(["--base", base])
    return _run_stdout(argv)


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
        pr_text = _pr_list_text(args.base)
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
