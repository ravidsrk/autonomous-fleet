#!/usr/bin/env python3
"""CLI: validate fleet branch/worktree hash namespacing in run archives."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.namespace import progress_paths_from_manifest, validate_archive_namespacing  # noqa: E402


def collect_archives(root: Path) -> list[Path]:
    """Return manifest-bearing run archive directories under ``.fleet/runs``."""
    runs = root / ".fleet" / "runs"
    if not runs.is_dir():
        return []
    return sorted(path for path in runs.iterdir() if path.is_dir() and (path / "manifest.json").is_file())


def _archive_child(archive: Path, rel_path: str) -> Path:
    archive = archive.resolve()
    child = (archive / rel_path).resolve()
    try:
        child.relative_to(archive)
    except ValueError as exc:
        raise ValueError(f"{rel_path}: progress path escapes archive") from exc
    return child


def _read_manifest(archive: Path) -> tuple[Any, list[str]]:
    manifest_path = archive / "manifest.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")), []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"{manifest_path}: cannot read manifest: {exc}"]


def _read_progress_ledgers(
    archive: Path, progress_paths: list[str]
) -> tuple[dict[str, str], list[str]]:
    ledgers: dict[str, str] = {}
    errors: list[str] = []
    for rel_path in progress_paths:
        try:
            ledgers[rel_path] = _archive_child(archive, rel_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            errors.append(f"{rel_path}: cannot read progress ledger: {exc}")
    return ledgers, errors


def validate_archive_path(archive: Path) -> list[str]:
    """Read one archive from disk and return namespacing errors."""
    manifest, errors = _read_manifest(archive)
    if errors:
        return errors

    _, progress_paths, manifest_errors = progress_paths_from_manifest(
        manifest, label=str(archive / "manifest.json")
    )
    if manifest_errors:
        return manifest_errors

    ledgers, ledger_errors = _read_progress_ledgers(archive, progress_paths)
    if ledger_errors:
        return ledger_errors

    return validate_archive_namespacing(manifest, ledgers, label=str(archive / "manifest.json"))


def main() -> int:
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_NAMESPACING"):
        return announce_disabled("validate-namespacing", "FLEET_DISABLE_NAMESPACING")

    parser = argparse.ArgumentParser(
        description="Validate per-run branch/worktree hash namespacing in run archives.",
    )
    parser.add_argument(
        "archives",
        nargs="*",
        type=Path,
        help="Run archive directories to validate (default: .fleet/runs/* with manifest.json).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root for default archive discovery.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress OK/no-archive lines.")
    args = parser.parse_args()

    archives = args.archives if args.archives else collect_archives(args.repo_root)
    if not archives:
        if not args.quiet:
            print("validate-namespacing: no run archives found")
        return 0

    failures = 0
    for archive in archives:
        if not archive.is_dir():
            print(f"FAIL {archive} (not a directory)", file=sys.stderr)
            failures += 1
            continue
        errors = validate_archive_path(archive)
        if errors:
            failures += 1
            print(f"FAIL {archive}", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        elif not args.quiet:
            print(f"OK   {archive}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
