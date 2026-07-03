"""Hash-namespacing helpers for fleet branch and worktree placement.

The pure functions here keep run-specific branch/worktree suffixing in one
place. The CLI validator reads manifests and ledgers; this module only parses
in-memory data and returns errors.
"""
from __future__ import annotations

import re
from typing import Any

from .recovery_scan import parse_ledger_rows

_RUN_ID_RE = re.compile(
    r"^[0-9]{8}T[0-9]{6}Z-[a-z](?:[a-z0-9-]*[a-z0-9])?-(?P<short>[0-9a-f]{6})$"
)


def derive_run_short(run_id: str) -> str:
    """Return the 6-hex run suffix from a fleet run_id."""
    match = _RUN_ID_RE.match(run_id)
    if not match:
        raise ValueError(f"run_id must end with a 6-hex suffix, got {run_id!r}")
    return match.group("short")


def namespaced_branch(prefix: str, slug: str, run_id: str) -> str:
    """Return ``<prefix><slug>-<run_short>``."""
    return f"{prefix}{slug}-{derive_run_short(run_id)}"


def namespaced_worktree(repo: str, slug: str, run_id: str) -> str:
    """Return ``../<repo>-<slug>-<run_short>``."""
    return f"../{repo}-{slug}-{derive_run_short(run_id)}"


def progress_paths_from_manifest(
    manifest: Any, label: str = "manifest"
) -> tuple[str | None, list[str], list[str]]:
    """Extract the run_id and manifest-listed progress ledger paths."""
    if not isinstance(manifest, dict):
        return None, [], [f"{label}: manifest must be an object"]

    errors: list[str] = []
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str):
        errors.append(f"{label}: run_id must be a string")
    else:
        try:
            derive_run_short(run_id)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")

    files = manifest.get("files")
    if not isinstance(files, list):
        errors.append(f"{label}: files must be a list")
        return run_id if isinstance(run_id, str) else None, [], errors

    paths: list[str] = []
    for idx, entry in enumerate(files):
        if not isinstance(entry, dict):
            errors.append(f"{label}.files[{idx}]: file entry must be an object")
            continue
        if entry.get("kind") != "progress":
            continue
        path = entry.get("path")
        if isinstance(path, str) and path:
            paths.append(path)
        else:
            errors.append(f"{label}.files[{idx}]: progress entry path must be a string")
    return run_id if isinstance(run_id, str) else None, paths, errors


def validate_ledger_namespacing(
    run_id: str, ledger_text: str, label: str = "progress ledger"
) -> list[str]:
    """Return branch/worktree suffix errors for task rows in one ledger."""
    run_short = derive_run_short(run_id)
    suffix = f"-{run_short}"
    errors: list[str] = []
    for row in parse_ledger_rows(ledger_text):
        if row.branch and not row.branch.endswith(suffix):
            errors.append(
                f"{label}: TASK {row.task_id} branch {row.branch!r} must end with {suffix!r}"
            )
        wt_path = row.wt_path or row.flags.get("WORKTREE-PATH") or row.flags.get("WT-PATH")
        if wt_path and not wt_path.rstrip("/").endswith(suffix):
            errors.append(
                f"{label}: TASK {row.task_id} worktree {wt_path!r} must end with {suffix!r}"
            )
    return errors


def validate_archive_namespacing(
    manifest: Any,
    progress_ledgers: dict[str, str],
    label: str = "manifest",
) -> list[str]:
    """Validate manifest-listed progress ledgers against the manifest run_id."""
    run_id, paths, errors = progress_paths_from_manifest(manifest, label)
    if errors or run_id is None:
        return errors

    for path in paths:
        ledger_text = progress_ledgers.get(path)
        if ledger_text is None:
            errors.append(f"{path}: progress ledger not provided")
            continue
        errors.extend(validate_ledger_namespacing(run_id, ledger_text, label=path))
    return errors
