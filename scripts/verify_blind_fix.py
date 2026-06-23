#!/usr/bin/env python3
"""CLI: Layer 3 (blind-fix) verifier for a fleet run archive.

For each finding in `<run_dir>/p0-review-findings.json`, verify the
anti-anchoring protocol (`references/blind-fix.md` § The invariant):

1. A blind-fix file exists at the canonical (or multi-reviewer) location.
2. The blind-fix mtime is BEFORE the findings doc mtime.
3. The blind-fix file contains a point-of-creation statement
   (file:[symbol]:line).
4. The blind-fix file contains a pre-commit confidence (0–100).
5. The blind-fix file is not a stub (length, stub-pattern, or diff-marker
   checks).

Exit codes:
  0 — every finding has a valid blind-fix chain
  1 — at least one finding violates the protocol
  2 — usage error (bad run-dir, missing findings doc, etc.)

Lineage: see `skills/autonomous-fleet-core/references/blind-fix.md`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.verify_blind_fix import verify_blind_fix_doc  # noqa: E402


def main() -> int:
    # SUBSTRATE KILL-SWITCH — see scripts/lib/substrate_disable.py.
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_BLIND_FIX"):
        return announce_disabled("verify-blind-fix", "FLEET_DISABLE_BLIND_FIX")

    p = argparse.ArgumentParser(
        description="Layer 3 (blind-fix) verifier for a fleet run archive.",
    )
    p.add_argument(
        "run_dir",
        type=Path,
        help="Path to the run-archive directory (.fleet/runs/<run_id>/).",
    )
    p.add_argument(
        "--findings",
        type=Path,
        default=None,
        help="Override findings doc path. Defaults to <run_dir>/p0-review-findings.json.",
    )
    p.add_argument(
        "--summary-out",
        type=Path,
        help="Optional path to write the verification summary as JSON.",
    )
    args = p.parse_args()

    if not args.run_dir.is_dir():
        print(f"verify-blind-fix: not a directory: {args.run_dir}", file=sys.stderr)
        return 2

    findings_path = args.findings or (args.run_dir / "p0-review-findings.json")
    if not findings_path.is_file():
        print(
            f"verify-blind-fix: findings doc not found: {findings_path}",
            file=sys.stderr,
        )
        return 2

    try:
        text = findings_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"verify-blind-fix: cannot read {findings_path}: {exc}", file=sys.stderr)
        return 2

    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"verify-blind-fix: invalid JSON in {findings_path}: {exc}", file=sys.stderr)
        return 2

    summary = verify_blind_fix_doc(
        doc,
        run_dir=args.run_dir,
        findings_path=findings_path,
    )

    if args.summary_out:
        args.summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    total = summary["findings"]
    verified = summary["verified_blind_fix"]
    unverified = summary["unverified_blind_fix"]
    print(f"verify-blind-fix: {verified}/{total} findings have valid blind-fix chains")
    if unverified:
        print(f"  unverified: {unverified}", file=sys.stderr)
        for result in summary["results"]:
            if not result["ok"]:
                reasons = "; ".join(result["reasons"])
                print(f"  - {result['finding_id']}: {reasons}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
