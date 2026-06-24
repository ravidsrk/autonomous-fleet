#!/usr/bin/env python3
"""CLI: trace-emission validator and summary printer for a fleet run archive.

Subcommands:

- ``validate <path>``  — validate every line of a ``trace.jsonl`` file
  against the schema. Exit 0 = all valid, 1 = at least one invalid line,
  2 = usage error (missing file, unreadable, etc.).
- ``summary <run_dir>`` — read ``<run_dir>/trace.jsonl`` and print counts
  by primitive, role, and status. Same exit-code convention.

Lineage: see ``skills/autonomous-fleet-core/references/engine.md`` § TRACE
EMISSION and ``assets/fleet-trace.schema.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.emit_trace import health_rollup, iter_trace_file, validate_event  # noqa: E402


def _cmd_validate(path: Path) -> int:
    if not path.is_file():
        print(f"emit-trace: not a file: {path}", file=sys.stderr)
        return 2
    bad = 0
    total = 0
    skipped = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                total += 1
                try:
                    event = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    skipped += 1
                    bad += 1
                    print(
                        f"emit-trace: {path}:{lineno}: invalid JSON: {exc}",
                        file=sys.stderr,
                    )
                    continue
                errors = validate_event(event)
                if errors:
                    bad += 1
                    for err in errors:
                        print(
                            f"emit-trace: {path}:{lineno}: {err}",
                            file=sys.stderr,
                        )
    except OSError as exc:
        print(f"emit-trace: cannot read {path}: {exc}", file=sys.stderr)
        return 2

    print(
        f"emit-trace: validated {total} events from {path} "
        f"({bad} invalid, {skipped} unparseable)"
    )
    return 1 if bad else 0


def _cmd_summary(run_dir: Path) -> int:
    if not run_dir.is_dir():
        print(f"emit-trace: not a directory: {run_dir}", file=sys.stderr)
        return 2
    trace_path = run_dir / "trace.jsonl"
    if not trace_path.is_file():
        print(f"emit-trace: trace file not found: {trace_path}", file=sys.stderr)
        return 2

    primitives: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    events = list(iter_trace_file(trace_path))
    total = 0
    for event in events:
        total += 1
        primitives[str(event.get("primitive", "<missing>"))] += 1
        roles[str(event.get("role", "<missing>"))] += 1
        statuses[str(event.get("status", "<missing>"))] += 1

    print(f"emit-trace: {total} events in {trace_path}")
    print("  primitives:")
    for key, count in sorted(primitives.items()):
        print(f"    {key}: {count}")
    print("  roles:")
    for key, count in sorted(roles.items()):
        print(f"    {key}: {count}")
    print("  statuses:")
    for key, count in sorted(statuses.items()):
        print(f"    {key}: {count}")
    health = health_rollup(events)
    last_failure = health["last_failure"]
    if last_failure is None:
        last = "last failure none"
    else:
        last = (
            "last failure "
            f"{last_failure['primitive']}@{last_failure['role']} "
            f"ts={last_failure['ts']}"
        )
    print(
        "  health: "
        f"{health['succeeded']} ok / {health['failed']} failed / "
        f"{health['blocked']} blocked / {health['skipped']} skipped; {last}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Trace-emission validator/summary for a fleet run archive.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate a trace.jsonl file.")
    p_validate.add_argument("path", type=Path, help="Path to trace.jsonl.")

    p_summary = sub.add_parser(
        "summary", help="Print counts by primitive/role/status."
    )
    p_summary.add_argument(
        "run_dir", type=Path, help="Path to .fleet/runs/<run_id>/."
    )

    args = p.parse_args(argv)

    if args.command == "validate":
        return _cmd_validate(args.path)
    return _cmd_summary(args.run_dir)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
