"""Substrate kill-switch convention.

Each of the 4 verification-substrate layers exposes a `FLEET_DISABLE_*`
env var that, when set to a truthy value, makes the layer's CLI early-
exit with code 0 and a one-line stderr notice. This is the operator-
facing kill switch and the comparator the `bench-adversarial.sh` driver
needs to flip the substrate off without forking the codebase.

Env var → layer mapping:

  FLEET_DISABLE_VERIFY_FINDINGS  → scripts/verify_findings.py     (Layer 1)
  FLEET_DISABLE_STOP_VERIFY      → scripts/stop_verify.py         (Layer 2)
                                   (legacy alias: STOP_VERIFY_DISABLED)
  FLEET_DISABLE_BLIND_FIX        → scripts/verify_blind_fix.py    (Layer 3)
  FLEET_DISABLE_RUN_ARCHIVE      → scripts/validate_run_archive.py (Layer 4)

Truthy values (case-insensitive): "1", "true", "yes", "on".

Semantics:

  * The disable is intentionally a noop+exit-0 — NOT a silent skip
    embedded in a longer pipeline. This makes it impossible to miss in
    a `set -x` log: every disabled run prints
    `<layer>: DISABLED via FLEET_DISABLE_<NAME>=1 (no-op exit 0)` to
    stderr.

  * The disable applies to the CLI entrypoint only, not to the library
    functions. Library imports continue to work; tests that import
    `scripts.lib.verify_findings` directly are unaffected.

  * The convention is symmetric: setting the env var to "0" / "false" /
    "" leaves the layer enabled. Unset is also enabled.

Why a convention rather than a config file:

  Operators need to flip a single layer off for one run (e.g. during
  a comparator bench or to unblock an emergency). Env vars compose
  cleanly with `FLEET_DISABLE_*=1 fleet run ...` and don't leave
  persistent state behind. A config-file knob would require careful
  cleanup and would invite "I forgot to flip it back" footguns.

Reference: docs/external-dogfood/adversarial-bench-2026-06.md
methodology section; engine.md SUBSTRATE KILL-SWITCH CONVENTION block.
"""
from __future__ import annotations

import os
import sys
from typing import Final

_TRUTHY: Final = frozenset({"1", "true", "yes", "on"})


def is_truthy(value: str | None) -> bool:
    """Return True iff value is a recognized truthy string."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


def is_disabled(env_var: str) -> bool:
    """Return True iff the named env var is set to a truthy value.

    Args:
        env_var: One of FLEET_DISABLE_VERIFY_FINDINGS,
            FLEET_DISABLE_STOP_VERIFY, FLEET_DISABLE_BLIND_FIX,
            FLEET_DISABLE_RUN_ARCHIVE. (Other names are accepted; the
            helper doesn't enforce the registry — callers do.)
    """
    return is_truthy(os.environ.get(env_var))


def stop_verify_legacy_disabled() -> bool:
    """Layer 2 honors a legacy env var STOP_VERIFY_DISABLED in addition
    to FLEET_DISABLE_STOP_VERIFY. We keep both so existing operators'
    runbooks don't break when they re-pull the substrate."""
    return is_truthy(os.environ.get("STOP_VERIFY_DISABLED")) or is_disabled(
        "FLEET_DISABLE_STOP_VERIFY"
    )


def announce_disabled(layer_label: str, env_var: str) -> int:
    """Print the standardized disable notice and return exit code 0.

    Layers call this as their FIRST action in main(), before parsing
    args or touching disk:

        if is_disabled("FLEET_DISABLE_VERIFY_FINDINGS"):
            return announce_disabled("verify-findings", "FLEET_DISABLE_VERIFY_FINDINGS")

    The CLI returns 0 (success) so disabling a layer does NOT poison
    the calling pipeline. This is the explicit operator contract:
    "disabled" means "treat the substrate's verdict as PASS for this
    run". If you want the layer to fail closed instead, do not use
    the disable knob — fix the upstream problem.
    """
    print(
        f"{layer_label}: DISABLED via {env_var}=1 (no-op exit 0)",
        file=sys.stderr,
    )
    return 0


__all__ = [
    "announce_disabled",
    "is_disabled",
    "is_truthy",
    "stop_verify_legacy_disabled",
]
