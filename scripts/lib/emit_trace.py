"""Library for the trace-emission contract (Commit E).

Emits one JSONL line per state transition in the run ledger. The trace stream
is the dashboard contract: vibe-kanban, Claude Code Agent View, and custom
dashboards are interchangeable consumers. Schema is pinned at 1.0; the
companion file is
``skills/autonomous-fleet-core/assets/fleet-trace.schema.json``.

Layered like ``verify_findings`` / ``verify_blind_fix``:

- ``TraceEmitter`` — runtime emitter; opens ``<run_dir>/trace.jsonl`` for
  append and writes one event per ``emit()`` call.
- ``validate_event(event)`` — manual structural validator (no jsonschema
  dependency) returning a list of error messages.
- ``iter_trace_file(path)`` — generator over parsed events; tolerates
  malformed lines so a half-written trace from a crashed run is still
  partially renderable.

See ``skills/autonomous-fleet-core/references/engine.md`` § TRACE EMISSION for
the doctrine. The "every state transition that writes to the ledger MUST
emit a trace event before the ledger write commits" rule is enforced
behaviourally by ``tests/test_emit_trace.py``.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# Schema constants. Keep these in lockstep with fleet-trace.schema.json; the
# drift test in tests/test_emit_trace.py asserts they agree.
SCHEMA_VERSION = "1.0"

PRIMITIVES = (
    "SPAWN_WORKER",
    "DISPATCH",
    "WAIT",
    "INSPECT",
    "SYNC",
    "MERGE",
    "FREEZE",
    "T-FINAL",
    "GOAL_BLOCKED",
    "COMMIT",
    "ABORT",
)

ROLES = (
    "COORDINATOR",
    "BUILDER",
    "REVIEWER",
    "INTEGRATOR",
    "FIXER",
    "OTHER",
)

STATUSES = (
    "started",
    "succeeded",
    "failed",
    "blocked",
    "skipped",
)

_REQUIRED_FIELDS = (
    "schema_version",
    "ts",
    "run_id",
    "mission",
    "primitive",
    "role",
    "status",
)

_OPTIONAL_FIELDS = (
    "task_id",
    "evidence_hash",
    "cost_delta",
    "parent_event",
    "details",
)

_ALLOWED_FIELDS = frozenset(_REQUIRED_FIELDS + _OPTIONAL_FIELDS)

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
# MUST stay identical to fleet_run.RUN_ID_PATTERN (pinned by a drift test); kept as a
# literal here rather than imported to avoid a circular import (fleet_run imports this module).
_RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*[a-z0-9]-[0-9a-f]{6}$")
_EVIDENCE_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _utc_now_iso() -> str:
    """ISO 8601 UTC timestamp with the trailing Z (millisecond precision)."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


_SECRET_RE = re.compile(
    r"sk-[A-Za-z0-9]{16,}"
    r"|sk_(?:live|test)_[A-Za-z0-9]{16,}"          # Stripe
    r"|AKIA[0-9A-Z]{16}"                            # AWS access key id
    r"|gh[opusr]_[A-Za-z0-9]{30,}"                  # GitHub p/o/u/s/r tokens
    r"|xai-[A-Za-z0-9-]{16,}"                       # x.ai
    r"|xox[bpras]-[A-Za-z0-9-]{10,}"               # Slack
    r"|AIza[0-9A-Za-z_\-]{35}"                      # Google API key
    r"|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"  # JWT
    r"|Bearer\s+[A-Za-z0-9._\-]{20,}"              # bearer header
    r"|-----BEGIN[A-Z ]*PRIVATE KEY-----"
)
_HOST_PATH_RE = re.compile(
    r"(?:^|[\s\"'=:])/(?:home|Users|root|etc|var|opt)/|/\.(?:ssh|aws|gnupg)/"
)


def _scan_details(details: dict) -> list[str]:
    """Flag secrets / host-absolute paths in a free-form details payload.

    The trace stream is published to external dashboards, so engine.md TRACE EMISSION
    forbids secrets and host-absolute paths in details. This makes that rule enforced
    (validate_event + emit both call it), not prose.
    """
    out: list[str] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, str):
            if _SECRET_RE.search(value):
                out.append(f"details{path} looks like a secret; reference by evidence_hash")
            elif _HOST_PATH_RE.search(value):
                out.append(f"details{path} leaks a host-absolute path; use a repo-relative path")
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(v, f"{path}.{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{path}[{i}]")

    walk(details, "")
    return out


