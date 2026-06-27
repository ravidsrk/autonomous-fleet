#!/usr/bin/env python3
"""CLI: declared cost-estimate aggregation across fleet readiness docs.

The ``cost_estimate`` field is operator-declared (no token/price model), so
this tool reports a DECLARED-ESTIMATE aggregation, not a measured spend.

Subcommands:
  per-run    — one declared-estimate row per readiness doc under --docs-root
  aggregate  — total declared estimate + per-mission estimates across docs

Exit codes:
  0 — at least one readiness doc found and analyzed
  1 — zero readiness docs present
  2 — usage error (bad --docs-root)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.analyze_cost import (  # noqa: E402
    aggregate,
    discover_readiness,
    per_run,
)


def _format_cost(value: float | None) -> str:
    if value is None:
        return "MISSING"
    return f"{value:.2f}"


def _print_per_run(rows: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    header = f"{'source':<60} {'mission':<30} {'status':<8} {'cost_est':>10}"
    print(header)
    print("-" * len(header))
    for r in rows:
        source = r["source"][-58:]
        mission = str(r.get("mission") or "")
        status = str(r.get("status") or "")
        print(
            f"{source:<60} {mission:<30} {status:<8} "
            f"{_format_cost(r.get('cost_estimate')):>10}"
        )


def _print_aggregate(agg: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(agg, indent=2))
        return
    print(f"basis: {agg['basis']} (operator-declared estimate, not measured spend)")
    print(f"runs: {agg['runs']}")
    print(f"missing_cost: {agg['missing_cost']}")
    print(f"estimates_without_provenance: {agg['estimates_without_provenance']}")
    print(f"total_cost_estimate: {agg['total_cost_estimate']:.2f}")
    print("by_mission_estimate:")
    for mission, total in agg["by_mission_estimate"].items():
        print(f"  {mission}: {total:.2f}")


def main() -> int:
    p = argparse.ArgumentParser(description="Cost analysis across fleet readiness docs.")
    p.add_argument(
        "--docs-root",
        type=Path,
        default=Path("docs"),
        help="Directory containing *-readiness.md docs.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )
    p.add_argument(
        "mode",
        choices=["per-run", "aggregate"],
        help="Output mode.",
    )
    args = p.parse_args()

    if not args.docs_root.is_dir():
        print(f"analyze-cost: not a directory: {args.docs_root}", file=sys.stderr)
        return 2

    paths = discover_readiness(args.docs_root)
    if not paths:
        print("analyze-cost: no readiness docs found", file=sys.stderr)
        return 1

    rows = per_run(paths)
    if args.mode == "per-run":
        _print_per_run(rows, args.json)
    else:
        _print_aggregate(aggregate(rows), args.json)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
