#!/usr/bin/env python3
"""CLI: assert the mission/adapter registry matches the on-disk catalog + skills-lock."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.substrate_disable import announce_disabled, is_disabled  # noqa: E402
from lib import registry_lint as rl  # noqa: E402


def main() -> int:
    if is_disabled("FLEET_DISABLE_REGISTRY_LINT"):
        return announce_disabled("registry-lint", "FLEET_DISABLE_REGISTRY_LINT")
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = (
        rl.lint_shipped_mission_dirs(root)
        + rl.lint_catalog_mentions(root)
        + rl.lint_skills_lock(root)
        + rl.lint_lock_hashes(root)
        + rl.lint_no_skill_version_literals_in_tests(root)
        + rl.lint_mission_state_docs(root)
        + rl.lint_adapter_contract_single_source(root)
        + rl.lint_external_source_pins(root)
        + rl.lint_campaign_missions(root)
    )
    for e in errors:
        print(f"registry-lint: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
