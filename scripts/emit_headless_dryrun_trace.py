#!/usr/bin/env python3
"""Emit headless dry-run archive + full primitive trace (entry point for shell scripts).

Usage:
  python scripts/emit_headless_dryrun_trace.py --mission doc-sync --repo /path/to/repo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.headless_trace import emit_headless_dryrun_archive  # noqa: E402
from lib.mission_registry import MISSION_DOCS, headless_emit_mission  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit headless dry-run trace archive")
    parser.add_argument("--mission", required=True)
    parser.add_argument("--repo", type=Path, required=True, help="Target git repo (agent cwd)")
    parser.add_argument(
        "--fleet-root",
        type=Path,
        help="autonomous-fleet clone for progress excerpts (default: parent of scripts/)",
    )
    parser.add_argument("--runtime", default="grok")
    parser.add_argument(
        "--runtime-response",
        type=Path,
        help="Captured stdout/stderr from a real headless runtime invocation",
    )
    args = parser.parse_args(argv)

    if args.mission not in MISSION_DOCS and args.mission != "fleet-program":
        print(f"emit_headless_dryrun_trace: unknown mission {args.mission!r}", file=sys.stderr)
        return 2

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"emit_headless_dryrun_trace: repo not found: {repo}", file=sys.stderr)
        return 2

    fleet_root = (args.fleet_root or Path(__file__).resolve().parent.parent).resolve()
    mission = headless_emit_mission(args.mission)
    if args.mission == "fleet-program":
        print(
            f"emit_headless_dryrun_trace: fleet-program remapped to {mission!r} for trace emission",
            file=sys.stderr,
        )

    arch, run_id, primitives = emit_headless_dryrun_archive(
        repo,
        mission=mission,
        runtime=args.runtime,
        fleet_root=fleet_root,
        runtime_response_path=args.runtime_response,
    )
    print(f"emit_headless_dryrun_trace: archive={arch}")
    print(f"  run_id: {run_id}")
    print(f"  primitives ({len(primitives)}): {', '.join(primitives)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())