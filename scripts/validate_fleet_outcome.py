#!/usr/bin/env python3
"""CLI: validate fleet-outcome frontmatter in readiness docs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.fleet_outcome import parse_readiness, validate_outcome


def collect_readiness_paths(root: Path) -> list[Path]:
    """Default readiness docs under docs/ AND the relocated ledger dir.

    Issue #101/#123: FLEET_LEDGER_DIR relocates fleet files on docs-site
    repos; the validator must not silently miss them.
    """
    import os

    paths = set(root.glob("docs/*-readiness.md"))
    ledger = os.environ.get("FLEET_LEDGER_DIR", "").strip().rstrip("/")
    if ledger and ledger != "docs":
        paths |= set(root.glob(f"{ledger}/*-readiness.md"))
    return sorted(paths)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="*", type=Path, help="Readiness docs (default: docs/*-readiness.md)")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]

    explicit = bool(args.files)
    if explicit:
        paths = args.files
    else:
        paths = collect_readiness_paths(root)

    if not paths:
        print("No readiness docs found.")
        return 0

    errors = 0
    for path in paths:
        if not path.is_file():
            if explicit:
                print(f"FAIL {path} (not found)")
                errors += 1
            else:
                print(f"SKIP {path} (not found)")
            continue
        try:
            outcome = parse_readiness(path)
            verrs = validate_outcome(outcome, path)
            if verrs:
                for e in verrs:
                    print(f"FAIL {e}")
                errors += 1
            else:
                print(f"OK   {path.name} mission={outcome.get('mission')}")
        except (ValueError, yaml.YAMLError) as exc:
            # Malformed YAML in one doc must fail that doc independently, not abort the whole batch
            # with an uncaught yaml.YAMLError.
            print(f"FAIL {path} (invalid: {exc})")
            errors += 1

    if errors:
        print(f"{errors} readiness doc(s) failed.")
        return 1
    print("All readiness docs passed fleet-outcome validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())