#!/usr/bin/env python3
"""CLI: verify stacked-PR status consistency in a PR snapshot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.stacked_pr_status import verify_stacked_pr_consistency  # noqa: E402


def _snapshot_paths(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    direct = target / "pr-snapshot.json"
    if direct.is_file():
        return [direct]
    return sorted((target / ".fleet" / "runs").glob("*/pr-snapshot.json"))


def main() -> int:
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_STACKED_PR"):
        return announce_disabled("stacked-pr", "FLEET_DISABLE_STACKED_PR")

    p = argparse.ArgumentParser(description="Verify stacked-PR aggregation rules.")
    p.add_argument("target", type=Path, help="Run archive dir or repo root.")
    p.add_argument("--summary-out", type=Path, help="Optional JSON summary path.")
    args = p.parse_args()

    if not args.target.exists():
        print(f"verify-stacked-pr: target not found: {args.target}", file=sys.stderr)
        return 1

    paths = _snapshot_paths(args.target)
    if not paths:
        print("verify-stacked-pr: no pr-snapshot.json records found")
        return 0

    errors: list[str] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"verify-stacked-pr: cannot read {path}: {exc}")
            continue
        prs = payload.get("prs", payload) if isinstance(payload, dict) else payload
        errors.extend(verify_stacked_pr_consistency(prs))

    summary = {"records": len(paths), "errors": errors, "ok": not errors}
    if args.summary_out:
        args.summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"verify-stacked-pr: {len(paths)} record(s) checked")
    if errors:
        for error in errors:
            print(f"FAIL  {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())