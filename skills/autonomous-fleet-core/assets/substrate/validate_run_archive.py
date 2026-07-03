#!/usr/bin/env python3
"""CLI: validate one or more run-archive directories under .fleet/runs/.

Each archive directory must contain manifest.json conforming to
fleet-run-manifest.schema.json, with every listed file present, the
recorded sha256/size matching disk, and the cross-cutting mtime-ordering
invariants from engine.md ARCHIVE_ENABLED satisfied:

  - blind_fix mtime < findings mtime (per producer)
  - verify_summary mtime > findings mtime (per producer)
  - readiness mtime = max(all file mtimes)
  - findings from different producers are not byte-identical
    (independent-review integrity, issue #77)

Exit codes:
  0 — all validated archives pass (or no archives present)
  1 — one or more archives failed

Default scan path: .fleet/runs/* (skips non-directories and files that don't
look like run_ids).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.fleet_run import RUN_ID_PATTERN, load_and_validate_manifest


def collect_archives(root: Path) -> list[Path]:
    """Return every .fleet/runs/<run_id>/ directory whose basename matches
    the run_id regex. Non-matching names are skipped (operator scratch dirs
    like `tmp/` or `notes/` don't get picked up)."""
    base = root / ".fleet" / "runs"
    if not base.is_dir():
        return []
    return sorted(
        d for d in base.iterdir() if d.is_dir() and RUN_ID_PATTERN.match(d.name)
    )


def main() -> int:
    # SUBSTRATE KILL-SWITCH — see scripts/lib/substrate_disable.py.
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_RUN_ARCHIVE"):
        return announce_disabled("validate-run-archive", "FLEET_DISABLE_RUN_ARCHIVE")

    p = argparse.ArgumentParser(
        description="Validate run-archive directories (.fleet/runs/<run_id>/)."
    )
    p.add_argument(
        "archives",
        nargs="*",
        type=Path,
        help="Archive directories to validate (default: every .fleet/runs/<run_id>/)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root (default: cwd). Used only when archives is empty for the default scan.",
    )
    p.add_argument(
        "--no-checksums",
        action="store_true",
        help="Skip on-disk sha256 verification (schema + mtime ordering only). "
        "Use for cheap pre-flight; the full validator must pass before T-FINAL.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-archive OK lines; only print failures.",
    )
    args = p.parse_args()

    explicit = bool(args.archives)
    if explicit:
        archives = args.archives
    else:
        root = (args.repo_root or Path.cwd()).resolve()
        archives = collect_archives(root)

    if not archives:
        if not args.quiet:
            print("No run-archives found.")
        return 0

    fail_count = 0
    for archive in archives:
        archive = archive.resolve()
        if not archive.is_dir():
            print(f"FAIL {archive} (not a directory)")
            fail_count += 1
            continue

        # When called with --no-checksums, we still want shape + mtime
        # ordering. The fleet_run.load_and_validate_manifest always does
        # checksums; replicate its shape+ordering-only path here.
        if args.no_checksums:
            from lib.fleet_run import validate_manifest_payload  # local import
            import json as _json

            manifest_path = archive / "manifest.json"
            if not manifest_path.is_file():
                print(f"FAIL {archive} (manifest.json missing)")
                fail_count += 1
                continue
            try:
                payload = _json.loads(manifest_path.read_text(encoding="utf-8"))
            except _json.JSONDecodeError as exc:
                print(f"FAIL {archive} (invalid manifest JSON: {exc})")
                fail_count += 1
                continue
            errs = validate_manifest_payload(
                payload,
                archive_root=archive,
                check_files_on_disk=False,
                label=str(manifest_path),
            )
        else:
            _payload, errs = load_and_validate_manifest(archive)

        if errs:
            fail_count += 1
            print(f"FAIL {archive}")
            for e in errs:
                print(f"  - {e}")
        elif not args.quiet:
            print(f"OK   {archive}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
