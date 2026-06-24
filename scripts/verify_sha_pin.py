#!/usr/bin/env python3
"""CLI: verify SHA-PIN records for approved fleet reviews.

For each ``sha-pin.json`` record whose verdict is ``approve`` or ``PASS``, the
CLI resolves the named branch's current HEAD and asks the pure library verifier
to compare it with ``reviewed_sha``. A deleted/unknown branch is N/A only when a
merged marker is present.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.verify_sha_pin import verify_sha_pin  # noqa: E402

_MERGED_MARKERS = (
    re.compile(r"\bmerged\s*[:=]\s*(?:true|t|yes)\b", re.IGNORECASE),
    re.compile(r"\bstatus\s*:\s*done\b", re.IGNORECASE),
)


def _sha_pin_paths(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    direct = target / "sha-pin.json"
    if direct.is_file():
        return [direct]
    return sorted((target / ".fleet" / "runs").glob("*/sha-pin.json"))


def _sibling_readiness_says_merged(run_dir: Path) -> bool:
    readiness_paths = sorted(
        path
        for path in run_dir.iterdir()
        if path.is_file() and ("readiness" in path.name or path.name.startswith("fleet-outcome"))
    )
    for path in readiness_paths:
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in _MERGED_MARKERS):
            return True
    return False


def _load_records(paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"verify-sha-pin: cannot read {path}: {exc}")
            continue
        if isinstance(record, dict) and record.get("merged") is not True:
            if _sibling_readiness_says_merged(path.parent):
                record = {**record, "merged": True}
        records.append(record)
    return records, errors


def _git_head(repo: Path, branch: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    stdout = result.stdout.strip()
    return stdout.splitlines()[0] if stdout else None


def main() -> int:
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_SHA_PIN"):
        return announce_disabled("SHA-pin", "FLEET_DISABLE_SHA_PIN")

    p = argparse.ArgumentParser(
        description="Verify SHA-PIN records for approved fleet reviews.",
    )
    p.add_argument(
        "target",
        type=Path,
        help="Path to sha-pin.json, a run archive dir, or a repo root containing .fleet/runs.",
    )
    p.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Repo root used for `git -C <repo> rev-parse <branch>`. Defaults to CWD.",
    )
    p.add_argument(
        "--summary-out",
        type=Path,
        help="Optional path to write the verification summary as JSON.",
    )
    args = p.parse_args()

    if not args.repo.is_dir():
        print(f"verify-sha-pin: --repo not a directory: {args.repo}", file=sys.stderr)
        return 1

    if not args.target.exists():
        print(f"verify-sha-pin: target not found: {args.target}", file=sys.stderr)
        return 1

    paths = _sha_pin_paths(args.target)
    if not paths:
        print("verify-sha-pin: no sha-pin.json records found")
        return 0

    records, errors = _load_records(paths)
    heads: dict[str, str | None] = {}

    def resolve(branch: str) -> str | None:
        if branch not in heads:
            heads[branch] = _git_head(args.repo, branch)
        return heads[branch]

    errors.extend(verify_sha_pin(records, resolve))

    summary = {
        "records": len(records),
        "errors": errors,
        "ok": not errors,
    }
    if args.summary_out:
        args.summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"verify-sha-pin: {len(records)} record(s) checked")
    if errors:
        for error in errors:
            print(f"FAIL  {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
