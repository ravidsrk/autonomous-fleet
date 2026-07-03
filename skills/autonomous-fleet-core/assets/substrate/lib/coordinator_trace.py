"""Resolve run context and emit live coordinator trace events.

Live coordinators and adapters call ``emit_trace.py emit`` (or this library)
at every ledger transition *before* writing the ledger row. Dry-run and
headless paths reconstruct traces from progress docs; this module is the
live-run counterpart.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .emit_trace import TraceEmitter, validate_event

_RUN_ID_RE = re.compile(
    r"^[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*[a-z0-9]-[0-9a-f]{6}$"
)


def resolve_run_context(
    run_dir: Path,
    *,
    mission: str | None = None,
    run_id: str | None = None,
) -> tuple[str, str]:
    """Return (mission, run_id) for a run archive directory."""
    if mission and run_id:
        return mission, run_id

    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read manifest: {manifest_path}: {exc}") from exc
        m = data.get("mission")
        r = data.get("run_id")
        if isinstance(m, str) and m and isinstance(r, str) and r:
            return m, r

    name = run_dir.name
    if _RUN_ID_RE.match(name):
        m = re.match(
            r"^[0-9]{8}T[0-9]{6}Z-(.+)-[0-9a-f]{6}$",
            name,
        )
        if m:
            mission_guess = m.group(1)
            return mission or mission_guess, run_id or name

    raise ValueError(
        "run_dir has no manifest.json and name is not a run_id; "
        "pass --mission and --run-id"
    )


def emit_coordinator_event(
    run_dir: Path,
    *,
    primitive: str,
    role: str,
    status: str,
    mission: str | None = None,
    run_id: str | None = None,
    task_id: str | None = None,
    evidence_hash: str | None = None,
    cost_delta: float | None = None,
    parent_event: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Append one trace event and return its id."""
    resolved_mission, resolved_run_id = resolve_run_context(
        run_dir, mission=mission, run_id=run_id
    )
    with TraceEmitter(
        run_dir,
        mission=resolved_mission,
        run_id=resolved_run_id,
    ) as emitter:
        return emitter.emit(
            primitive,
            role,
            status,
            task_id=task_id,
            evidence_hash=evidence_hash,
            cost_delta=cost_delta,
            parent_event=parent_event,
            details=details,
        )