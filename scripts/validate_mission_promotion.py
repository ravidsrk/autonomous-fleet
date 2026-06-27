#!/usr/bin/env python3
"""Report exploratory mission promotion readiness (archive triple).

Exit 0 when every listed mission is correctly NOT ready (default scan), or when
``--require-ready <slug>`` passes. Exit 1 when ``--require-ready`` fails.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.mission_promotion import assess_all_exploratory, assess_promotion  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Exploratory mission promotion gate.")
    p.add_argument(
        "--require-ready",
        metavar="MISSION",
        help="Exit 1 unless this mission has progress + readiness + archive.",
    )
    p.add_argument(
        "--repo",
        type=Path,
        default=root,
        help="Repo root (default: autonomous-fleet checkout).",
    )
    args = p.parse_args(argv)
    repo = args.repo.resolve()

    if args.require_ready:
        report = assess_promotion(repo, args.require_ready)
        if report.ready:
            print(
                f"validate-mission-promotion: {report.mission} ready "
                f"(progress, readiness, archive)"
            )
            return 0
        print(
            f"validate-mission-promotion: {report.mission} NOT ready; "
            f"missing: {', '.join(report.missing)}",
            file=sys.stderr,
        )
        return 1

    reports = assess_all_exploratory(repo)
    ready = [r for r in reports if r.ready]
    pending = [r for r in reports if not r.ready]
    print(
        f"validate-mission-promotion: {len(reports)} exploratory missions; "
        f"{len(ready)} promotion-ready, {len(pending)} pending"
    )
    for r in pending:
        print(f"  {r.mission}: missing {', '.join(r.missing)}")
    for r in ready:
        print(f"  {r.mission}: READY ({len(r.archive_refs)} archive ref(s))")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())