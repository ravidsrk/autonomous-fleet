"""Pure SHA-PIN enforcement for fleet reviewer approvals.

Reviewers pin the branch HEAD they inspected in ``sha-pin.json``. This module
validates that record shape and compares approved pins against caller-supplied
branch heads. It intentionally performs no filesystem or git operations; the CLI
is responsible for loading records and resolving branch heads.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

SCHEMA_VERSION = "1.0"
REQUIRED_FIELDS = ("schema_version", "review_id", "reviewed_sha", "branch", "verdict")
ALLOWED_FIELDS = frozenset({*REQUIRED_FIELDS, "merged"})
ENFORCED_VERDICTS = frozenset({"approve", "PASS"})
VALID_VERDICTS = frozenset({"approve", "PASS", "request_changes", "partial", "fail", "FAIL"})

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_REVIEW_ID_RE = re.compile(r"^[a-zA-Z0-9._/-]+$")
_BRANCH_RE = re.compile(r"^[a-zA-Z0-9._/-]+$")


def validate_sha_pin_record(record: Any, label: str = "sha-pin") -> list[str]:
    """Return schema errors for one sha-pin record."""
    if not isinstance(record, dict):
        return [f"{label}: top-level must be an object, got {type(record).__name__}"]

    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"{label}: missing required field '{field}'")

    extra = sorted(set(record) - ALLOWED_FIELDS)
    for field in extra:
        errors.append(f"{label}: additional property not allowed: '{field}'")

    schema_version = record.get("schema_version")
    if schema_version not in (None, SCHEMA_VERSION):
        errors.append(f"{label}: schema_version must be '1.0', got {schema_version!r}")

    review_id = record.get("review_id")
    if review_id is not None and (
        not isinstance(review_id, str) or not _REVIEW_ID_RE.match(review_id)
    ):
        errors.append(f"{label}: review_id must match ^[a-zA-Z0-9._/-]+$, got {review_id!r}")

    reviewed_sha = record.get("reviewed_sha")
    if reviewed_sha is not None and (
        not isinstance(reviewed_sha, str) or not _SHA_RE.match(reviewed_sha)
    ):
        errors.append(f"{label}: reviewed_sha must be a 40-hex git SHA, got {reviewed_sha!r}")

    branch = record.get("branch")
    if branch is not None and (
        not isinstance(branch, str) or not _BRANCH_RE.match(branch)
    ):
        errors.append(f"{label}: branch must match ^[a-zA-Z0-9._/-]+$, got {branch!r}")

    verdict = record.get("verdict")
    if verdict is not None and verdict not in VALID_VERDICTS:
        errors.append(f"{label}: verdict must be one of {sorted(VALID_VERDICTS)}, got {verdict!r}")

    merged = record.get("merged")
    if merged is not None and type(merged) is not bool:
        errors.append(f"{label}: merged must be boolean, got {type(merged).__name__}")

    return errors


def verify_sha_pin(
    records: list[dict[str, Any]],
    head_resolver: Callable[[str], str | None],
) -> list[str]:
    """Return enforcement errors for approved sha-pin records.

    ``head_resolver`` is injected so this function stays hermetic. It returns a
    branch's current HEAD SHA, or ``None`` when the branch is unknown/deleted.
    """
    errors: list[str] = []
    for idx, record in enumerate(records):
        label = f"sha-pin[{idx}]"
        schema_errors = validate_sha_pin_record(record, label)
        if schema_errors:
            errors.extend(schema_errors)
            continue

        if record["verdict"] not in ENFORCED_VERDICTS:
            continue

        branch = record["branch"]
        reviewed_sha = record["reviewed_sha"]
        head = head_resolver(branch)
        if head is None:
            if record.get("merged") is True:
                continue
            errors.append(
                f"{branch}: HEAD unknown for reviewed {reviewed_sha} and no merged marker; "
                "cannot enforce SHA-pin"
            )
            continue

        if reviewed_sha.lower() != head.lower():
            errors.append(
                f"{branch} moved {reviewed_sha}..{head}: REVIEWED is OUTDATED, force re-review"
            )

    return errors
