#!/usr/bin/env python3
"""CLI: seat analysis across fleet run-archives.

Subcommands:
  per-run    — one row per archive under --runs-root
  aggregate  — totals + averages across all archives

Exit codes:
  0 — at least one parsable archive found and analyzed
  1 — no parsable archives (all malformed) or zero archives present
  2 — usage error (bad --runs-root)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.analyze_seat import (  # noqa: E402
    aggregate,
    analyze_run,
    discover_runs,
)


def _print_per_run(rows: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    header = (
        f"{'run':<60} {'emit':>5} {'verif':>6} {'closed':>7} "
        f"{'cost':>8} {'vpd':>8} {'stop':>5}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        run = r["run_dir"][-58:]
        print(
            f"{run:<60} {r['findings_emitted']:>5} {r['findings_verified']:>6} "
            f"{r['findings_closed']:>7} {r['cost_estimate']:>8.2f} "
            f"{r['value_per_dollar']:>8.2f} {r['stop_verify_activations']:>5}"
        )


def _print_aggregate(agg: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(agg, indent=2))
        return
    print(f"runs: {agg['runs']}")
    print(f"findings_emitted_total: {agg['findings_emitted_total']}")
    print(f"findings_verified_total: {agg['findings_verified_total']}")
    print(f"findings_closed_total: {agg['findings_closed_total']}")
    print(f"findings_withdrawn_total: {agg['findings_withdrawn_total']}")
    print(f"cost_estimate_total: {agg['cost_estimate_total']:.2f}")
    print(f"value_per_dollar_avg: {agg['value_per_dollar_avg']:.2f}")
    print(f"stop_verify_activations_total: {agg['stop_verify_activations_total']}")
    if agg["wall_clock_to_freeze_avg_s"] is not None:
        print(f"wall_clock_to_freeze_avg_s: {agg['wall_clock_to_freeze_avg_s']:.1f}")
    if agg["wall_clock_to_all_closed_avg_s"] is not None:
        print(
            f"wall_clock_to_all_closed_avg_s: {agg['wall_clock_to_all_closed_avg_s']:.1f}"
        )


def main() -> int:
    p = argparse.ArgumentParser(description="Seat analysis across fleet run-archives.")
    p.add_argument(
        "--runs-root",
        type=Path,
        default=Path(".fleet/runs"),
        help="Directory containing run-archive subdirectories.",
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

    if not args.runs_root.is_dir():
        print(f"analyze-seat: not a directory: {args.runs_root}", file=sys.stderr)
        return 2

    archives = discover_runs(args.runs_root)
    if not archives:
        print("analyze-seat: no archives found", file=sys.stderr)
        return 1

    rows = [analyze_run(d) for d in archives]
    parsable_rows = [r for r in rows if r["parsable"]]
    if not parsable_rows:
        print("analyze-seat: no parsable archives", file=sys.stderr)
        return 1

    if args.mode == "per-run":
        _print_per_run(rows, args.json)
    else:
        _print_aggregate(aggregate(rows), args.json)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
