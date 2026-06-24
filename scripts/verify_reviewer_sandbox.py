#!/usr/bin/env python3
"""CLI: verify reviewer-role sandbox manifest attribution.

For each run-archive ``manifest.json``, reviewer producer slugs may only emit
``blind_fix``, ``findings``, and ``verify_summary`` entries. A reviewer producer
attributed a ``diff`` or ``commit`` on the candidate branch is a hard failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.reviewer_sandbox import verify_reviewer_sandbox_manifest  # noqa: E402


def _manifest_paths(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    direct = target / "manifest.json"
    if direct.is_file():
        return [direct]
    runs_root = target / ".fleet" / "runs"
    if runs_root.is_dir():
        return sorted(runs_root.glob("*/manifest.json"))
    return []


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"verify-reviewer-sandbox: cannot read {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"verify-reviewer-sandbox: {path}: manifest must be an object"
    return payload, None


def main() -> int:
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_REVIEWER_SANDBOX"):
        return announce_disabled(
            "verify-reviewer-sandbox", "FLEET_DISABLE_REVIEWER_SANDBOX"
        )

    p = argparse.ArgumentParser(
        description="Verify reviewer-role sandbox manifest attribution.",
    )
    p.add_argument(
        "target",
        type=Path,
        help="Path to manifest.json, a run archive dir, or a repo root containing .fleet/runs.",
    )
    p.add_argument(
        "--reviewer-producer",
        action="append",
        default=[],
        help="Reviewer producer slug to enforce. May be passed more than once.",
    )
    p.add_argument(
        "--candidate-branch",
        help="Candidate branch name. Defaults to candidate_branch/branch fields when present.",
    )
    p.add_argument(
        "--summary-out",
        type=Path,
        help="Optional path to write the verification summary as JSON.",
    )
    args = p.parse_args()

    if not args.target.exists():
        print(f"verify-reviewer-sandbox: target not found: {args.target}", file=sys.stderr)
        return 1

    paths = _manifest_paths(args.target)
    if not paths:
        print("verify-reviewer-sandbox: no manifest.json files found")
        return 0

    problems: list[str] = []
    results: list[dict[str, Any]] = []
    for path in paths:
        manifest, error = _load_json(path)
        if error:
            problems.append(error)
            continue
        result = verify_reviewer_sandbox_manifest(
            manifest,
            reviewer_producers=args.reviewer_producer,
            candidate_branch=args.candidate_branch,
            label=str(path),
        )
        results.append({"manifest": str(path), **result})
        for violation in result["violations"]:
            problems.append(str(violation["message"]))

    summary = {
        "manifests": len(paths),
        "ok": not problems,
        "problems": problems,
        "results": results,
    }
    if args.summary_out:
        args.summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(
        "verify-reviewer-sandbox: "
        f"{len(paths)} manifest(s) checked; {len(problems)} violation(s)"
    )
    if problems:
        for problem in problems:
            print(f"FAIL  {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
