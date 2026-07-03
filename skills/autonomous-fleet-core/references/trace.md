# Trace

<!-- demoted from engine.md (issue #84) -->
═══════════════════════════════════════════════════════════
TRACE EMISSION — the dashboard contract (vibe-kanban, Agent View, custom).
═══════════════════════════════════════════════════════════
The trace stream is ONE JSONL line per state transition in the ledger, written to
`.fleet/runs/<run_id>/trace.jsonl`. The schema (`assets/fleet-trace.schema.json`, pinned at
`schema_version: "1.0"`) is the CONTRACT: vibe-kanban, Claude Code Agent View, and custom dashboards
are interchangeable consumers — owning the format, not the renderer, is what keeps live observability
free of UI debt. Landscape Gap 8 ("no live dashboard") is closed by emitting the stream and letting
existing readers render it, not by building a GUI.
- Every state transition that writes to the ledger SHOULD emit a trace event BEFORE the ledger
  write commits (trace first, ledger second) so a crashed coordinator rarely leaves a row with no
  externally-visible cause. AUTHORITY: the LEDGER is the authoritative loop state; the trace is
  best-effort causal TELEMETRY. (These were previously stated the other way around in this block
  while the failure-handling bullet below made emission fail-soft — an internal contradiction,
  issue #85. Telemetry that can be skipped on I/O error cannot be a source of truth.)
- The mechanism is the `emit_trace.TraceEmitter` library, which the coordinator and each adapter call
  at every transition; `fleet_run.write_manifest(..., emitter=...)` is the reference in-code
  integration (it emits the `T-FINAL` archive transition, test + mutation covered). Enforcement is the
  schema + `emit_trace.validate_event` + the schema-drift test + the trace mutations, NOT auto-wiring,
  because the file ledger is coordinator-driven.
- CAUSAL LINEAGE: `emit()` stamps every event with a unique `id` and RETURNS it; a worker's
  `COMMIT`/`INSPECT`/`WORKER_DONE` MUST set `parent_event` to that worker's `SPAWN_WORKER` id, so a
  consumer can reconstruct one worker's lifeline. `fleet_run` wires the reference SPAWN→COMMIT edge;
  `id` is optional in the schema (non-breaking) but always generated.
- The `details` object is free-form but MUST NOT carry secrets or host-absolute paths; reference
  sensitive evidence by `evidence_hash`. The stream is meant for publication to external dashboards.
- Schema is versioned (`schema_version: "1.0"`) and breaking changes require a NEW `$id`; consumers
  pin to the version they understand. Adding a primitive, role, or status to the enum is a breaking
  change for the same reason — closed enums are part of the contract.
- The trace `primitive`/`role` enums are trace-specific vocabulary — overlapping with, but NOT
  identical to, the 13 coordinator PRIMITIVES (engine.md). The trace records ledger state-transition verbs the
  coordinator does not dispatch (`SYNC`, `MERGE`, `FREEZE`, `T-FINAL`, `COMMIT`, `ABORT`) and a
  `FIXER` role (the blind-fix author), and omits coordinator-only primitives the trace never emits
  (e.g. `PLACE`, `WORKER_DONE`, `OPEN_PR`, `CLEANUP`, `LOOP_POLL`). Neither list is a subset of the
  other; the 13-primitive coordinator list in engine.md's PRIMITIVES section is unchanged.
- Failure to emit a trace event is NOT a hard error. The run continues with degraded telemetry; the
  coordinator records `trace_emission_degraded: true` in `fleet-outcome.yaml` so the post-hoc audit
  knows the stream is incomplete. Hard-failing on a telemetry I/O error would let the dashboard veto
  real work, which inverts the dependency.
