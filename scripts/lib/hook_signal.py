"""Hook-signal health grace (Agent Orchestrator ``no_signal`` port).

When an adapter installs an activity-hook pipeline, prolonged silence after
spawn/restore must not be reported as confident ``idle``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HOOK_SIGNAL_GRACE_SECONDS = 90

Event = dict[str, Any]

_SPAWN_STATUSES = frozenset({"started", "succeeded"})


def _task_id(event: Event) -> str | None:
    """Return task id from top-level trace field or ``details.task_id``."""
    top = event.get("task_id")
    if isinstance(top, str) and top:
        return top
    details = event.get("details") or {}
    nested = details.get("task_id")
    if isinstance(nested, str) and nested:
        return nested
    return None


def _parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def first_hook_signal_at(
    events: list[Event],
    *,
    before: datetime | None = None,
) -> datetime | None:
    """Return timestamp of the first hook/activity callback event, if any."""
    for event in events:
        ts = _parse_ts(event["ts"])
        if before is not None and ts > before:
            continue
        details = event.get("details") or {}
        if details.get("hook_callback") is True or details.get("activity_state"):
            return ts
    return None


def spawn_or_restore_at(events: list[Event], task_id: str | None = None) -> datetime | None:
    """Return spawn/restore timestamp for a worker task."""
    for event in events:
        if event.get("primitive") not in {"SPAWN_WORKER", "CONTINUE_WORKER"}:
            continue
        if task_id and _task_id(event) != task_id:
            continue
        if event.get("status") in _SPAWN_STATUSES:
            return _parse_ts(event["ts"])
    return None


def derive_signal_status(
    *,
    spawn_at: datetime,
    now: datetime,
    first_signal_at: datetime | None,
    hook_capable: bool,
) -> str:
    """Return working | idle | no_signal for a hook-capable harness."""
    if not hook_capable:
        return "idle"
    if first_signal_at is not None:
        return "idle"
    elapsed = (now - spawn_at).total_seconds()
    if elapsed > HOOK_SIGNAL_GRACE_SECONDS:
        return "no_signal"
    return "idle"


def verify_hook_signal_trace(
    events: list[Event],
    *,
    hook_capable: bool = True,
) -> list[str]:
    """Return errors when INSPECT claims idle despite a broken hook pipeline."""
    if not hook_capable:
        return []

    errors: list[str] = []
    task_ids = {tid for event in events if (tid := _task_id(event))}

    for task_id in sorted(task_ids):
        spawn_at = spawn_or_restore_at(events, task_id)
        if spawn_at is None:
            continue
        task_events = [e for e in events if _task_id(e) == task_id]

        for event in events:
            if event.get("primitive") != "INSPECT":
                continue
            if _task_id(event) != task_id:
                continue
            details = event.get("details") or {}
            reported = details.get("signal_state") or details.get("worker_state")
            if reported is None:
                continue
            inspect_at = _parse_ts(event["ts"])
            first_signal = first_hook_signal_at(task_events, before=inspect_at)
            at_inspect = derive_signal_status(
                spawn_at=spawn_at,
                now=inspect_at,
                first_signal_at=first_signal,
                hook_capable=True,
            )
            if at_inspect == "no_signal" and reported in {"idle", "working"}:
                errors.append(
                    f"{task_id}: INSPECT reported {reported!r} at {event['ts']} "
                    f"but hook pipeline had no signal (expected no_signal)"
                )
    return errors