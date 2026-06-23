#!/usr/bin/env python3
"""CLI: structurally validate AND source-verify a fleet reviewer findings document.

Reads a JSON findings doc emitted by adversarial-review-and-fix (or any review
mission), conformant to
`skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json`.

Two passes — both must succeed for exit 0:

1. **Structural validation** — required fields, enum values, id uniqueness,
   schema_version pin. Fails fast before we touch the filesystem so a malformed
   doc produces a clean error instead of misleading file-not-found noise.
2. **Source verification** — for each finding, whitespace-tolerant grep of
   `evidence.quoted_line` in `evidence.file_path`, resolved against `--repo`.
   Findings whose quote can't be located are mutated in place with
   `verified: false` and a `verify_reason`. The doc is rewritten when
   `--write` (or `--in-place`) is set; otherwise we print the summary only.

Exit codes:
  0 — structurally valid AND every finding verified
  1 — at least one finding unverified (likely reviewer hallucination)
  2 — structurally invalid (schema violation; verification skipped)
  3 — usage error (missing file, unreadable, bad --repo, etc.)

Lineage: GodModeSkill work-converge.py self-consistency check, generalised
into autonomous-fleet's adapter-agnostic shape.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.verify_findings import (
    load_findings_doc,
    validate_findings_doc,
    verify_findings_doc,
)


def main() -> int:
    # SUBSTRATE KILL-SWITCH — see scripts/lib/substrate_disable.py.
    # Checked BEFORE arg parsing so a disabled layer never inspects user
    # input, never touches disk, and never reports errors that would
    # confuse a bench operator into thinking the substrate ran.
    from lib.substrate_disable import announce_disabled, is_disabled

    if is_disabled("FLEET_DISABLE_VERIFY_FINDINGS"):
        return announce_disabled("verify-findings", "FLEET_DISABLE_VERIFY_FINDINGS")

    p = argparse.ArgumentParser(
        description="Validate and source-verify a fleet reviewer findings JSON document.",
    )
    p.add_argument(
        "findings_doc",
        type=Path,
        help="Path to the findings JSON document.",
    )
    p.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Repo root for resolving relative evidence.file_path entries. Defaults to CWD.",
    )
    p.add_argument(
        "--write",
        action="store_true",
        help="Rewrite the findings doc with `verified` and `verify_reason` fields populated. "
        "Default: dry run, print summary only.",
    )
    p.add_argument(
        "--summary-out",
        type=Path,
        help="Optional path to write the verification summary as JSON. "
        "Operators wire this into fleet-outcome.metrics directly.",
    )
    p.add_argument(
        "--strict-schema",
        action="store_true",
        help="Treat schema warnings as errors. Currently every reported issue is already "
        "an error; reserved for future soft-warning checks.",
    )
    args = p.parse_args()

    if not args.findings_doc.is_file():
        print(f"verify-findings: not a file: {args.findings_doc}", file=sys.stderr)
        return 3

    if not args.repo.is_dir():
        print(f"verify-findings: --repo not a directory: {args.repo}", file=sys.stderr)
        return 3

    try:
        doc = load_findings_doc(args.findings_doc)
    except ValueError as exc:
        print(f"verify-findings: {exc}", file=sys.stderr)
        return 2

    # Pass 1 — schema. We bail before verification when shape is wrong, otherwise
    # we'd report "file not found" for paths that don't even exist in the schema.
    schema_errors = validate_findings_doc(doc, label=str(args.findings_doc))
    if schema_errors:
        for e in schema_errors:
            print(f"SCHEMA  {e}", file=sys.stderr)
        print(
            f"verify-findings: {len(schema_errors)} schema error(s); skipping source verification.",
            file=sys.stderr,
        )
        return 2

    # Pass 2 — verification. Mutates doc in place.
    summary = verify_findings_doc(doc, repo_root=args.repo.resolve())

    # Optional write-back so fleet runs can keep one canonical artifact under
    # `.fleet/runs/<run_id>/`. Round-tripped JSON stays sorted and 2-space
    # indented to keep diffs readable.
    if args.write:
        args.findings_doc.write_text(
            json.dumps(doc, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    if args.summary_out:
        args.summary_out.write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )

    # Human-readable summary on stdout. Programmatic consumers use --summary-out.
    total = summary["total_findings"]
    verified = summary["verified_findings"]
    unverified = summary["unverified_findings"]
    print(f"verify-findings: {verified}/{total} findings verified")
    print(f"  unverified: {unverified}")
    if summary["unverified_ids"]:
        print(f"  unverified ids: {', '.join(summary['unverified_ids'])}")
    print(f"  auto_applicable: {summary['auto_applicable_findings']}")
    print(f"  human_gated:     {summary['human_gated_findings']}")

    if unverified:
        # Surface the verdict so operators don't need to parse JSON to know what to do
        print(
            "\nDOWNGRADE: at least one finding's quoted_line was not found in the cited file. "
            "These are likely reviewer hallucinations; fleet-outcome.metrics.unverified_findings "
            "must surface this count and the operator must inspect each one before the fix loop "
            "consumes them.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
