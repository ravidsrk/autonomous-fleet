# Vibe Kanban Trace Integration

Status: planned Commit E external-dogfood integration note. This document
describes the checked-in trace contract that vibe-kanban, Agent View, or a
custom dashboard can consume. It does not claim that a dashboard adapter is
already checked in.

## Trace Stream

Fleet runs write one JSONL event per ledger state transition to:

```text
.fleet/runs/<run_id>/trace.jsonl
```

Each line is one JSON object validated by
`skills/autonomous-fleet-core/assets/fleet-trace.schema.json`. The schema is
pinned at `schema_version: "1.0"` and has `$id`
`https://autonomous-fleet.dev/schemas/fleet-trace.schema.json`.

The required top-level fields are:

- `schema_version` - currently the constant string `"1.0"`
- `ts` - UTC ISO 8601 timestamp with trailing `Z`
- `run_id` - archive id shaped as `YYYYMMDDTHHMMSSZ-<mission>-<6-hex>`
- `mission` - mission slug
- `primitive` - one of `SPAWN_WORKER`, `DISPATCH`, `WAIT`, `INSPECT`, `SYNC`, `MERGE`, `FREEZE`, `T-FINAL`, `GOAL_BLOCKED`, `COMMIT`, `ABORT`
- `role` - one of `COORDINATOR`, `BUILDER`, `REVIEWER`, `INTEGRATOR`, `FIXER`, `OTHER`
- `status` - one of `started`, `succeeded`, `failed`, `blocked`, `skipped`

Optional top-level fields are:

- `task_id` - task identifier from the frozen DAG
- `evidence_hash` - 64-character lowercase hex SHA-256 digest
- `cost_delta` - non-negative numeric cost increment
- `parent_event` - UUID-shaped pointer to a prior event
- `details` - free-form object for renderer-specific or primitive-specific context

Consumers should treat `details` as best-effort display data only. Stable
dashboard behavior should be based on the typed top-level fields above.

## Emission And CLI

The append-only runtime emitter is `TraceEmitter` in
`scripts/lib/emit_trace.py`. It opens `<run_dir>/trace.jsonl`, writes one JSONL
line per `emit()` call, flushes immediately, and returns the event dict so the
coordinator can attach it to the ledger row. The engine doctrine requires the
trace event to land before the corresponding ledger write commits.

The checked-in CLI for the emitted stream is `scripts/emit_trace.py`:

```bash
python scripts/emit_trace.py validate .fleet/runs/<run_id>/trace.jsonl
python scripts/emit_trace.py summary .fleet/runs/<run_id>
```

`validate` checks every non-empty JSONL line against the schema-compatible
validator. `summary` reads `<run_dir>/trace.jsonl` and prints counts by
primitive, role, and status.

## Dashboard Consumption

For vibe-kanban, Agent View, or a custom dashboard:

1. Watch `.fleet/runs/*/trace.jsonl` for appended lines.
2. Parse each non-empty line as JSON.
3. Validate against `fleet-trace.schema.json` or mirror
   `scripts/lib/emit_trace.py::validate_event`.
4. Group by `run_id`, then order by `ts`.
5. Render lanes or timelines from `task_id`, `primitive`, `role`, and `status`.
6. Sum `cost_delta` per run when present.
7. Treat malformed lines as degraded telemetry, not as a run failure.

The schema is the integration boundary. A renderer can change without touching
the fleet run loop as long as it consumes the same JSONL contract.
