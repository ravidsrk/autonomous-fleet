"""Adapter requires-block loader and intent-keyed preflight checks."""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REQUIRES_BLOCK_RE = re.compile(
    r"```(?:yaml|yml)\s+requires\s*\n(?P<body>.*?)^```",
    re.MULTILINE | re.DOTALL,
)

# Auth probes must not hang forever (OPS-002 / PREFLIGHT-01). Override via
# FLEET_ADAPTER_AUTH_TIMEOUT_S (seconds); non-positive or invalid values fall
# back to the default.
DEFAULT_AUTH_TIMEOUT_S = 30.0
_AUTH_TIMEOUT_ENV = "FLEET_ADAPTER_AUTH_TIMEOUT_S"


def _auth_timeout_s(environ: Mapping[str, str] = os.environ) -> float:
    raw = environ.get(_AUTH_TIMEOUT_ENV)
    if raw is None or raw == "":
        return DEFAULT_AUTH_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_AUTH_TIMEOUT_S
    if value <= 0:
        return DEFAULT_AUTH_TIMEOUT_S
    return value


@dataclass(frozen=True)
class Intent:
    """Caller intent that decides whether SCM/PR-write checks are required."""

    scm: bool = False
    wiring_only: bool = False


def load_requires(adapter_dir: str | Path) -> dict[str, Any]:
    """Load the fenced ``yaml requires`` block from an adapter ``SKILL.md``."""
    skill_path = Path(adapter_dir) / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    match = _REQUIRES_BLOCK_RE.search(text)
    if not match:
        raise ValueError(f"{skill_path}: missing fenced yaml requires-block")
    data = yaml.safe_load(match.group("body")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{skill_path}: requires-block must be a YAML mapping")
    return data


def _scm_enabled(intent: Intent | Mapping[str, Any]) -> bool:
    if isinstance(intent, Intent):
        return intent.scm
    return bool(intent.get("scm", False))


def _wiring_only(intent: Intent | Mapping[str, Any]) -> bool:
    if isinstance(intent, Intent):
        return intent.wiring_only
    return bool(intent.get("wiring_only", False))


def _active_intent(intent: Intent | Mapping[str, Any]) -> str:
    return "scm" if _scm_enabled(intent) else "no_scm"


def _first_command_token(command: str) -> str | None:
    parts = shlex.split(command)
    return parts[0] if parts else None


def _bins_skipped_by_intent(requires: Mapping[str, Any], intent_name: str) -> set[str]:
    skipped: set[str] = set()
    for entry in requires.get("auth") or []:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("skip_if_intent") == intent_name:
            token = _first_command_token(entry.get("check", ""))
            if token:
                skipped.add(token)
    return skipped


def activity_hooks_advisory(requires: Mapping[str, Any]) -> str | None:
    """Return a coordinator note when the adapter installs an activity-hook pipeline."""
    if requires.get("activity_hooks") is True:
        return (
            "activity_hooks: INSPECT must treat >90s post-spawn silence as no_signal "
            "(see ao-adoptions.md AO MECHANISMS; verify_hook_signal.py)"
        )
    return None


def check(
    requires: Mapping[str, Any],
    intent: Intent | Mapping[str, Any],
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
    environ: Mapping[str, str] = os.environ,
) -> list[str]:
    """Return all preflight failures for ``requires`` under ``intent``.

    SCM-gated auth commands, and their command binary (for example ``gh``), are
    skipped when the caller did not request SCM/PR-write intent. The command
    runner is injectable so tests never need to invoke real host auth.
    """
    if _wiring_only(intent):
        return []

    intent_name = _active_intent(intent)
    skipped_bins = _bins_skipped_by_intent(requires, intent_name)
    failures: list[str] = []

    for binary in requires.get("bins") or []:
        if binary in skipped_bins:
            continue
        if which(binary) is None:
            failures.append(f"missing required binary: {binary}")

    for env_name in requires.get("env") or []:
        if not environ.get(env_name):
            failures.append(f"missing required env var: {env_name}")

    for entry in requires.get("auth") or []:
        if not isinstance(entry, Mapping):
            failures.append(f"malformed auth entry (expected mapping): {entry!r}")
            continue
        command = entry.get("check")
        if not command:
            failures.append(f"malformed auth entry (missing 'check'): {entry!r}")
            continue
        if entry.get("skip_if_intent") == intent_name:
            continue
        timeout_s = _auth_timeout_s(environ)
        try:
            result = run(
                shlex.split(command),
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            failures.append(
                f"auth check timed out after {timeout_s:g}s: {command}"
            )
            continue
        if result.returncode != 0:
            failures.append(f"auth check failed ({result.returncode}): {command}")

    return failures
