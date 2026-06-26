#!/usr/bin/env python3
"""Emit a representative multi-primitive trace for mechanical validation.

Usage:
  python scripts/emit_representative_trace.py --mission doc-sync --out /path/to/run-dir
  python scripts/emit_representative_trace.py --fixture  # overwrite example-fixture trace only

No runtime CLI auth required — drives TraceEmitter directly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.emit_trace import TraceEmitter, emit_representative_mission_trace, iter_trace_file  # noqa: E402
from lib.fleet_run import RUN_ID_PATTERN  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit representative mission trace")
    parser.add_argument("--mission", default="doc-sync")
    parser.add_argument("--run-id", default="20260626T120000Z-doc-sync-000001")
    parser.add_argument("--out", type=Path, help="Directory for trace.jsonl")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help=(
            "Overwrite .fleet/runs/example-fixture/trace.jsonl only when --mission and "
            "--run-id match the committed manifest (use _build_example_fixture.py for full regen)"
        ),
    )
    args = parser.parse_args()

    if not RUN_ID_PATTERN.match(args.run_id):
        print(f"emit_representative_trace: invalid run_id {args.run_id!r}", file=sys.stderr)
        return 2

    repo = Path(__file__).resolve().parent.parent
    if args.fixture:
        out_dir = repo / ".fleet" / "runs" / "example-fixture"
        manifest_path = out_dir / "manifest.json"
        if not manifest_path.is_file():
            print(
                "emit_representative_trace: example-fixture manifest missing; "
                "run: python scripts/_build_example_fixture.py",
                file=sys.stderr,
            )
            return 2
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_mission = manifest["mission"]
        expected_run_id = manifest["run_id"]
        if args.mission != expected_mission:
            print(
                f"emit_representative_trace: --fixture requires --mission {expected_mission!r}, "
                f"got {args.mission!r}",
                file=sys.stderr,
            )
            return 2
        if args.run_id != expected_run_id:
            print(
                f"emit_representative_trace: --fixture requires --run-id {expected_run_id!r}, "
                f"got {args.run_id!r}",
                file=sys.stderr,
            )
            return 2
        file_count = len(manifest["files"])
    elif args.out:
        out_dir = args.out
        file_count = 9
    else:
        print("emit_representative_trace: specify --out or --fixture", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"
    if trace_path.exists():
        trace_path.unlink()

    with TraceEmitter(out_dir, mission=args.mission, run_id=args.run_id) as emitter:
        ids = emit_representative_mission_trace(emitter, file_count=file_count)

    primitives = sorted({e["primitive"] for e in iter_trace_file(trace_path)})
    print(f"emit_representative_trace: wrote {trace_path}")
    print(f"  events: {sum(1 for _ in iter_trace_file(trace_path))}")
    print(f"  primitives: {', '.join(primitives)}")
    print(f"  t_final_id: {ids['t_final']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())