def validate_event(event: Any) -> list[str]:
    """Return a list of structural error messages for a candidate event.

    Empty list = valid. Mirrors fleet-trace.schema.json without depending on
    jsonschema; the drift test asserts the two stay in sync.
    """
    errors: list[str] = []
    if not isinstance(event, dict):
        return [f"event must be an object, got {type(event).__name__}"]

    for field in _REQUIRED_FIELDS:
        if field not in event:
            errors.append(f"missing required field: {field}")

    extra = set(event) - _ALLOWED_FIELDS
    for field in sorted(extra):
        errors.append(f"additionalProperties not allowed: {field}")

    if "schema_version" in event and event["schema_version"] != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, got "
            f"{event['schema_version']!r}"
        )

    ts = event.get("ts")
    if "ts" in event:
        if not isinstance(ts, str) or not _TS_RE.match(ts):
            errors.append(f"ts must be ISO 8601 UTC (trailing Z), got {ts!r}")

    run_id = event.get("run_id")
    if "run_id" in event:
        if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id):
            errors.append(f"run_id does not match archive pattern: {run_id!r}")

    mission = event.get("mission")
    if "mission" in event:
        if not isinstance(mission, str) or not mission:
            errors.append("mission must be a non-empty string")

    primitive = event.get("primitive")
    if "primitive" in event and primitive not in PRIMITIVES:
        errors.append(
            f"primitive must be one of {list(PRIMITIVES)}, got {primitive!r}"
        )

    role = event.get("role")
    if "role" in event and role not in ROLES:
        errors.append(f"role must be one of {list(ROLES)}, got {role!r}")

    status = event.get("status")
    if "status" in event and status not in STATUSES:
        errors.append(
            f"status must be one of {list(STATUSES)}, got {status!r}"
        )

    if "task_id" in event:
        task_id = event["task_id"]
        if not isinstance(task_id, str) or not task_id:
            errors.append("task_id must be a non-empty string when set")

    if "evidence_hash" in event:
        evidence_hash = event["evidence_hash"]
        if not isinstance(evidence_hash, str) or not _EVIDENCE_HASH_RE.match(
            evidence_hash
        ):
            errors.append(
                f"evidence_hash must be 64-char hex sha256, got {evidence_hash!r}"
            )

    if "cost_delta" in event:
        cost_delta = event["cost_delta"]
        if isinstance(cost_delta, bool) or not isinstance(
            cost_delta, (int, float)
        ):
            errors.append(
                f"cost_delta must be a non-negative number, got {cost_delta!r}"
            )
        elif cost_delta < 0:
            errors.append(
                f"cost_delta must be non-negative, got {cost_delta!r}"
            )

    if "parent_event" in event:
        parent_event = event["parent_event"]
        if not isinstance(parent_event, str) or not _UUID_RE.match(parent_event):
            errors.append(
                f"parent_event must be UUID-shaped, got {parent_event!r}"
            )

    if "details" in event:
        if not isinstance(event["details"], dict):
            errors.append("details must be an object when set")
        else:
            errors.extend(_scan_details(event["details"]))

    return errors


def iter_trace_file(path: Path) -> Iterator[dict]:
    """Yield parsed events from a trace.jsonl file.

    Tolerates malformed lines (logs them on the generator's ``skipped``
    attribute as a count). A half-written trace from a crashed run remains
    partially renderable; this matches the "trace failure is degraded
    telemetry, not a hard error" doctrine.
    """
    skipped = 0
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(event, dict):
                skipped += 1
                continue
            yield event
    iter_trace_file.last_skipped = skipped  # type: ignore[attr-defined]


def health_rollup(events) -> dict:
    """Summarize run health from a trace event stream."""
    rollup: dict[str, Any] = {
        "total": 0,
        "succeeded": 0,
        "failed": 0,
        "blocked": 0,
        "skipped": 0,
        "last_failure": None,
    }
    for event in events:
        rollup["total"] += 1
        status = event.get("status")
        if status in {"succeeded", "failed", "blocked", "skipped"}:
            rollup[status] += 1
        if status in {"failed", "blocked"}:
            failure = {
                "ts": event.get("ts"),
                "primitive": event.get("primitive"),
                "role": event.get("role"),
                "task_id": event.get("task_id"),
                "details": event.get("details"),
            }
            last_failure = rollup["last_failure"]
            if last_failure is None or str(failure["ts"] or "") >= str(
                last_failure["ts"] or ""
            ):
                rollup["last_failure"] = failure
    return rollup


class TraceEmitter:
    """Append-only JSONL emitter for one run's trace stream.

    The emitter is opened in append mode so multiple coordinators in the
    same run share one stream without truncation. ``emit()`` writes one
    line, flushes, and returns the event dict so callers can attach the
    event to the ledger row.
    """

    def __init__(self, run_dir: Path, *, mission: str, run_id: str) -> None:
        self._run_dir = Path(run_dir)
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._run_dir / "trace.jsonl"
        self._mission = mission
        self._run_id = run_id
        self._fh = self._path.open("a", encoding="utf-8")

    @property
    def path(self) -> Path:
        return self._path

    def emit(
        self,
        primitive: str,
        role: str,
        status: str,
        *,
        task_id: str | None = None,
        evidence_hash: str | None = None,
        cost_delta: float | None = None,
        details: dict | None = None,
        parent_event: str | None = None,
    ) -> dict:
        """Write one event, flush, and return the event dict.

        The line is built then written-and-flushed in one call so partial
        lines never reach disk; this is the atomicity invariant guarded by
        the ``trace-emit-atomicity-off`` mutation.
        """
        event: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "ts": _utc_now_iso(),
            "run_id": self._run_id,
            "mission": self._mission,
            "primitive": primitive,
            "role": role,
            "status": status,
        }
        if task_id is not None:
            event["task_id"] = task_id
        if evidence_hash is not None:
            event["evidence_hash"] = evidence_hash
        if cost_delta is not None:
            event["cost_delta"] = cost_delta
        if parent_event is not None:
            event["parent_event"] = parent_event
        if details is not None:
            event["details"] = details

        if details is not None:
            violations = _scan_details(details)
            if violations:
                raise ValueError("; ".join(violations))
        line = json.dumps(event, sort_keys=True) + "\n"
        self._fh.write(line)
        self._fh.flush()
        return event

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "TraceEmitter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
