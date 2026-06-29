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
    if target.is_dir():
        paths = sorted(target.glob("sha-pin*.json"))
        pins_dir = target / "sha-pins"
        if pins_dir.is_dir():
            paths.extend(sorted(pins_dir.glob("*.json")))
        if paths:
            return paths
    return sorted(
        list((target / ".fleet" / "runs").glob("*/sha-pin.json"))
        + list((target / ".fleet" / "runs").glob("*/sha-pin-*.json"))
        + list((target / ".fleet" / "runs").glob("*/sha-pins/*.json"))
    )


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
    # Terminate option parsing before the branch so a branch name can never be
    # interpreted as a git option (e.g. "--upload-pack=...", "--help"). We use
    # `--end-of-options` rather than a bare `--`: for `git rev-parse`, `--`
    # switches the remaining args to *paths* (which would NOT resolve the
    # branch), whereas `--end-of-options` ends option parsing while still
    # treating the next argument as a revision. `--verify` makes rev-parse emit
    # exactly one clean SHA line (and fail non-zero on anything else), so a
    # crafted name yields None rather than leaking an injected option. This is
    # belt-and-suspenders with lib._BRANCH_RE's alphanumeric-first-char rule,
    # which already rejects leading-dash names like "--help" upstream.
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--end-of-options", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    stdout = result.stdout.strip()
    return stdout.splitlines()[0] if stdout else None


def main() -> int:
    from lib.substrate_disable import (
        SECURITY_OVERRIDE_ACK_ENV,
        announce_disabled,
        is_disabled,
        is_security_disable_acknowledged,
    )

    if is_disabled("FLEET_DISABLE_SHA_PIN"):
        # SHA-pin is a security/integrity gate, NOT an operator escape-hatch
        # quality gate: it must FAIL CLOSED. A bare FLEET_DISABLE_SHA_PIN=1 is
        # not enough to drop a supply-chain check — a stray env var in CI must
        # not silently disable it. Require an explicit, recorded operator ack.
        if not is_security_disable_acknowledged():
            print(
                "SHA-pin: REFUSING to disable a security check via "
                "FLEET_DISABLE_SHA_PIN without explicit operator override. "
                f"Set {SECURITY_OVERRIDE_ACK_ENV}=1 to acknowledge that "
                "dropping the SHA-pin integrity gate is a deliberate, recorded "
                "decision (see DECISIONS.md); failing closed.",
                file=sys.stderr,
            )
            return 1
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
