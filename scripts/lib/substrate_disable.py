"""Substrate kill-switch convention — helper API.

Each verification-substrate layer exposes a `FLEET_DISABLE_*` env var that, when
set truthy (case-insensitive "1"/"true"/"yes"/"on"), makes the layer's CLI early-
exit 0 with a one-line stderr notice. The disable applies to the CLI entrypoint
only — library imports are unaffected. One knob per layer, no legacy aliases (the
stale `STOP_VERIFY_DISABLED` name is NOT honored — delete on sight if seen).

This module is the helper API (`is_disabled` / `announce_disabled` / the env-var
registry). The full doctrine — registry, semantics, rationale, bench-comparator
use — lives in `references/substrate-disable-knobs.md` (single source of truth).
Keep this docstring an API summary, not a second copy.
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
]
