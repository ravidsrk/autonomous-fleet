#!/usr/bin/env python3
"""CLI: review round-budget circuit-breaker verifier for a fleet run archive.

For ``<run_dir>/trace.jsonl``, count failed reviewer rounds per task. Any task
with more than ``MAX_ROUNDS`` failed review rounds must end as
``GOAL_BLOCKED``/``blocked`` and must not have shipped via successful MERGE.

Exit codes:
  0 - every over-budget task is terminally blocked
  1 - at least one task violates the round-budget circuit breaker
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.emit_trace import iter_trace_file  # noqa: E402
from lib.verify_round_budget import MAX_ROUNDS, verify_round_budget  # noqa: E402


def main() -> int:
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_ROUND_BUDGET"):
        return announce_disabled("verify-round-budget", "FLEET_DISABLE_ROUND_BUDGET")

    p = argparse.ArgumentParser(
        description="Review round-budget verifier for a fleet run archive.",
    )
    p.add_argument(
        "run_dir",
        type=Path,
        help="Path to the run-archive directory (.fleet/runs/<run_id>/).",
    )
    args = p.parse_args()

    if not args.run_dir.is_dir():
        print(f"verify-round-budget: not a directory: {args.run_dir}", file=sys.stderr)
        return 1

    trace_path = args.run_dir / "trace.jsonl"
    if not trace_path.is_file():
        print(f"verify-round-budget: trace file not found: {trace_path}", file=sys.stderr)
        return 1

    summary = verify_round_budget(iter_trace_file(trace_path), max_rounds=MAX_ROUNDS)
    violations = summary["violations"]
    print(
        "verify-round-budget: "
        f"{summary['checked_tasks']} tasks checked; {len(violations)} violations"
    )
    if violations:
        for violation in violations:
            print(f"  - {violation['message']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
