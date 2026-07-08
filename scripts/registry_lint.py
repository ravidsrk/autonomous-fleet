#!/usr/bin/env python3
"""CLI: assert the mission/adapter registry matches the on-disk catalog + skills-lock."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.substrate_disable import (  # noqa: E402
    SECURITY_OVERRIDE_ACK_ENV,
    announce_disabled,
    is_disabled,
    is_security_disable_acknowledged,
)
from lib import registry_lint as rl  # noqa: E402


def main() -> int:
    # SEC-009: registry-lint enforces supply-chain pin/hash checks — fail-closed
    # like sha-pin. A bare FLEET_DISABLE_REGISTRY_LINT=1 is not enough.
    if is_disabled("FLEET_DISABLE_REGISTRY_LINT"):
        if not is_security_disable_acknowledged():
            print(
                "registry-lint: REFUSING to disable a security check via "
                "FLEET_DISABLE_REGISTRY_LINT without explicit operator override. "
                f"Set {SECURITY_OVERRIDE_ACK_ENV}=1 to acknowledge that "
                "dropping registry pin/hash enforcement is a deliberate, recorded "
                "decision (see DECISIONS.md); failing closed.",
                file=sys.stderr,
            )
            return 1
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
        + rl.lint_exploratory_on_disk_registered(root)
        + rl.lint_exploratory_on_disk_registered(root)
    )
    for e in errors:
        print(f"registry-lint: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
