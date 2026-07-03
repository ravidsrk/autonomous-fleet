"""Persisted PR-feedback nudge dedup (Agent Orchestrator ``sendOnce`` port).

The coordinator records dedup state in ``nudge-state.json`` so CI/review/conflict
nudges are not re-sent for unchanged evidence across polls or coordinator resumes.
Pure library — no I/O.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = "1.0"
REQUIRED_FIELDS = ("schema_version", "pr_url", "entries")
_ALLOWED_ENTRY_KINDS = frozenset({"ci", "review", "merge_conflict", "ao_review"})
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_DEFAULT_REVIEW_MAX = 3

Entry = dict[str, Any]
State = dict[str, Any]


def validate_nudge_state(record: Any, label: str = "nudge-state") -> list[str]:
    """Return schema errors for one nudge-state record."""
    if not isinstance(record, dict):
        return [f"{label}: top-level must be an object, got {type(record).__name__}"]

    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"{label}: missing required field '{field}'")

    if record.get("schema_version") not in (None, SCHEMA_VERSION):
        errors.append(f"{label}: schema_version must be '1.0', got {record.get('schema_version')!r}")

    pr_url = record.get("pr_url")
    if pr_url is not None and (not isinstance(pr_url, str) or not pr_url.strip()):
        errors.append(f"{label}: pr_url must be a non-empty string")

    entries = record.get("entries")
    if entries is not None:
        if not isinstance(entries, list):
            errors.append(f"{label}: entries must be an array")
        else:
            for idx, entry in enumerate(entries):
                errors.extend(_validate_entry(entry, f"{label}.entries[{idx}]"))

    extra = sorted(set(record) - {*REQUIRED_FIELDS, "updated_at"})
    for field in extra:
        errors.append(f"{label}: additional property not allowed: '{field}'")

    return errors


def _validate_entry(entry: Any, label: str) -> list[str]:
    if not isinstance(entry, dict):
        return [f"{label}: must be an object, got {type(entry).__name__}"]

    errors: list[str] = []
    for field in ("key", "kind", "signature", "attempts"):
        if field not in entry:
            errors.append(f"{label}: missing required field '{field}'")

    kind = entry.get("kind")
    if kind is not None and kind not in _ALLOWED_ENTRY_KINDS:
        errors.append(
            f"{label}: kind must be one of {sorted(_ALLOWED_ENTRY_KINDS)}, got {kind!r}"
        )

    sig = entry.get("signature")
    if sig is not None and (not isinstance(sig, str) or not sig):
        errors.append(f"{label}: signature must be a non-empty string")

    attempts = entry.get("attempts")
    if attempts is not None and (not isinstance(attempts, int) or attempts < 0):
        errors.append(f"{label}: attempts must be a non-negative integer")

    commit_sha = entry.get("commit_sha")
    if commit_sha is not None and (
        not isinstance(commit_sha, str) or not _SHA_RE.match(commit_sha)
    ):
        errors.append(f"{label}: commit_sha must be a 40-hex git SHA when present")

    max_attempts = entry.get("max_attempts")
    if max_attempts is not None and (not isinstance(max_attempts, int) or max_attempts < 0):
        errors.append(f"{label}: max_attempts must be a non-negative integer when present")

    extra = sorted(set(entry) - {"key", "kind", "signature", "attempts", "commit_sha", "max_attempts"})
    for field in extra:
        errors.append(f"{label}: additional property not allowed: '{field}'")

    return errors


def should_send_nudge(
    state: State,
    *,
    key: str,
    signature: str,
    kind: str,
    max_attempts: int | None = None,
) -> bool:
    """Return True when a nudge with ``key``/``signature`` may be sent."""
    if max_attempts is None:
        max_attempts = _DEFAULT_REVIEW_MAX if kind in {"review", "ao_review"} else 0

    for entry in state.get("entries") or []:
        if entry.get("key") != key:
            continue
        if entry.get("signature") == signature:
            return False
        attempts = int(entry.get("attempts") or 0)
        if max_attempts > 0 and attempts >= max_attempts:
            return False
        return True
    return True


def record_nudge(
    state: State,
    *,
    key: str,
    kind: str,
    signature: str,
    commit_sha: str | None = None,
    max_attempts: int | None = None,
) -> State:
    """Return updated state after recording one sent nudge."""
    if max_attempts is None:
        max_attempts = _DEFAULT_REVIEW_MAX if kind in {"review", "ao_review"} else 0

    entries: list[Entry] = list(state.get("entries") or [])
    updated = False
    for entry in entries:
        if entry.get("key") != key:
            continue
        entry["kind"] = kind
        entry["signature"] = signature
        entry["attempts"] = int(entry.get("attempts") or 0) + 1
        if commit_sha:
            entry["commit_sha"] = commit_sha
        if max_attempts:
            entry["max_attempts"] = max_attempts
        updated = True
        break

    if not updated:
        new_entry: Entry = {
            "key": key,
            "kind": kind,
            "signature": signature,
            "attempts": 1,
        }
        if commit_sha:
            new_entry["commit_sha"] = commit_sha
        if max_attempts:
            new_entry["max_attempts"] = max_attempts
        entries.append(new_entry)

    return {**state, "entries": entries}


def verify_nudge_state_invariants(state: State) -> list[str]:
    """Return enforcement errors for dedup invariants on a validated state."""
    errors: list[str] = []
    schema_errors = validate_nudge_state(state)
    if schema_errors:
        return schema_errors

    seen_keys: set[str] = set()
    for idx, entry in enumerate(state.get("entries") or []):
        key = entry["key"]
        if key in seen_keys:
            errors.append(f"nudge-state.entries[{idx}]: duplicate key {key!r}")
        seen_keys.add(key)

        max_attempts = entry.get("max_attempts")
        if max_attempts is None:
            max_attempts = _DEFAULT_REVIEW_MAX if entry["kind"] in {"review", "ao_review"} else 0
        if max_attempts > 0 and int(entry["attempts"]) > max_attempts:
            errors.append(
                f"nudge-state.entries[{idx}]: attempts {entry['attempts']} exceed "
                f"max_attempts {max_attempts} for key {key!r}"
            )

    return errors