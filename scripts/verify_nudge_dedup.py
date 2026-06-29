#!/usr/bin/env python3
"""CLI: verify persisted PR-feedback nudge dedup state."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.nudge_dedup import verify_nudge_state_invariants  # noqa: E402


def _nudge_paths(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    direct = target / "nudge-state.json"
    if direct.is_file():
        return [direct]
    return sorted((target / ".fleet" / "runs").glob("*/nudge-state.json"))


def main() -> int:
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_NUDGE_DEDUP"):
        return announce_disabled("nudge-dedup", "FLEET_DISABLE_NUDGE_DEDUP")

    p = argparse.ArgumentParser(description="Verify nudge-state.json dedup invariants.")
    p.add_argument("target", type=Path, help="Run archive dir or repo root.")
    p.add_argument("--summary-out", type=Path, help="Optional JSON summary path.")
    args = p.parse_args()

    if not args.target.exists():
        print(f"verify-nudge-dedup: target not found: {args.target}", file=sys.stderr)
        return 1

    paths = _nudge_paths(args.target)
    if not paths:
        print("verify-nudge-dedup: no nudge-state.json records found")
        return 0

    errors: list[str] = []
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"verify-nudge-dedup: cannot read {path}: {exc}")
            continue
        errors.extend(verify_nudge_state_invariants(record))

    summary = {"records": len(paths), "errors": errors, "ok": not errors}
    if args.summary_out:
        args.summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"verify-nudge-dedup: {len(paths)} record(s) checked")
    if errors:
        for error in errors:
            print(f"FAIL  {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())