#!/usr/bin/env python3
"""Report exploratory mission promotion readiness (archive triple).

Exit 0 when every listed mission is correctly NOT ready (default scan), when
``--require-ready <slug>`` passes, or when ``--require-shipped`` passes with no
undocumented gaps. Exit 1 when a required mission lacks promotion evidence.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.mission_promotion import assess_all_exploratory, assess_promotion  # noqa: E402
from lib.mission_registry import SHIPPED_MISSIONS  # noqa: E402


def _parse_known_gap(value: str) -> tuple[str, str]:
    mission, sep, reason = value.partition(":")
    if not sep or not mission or not reason.strip():
        raise argparse.ArgumentTypeError(
            "--known-gap must be formatted as <slug>:<reason>"
        )
    return mission, reason.strip()


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Exploratory mission promotion gate.")
    required = p.add_mutually_exclusive_group()
    required.add_argument(
        "--require-ready",
        metavar="MISSION",
        help="Exit 1 unless this mission has progress + readiness + archive.",
    )
    required.add_argument(
        "--require-shipped",
        action="store_true",
        help="Exit 1 unless every shipped mission has progress + readiness + archive.",
    )
    p.add_argument(
        "--known-gap",
        action="append",
        default=[],
        type=_parse_known_gap,
        metavar="MISSION:REASON",
        help="Document a temporary shipped-mission gap when using --require-shipped.",
    )
    p.add_argument(
        "--repo",
        type=Path,
        default=root,
        help="Repo root (default: autonomous-fleet checkout).",
    )
    args = p.parse_args(argv)
    if args.known_gap and not args.require_shipped:
        p.error("--known-gap requires --require-shipped")
    repo = args.repo.resolve()

    if args.require_shipped:
        known_gaps = dict(args.known_gap)
        shipped_reports = [
            assess_promotion(repo, mission) for mission in sorted(SHIPPED_MISSIONS)
        ]
        reports_by_mission = {report.mission: report for report in shipped_reports}
        missing_reports = [report for report in shipped_reports if not report.ready]
        unforgiven = [
            report for report in missing_reports if report.mission not in known_gaps
        ]
        unexpected_gaps = sorted(
            mission
            for mission in known_gaps
            if mission not in reports_by_mission or reports_by_mission[mission].ready
        )
        if not missing_reports and not unexpected_gaps:
            print(
                f"validate-mission-promotion: {len(shipped_reports)} shipped missions ready "
                "(progress, readiness, archive)"
            )
            return 0
        for report in missing_reports:
            suffix = ""
            if report.mission in known_gaps:
                suffix = f" (known gap: {known_gaps[report.mission]})"
            print(
                f"validate-mission-promotion: {report.mission} missing: "
                f"{', '.join(report.missing)}{suffix}",
                file=sys.stderr,
            )
        for mission in unexpected_gaps:
            print(
                f"validate-mission-promotion: known gap {mission} does not match "
                "a missing shipped mission",
                file=sys.stderr,
            )
        if unforgiven or unexpected_gaps:
            return 1
        print(
            f"validate-mission-promotion: {len(shipped_reports)} shipped missions checked; "
            "missing artifacts are documented known gaps"
        )
        return 0

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