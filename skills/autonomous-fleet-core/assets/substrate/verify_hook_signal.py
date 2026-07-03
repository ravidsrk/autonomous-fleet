#!/usr/bin/env python3
"""CLI: verify hook-signal / no_signal discipline in trace.jsonl."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.emit_trace import iter_trace_file  # noqa: E402
from lib.hook_signal import verify_hook_signal_trace  # noqa: E402


def _trace_paths(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    direct = target / "trace.jsonl"
    if direct.is_file():
        return [direct]
    return sorted((target / ".fleet" / "runs").glob("*/trace.jsonl"))


def main() -> int:
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_HOOK_SIGNAL"):
        return announce_disabled("hook-signal", "FLEET_DISABLE_HOOK_SIGNAL")

    p = argparse.ArgumentParser(description="Verify hook-signal grace in trace streams.")
    p.add_argument("target", type=Path, help="Run archive dir, trace.jsonl, or repo root.")
    p.add_argument(
        "--no-hooks",
        action="store_true",
        help="Skip verification (adapter declares no activity-hook pipeline).",
    )
    p.add_argument("--summary-out", type=Path, help="Optional JSON summary path.")
    args = p.parse_args()

    if not args.target.exists():
        print(f"verify-hook-signal: target not found: {args.target}", file=sys.stderr)
        return 1

    paths = _trace_paths(args.target)
    if not paths:
        print("verify-hook-signal: no trace.jsonl records found")
        return 0

    if args.no_hooks:
        print("verify-hook-signal: skipped (--no-hooks)")
        return 0

    errors: list[str] = []
    for path in paths:
        events = list(iter_trace_file(path))
        errors.extend(verify_hook_signal_trace(events, hook_capable=True))

    summary = {"records": len(paths), "errors": errors, "ok": not errors}
    if args.summary_out:
        args.summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"verify-hook-signal: {len(paths)} trace file(s) checked")
    if errors:
        for error in errors:
            print(f"FAIL  {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())