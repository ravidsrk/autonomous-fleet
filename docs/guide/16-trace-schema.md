<!-- title: Trace schema (v1) | description: The fleet-trace JSONL contract every dashboard consumes: fields, primitives, roles, statuses, the redaction rule, and what is emitted today. | sidebar_order: 16 -->

# Trace schema (v1)

**On this page:** [Why a trace stream](#why-a-trace-stream) · [Schema reference](#schema-reference) ·
[Primitive reference](#primitive-reference) · [Role and status enums](#role-and-status-enums) ·
[The `details` contract and the redaction rule](#the-details-contract-and-the-redaction-rule) ·
[What is emitted today vs the roadmap](#what-is-emitted-today-vs-the-roadmap) ·
[Versioning and the `$id` policy](#versioning-and-the-id-policy) ·
[Consumer guide: how to read the stream](#consumer-guide-how-to-read-the-stream) ·
[The vibe-kanban integration doc](#the-vibe-kanban-integration-doc)

The trace stream is how a dashboard sees a fleet run without reaching into the engine. It is one
append-only JSONL file per run, one line per state transition, with a schema that is the integration
boundary. vibe-kanban, Claude Code's Agent View, and a dashboard you write yourself are interchangeable
consumers: they read the same file, validate against the same schema, and render lanes or timelines from
the same typed fields. The framework owns the format. It does not own the renderer. That split is the
whole point, it is what keeps live observability free of UI debt.

This chapter is the reference for that format. Every field, every constraint, every enum value is taken
from the checked-in schema and the emitter library, not from memory. If you are building a dashboard,
this is your contract. If you are extending the engine, this is what your adapter must emit.

> The schema lives at `skills/autonomous-fleet-core/assets/fleet-trace.schema.json`. The runtime
> emitter and the dependency-free validator live at `scripts/lib/emit_trace.py`. A copy-pasteable
> example stream lives at `skills/autonomous-fleet-core/assets/fleet-trace.v1.example.jsonl`. When this
> chapter and those files disagree, the files win, and a schema-drift test
> (`tests/test_emit_trace.py`) keeps the emitter and the schema in lockstep.

## Why a trace stream

The engine writes a file-based ledger under `.fleet/runs/<run_id>/`. The ledger is derived state: it is
the answer to "what is the current shape of this run". The trace is the source of truth for "what
happened, in order". A dashboard wants the second thing. So the doctrine (see
[The engine](06-the-engine.md), TRACE EMISSION) is: every state transition that writes to the ledger
emits a trace event BEFORE the ledger write commits. Trace first, ledger second, never the reverse. If a
coordinator crashes mid-transition, you are left with a trace event whose ledger row never landed, which
is recoverable, instead of a ledger row with no externally-visible cause, which is not.

```text
   one fleet run
   ┌──────────────────────────────────────────────────────────┐
   │  state transition                                         │
   │     │                                                     │
   │     ▼                                                     │
   │  emit()  ──►  trace.jsonl  (append one line, flush)       │  ◄── dashboards read this
   │     │              │                                      │
   │     ▼              │ (trace first)                        │
   │  ledger write  ◄───┘ (ledger second, derived state)       │
   └──────────────────────────────────────────────────────────┘
```

The stream is published to external dashboards, which is why it carries a hard redaction rule (no
secrets, no host-absolute paths) that is enforced in code, not just documented. More on that below.

## Schema reference

The file is `fleet-trace.schema.json`, a JSON Schema draft 2020-12 document. The root is a single object
with `additionalProperties: false`, so an event carries exactly the fields below and nothing else. Seven
fields are required. Five are optional.

```text
required:  schema_version  ts  run_id  mission  primitive  role  status
optional:  task_id  evidence_hash  cost_delta  parent_event  details
```

Field by field. The constraint column is the literal constraint from the schema and the matching regex
or check in `validate_event`.

```text
field           req?  type     constraint
─────────────── ────  ───────  ───────────────────────────────────────────────────────────────
schema_version  yes   string   const "1.0". Any other value is rejected.
ts              yes   string   ISO 8601 UTC with a trailing Z. Local times are REJECTED.
run_id          yes   string   ^[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*-[0-9a-f]{6}$
mission         yes   string   minLength 1. MUST match the slug embedded in run_id.
primitive       yes   string   one of the 11 primitives (closed enum).
role            yes   string   one of the 6 roles (closed enum).
status          yes   string   one of the 5 statuses (closed enum).
task_id         no    string   minLength 1 when present. Task id from the frozen DAG.
evidence_hash   no    string   ^[0-9a-f]{64}$  (lowercase hex SHA-256).
cost_delta      no    number   minimum 0. Non-negative cost increment, USD by convention.
parent_event    no    string   UUID-shaped pointer to a prior event.
details         no    object   free-form; see the redaction rule below.
```

A few constraints are worth calling out because dashboards trip over them:

The `ts` regex is `^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$`. Fractional
seconds are allowed. A timezone offset like `+05:30` is not, because the whole point is that a dashboard
can sort across runs from different machines without doing timezone arithmetic. The emitter itself writes
whole-second precision (`_utc_now_iso()` drops microseconds), so in practice you will see
`2026-06-23T00:07:00Z`.

The `run_id` regex pins the archive layout: `YYYYMMDDTHHMMSSZ-<mission>-<6-hex>`, for example
`20260623T000000Z-doc-sync-abc123`. The `mission` field MUST match the `<mission>` slug inside that id.
The emitter enforces this by construction: it is constructed with `run_id` and `mission` and stamps both
onto every event, so they cannot drift apart within a run.

The `cost_delta` check is stricter in the validator than the bare JSON Schema implies. `validate_event`
rejects a boolean even though `true` is technically a JSON number-adjacent value in some readers, and it
rejects anything below zero. Total run cost is the sum of `cost_delta` across events, so a negative delta
would corrupt the total.

Here is a single well-formed event, every field populated, copy-pasteable:

```json
{
  "schema_version": "1.0",
  "ts": "2026-06-23T00:07:00Z",
  "run_id": "20260623T000000Z-doc-sync-abc123",
  "mission": "doc-sync",
  "primitive": "T-FINAL",
  "role": "INTEGRATOR",
  "status": "succeeded",
  "task_id": "task-04",
  "evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "cost_delta": 0.42,
  "parent_event": "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
  "details": { "manifest": "manifest.json", "files": 7 }
}
```

When serialized to the trace file, keys are sorted and there is no indentation: one event is one line.
`TraceEmitter.emit()` writes `json.dumps(event, sort_keys=True) + "\n"`, so the on-disk form of the event
above is a single line with keys in alphabetical order.

## Primitive reference

The `primitive` enum is closed. Adding a primitive is a breaking change (it widens the contract a
consumer pinned against), so a new primitive requires a doctrine update first, then a schema bump. The 11
primitives, in the order they appear in the schema enum and the emitter's `PRIMITIVES` tuple:

```text
primitive      what the transition marks
───────────── ─────────────────────────────────────────────────────────────────────────────
SPAWN_WORKER   A worker process is being started in its own terminal / task slot.
DISPATCH       Work is handed to a worker (the task is assigned and the worker is told to go).
WAIT           The coordinator is blocking on a worker, a lock, or an external signal.
INSPECT        A poll or read of worker / ledger / external state (one observation, not a decision).
SYNC           Reconciling observed signals into a single decision (signal reconciliation).
MERGE          Integrating a worker's unit of work (the PR-shaped merge step).
FREEZE         Freezing a plan or a file boundary so it cannot change underneath the run.
T-FINAL        The terminal archive transition: the run-archive manifest is being written.
GOAL_BLOCKED   The run cannot make progress toward its goal and is surfacing that, not pretending.
COMMIT         A worker's construction is committed (its artifacts are finalized in its slot).
ABORT          A worker or the run is aborting (the inverse terminal of COMMIT).
```

Notes that matter when you render these:

`SYNC` is not the same as `INSPECT`. `INSPECT` is one observation. `SYNC` is the decision made from a set
of observations. A single poll is not a decision, which is why the engine separates them (see
[The engine](06-the-engine.md), signal reconciliation). On a timeline, expect several `INSPECT` events to
precede one `SYNC`.

`COMMIT` and `ABORT` are the two terminals of a worker's construction lifetime. `T-FINAL` is the terminal
of the whole run's archive write. They are different scopes: a run has many `COMMIT`/`ABORT` events (one
per worker) but the run-archive `T-FINAL` is the one that fires when the manifest is sealed.

`GOAL_BLOCKED` is a first-class primitive, not an error. The framework surfaces "I cannot get there from
here" as a normal transition with `status: blocked`, because hiding it would be the dishonest move.

## Role and status enums

Both enums are closed for the same reason the primitive enum is: a consumer pins against them.

```text
role           who is acting at the transition
───────────── ─────────────────────────────────────────────────────────────────────────────
COORDINATOR    The run loop itself: dispatching, polling, reconciling, deciding.
BUILDER        A worker producing artifacts (the unit of work).
REVIEWER       A build-blind reviewer checking a builder's output.
INTEGRATOR     The role that merges and seals (T-FINAL is emitted as INTEGRATOR).
FIXER          A worker patching a finding raised by review.
OTHER          The escape hatch for orchestrator-only events with no human-shaped role.
```

```text
status      meaning
─────────── ──────────────────────────────────────────────────────────────
started     The primitive's transition has begun.
succeeded   The primitive completed and its postcondition holds.
failed      The primitive ran and did not achieve its postcondition.
blocked     The primitive cannot proceed (e.g. GOAL_BLOCKED, a held lock).
skipped     The primitive was intentionally not run for this transition.
```

`OTHER` exists so the engine never has to invent a fake human role for a purely mechanical event. Do not
read meaning into the absence of a builder/reviewer/integrator label; `OTHER` means "no human-shaped role
applies", not "unknown".

The example stream at `skills/autonomous-fleet-core/assets/fleet-trace.v1.example.jsonl` is a deliberate
enum-coverage fixture: it walks every primitive paired with every role and every status so the schema and
the validator are exercised across the full matrix. It is NOT a recording of a real run, do not infer
real-world ordering or real `status` values from it. For example, that fixture pairs `T-FINAL` with
`status: failed`, which is a coverage cell, not a thing production emits (production emits `T-FINAL` /
`INTEGRATOR` / `succeeded`, as shown in the next section).

## The `details` contract and the redaction rule

`details` is a free-form object. Consumers MUST treat it as best-effort display data and MUST NOT depend
on any specific shape inside it. The schema says so (`additionalProperties: true` on `details`, with the
description "Consumers MUST NOT depend on any specific shape here"), and the integration doc says so. If a
field inside `details` becomes load-bearing for a dashboard, the correct move is to promote it to a typed
top-level property under a new schema `$id`, not to start parsing `details`.

The redaction rule is the part that is enforced, not merely written down. Because the stream is published
to external dashboards, `details` MUST NOT carry secrets or host-absolute paths. This is checked in two
places in `emit_trace.py`, both calling the same `_scan_details` walker:

1. `validate_event(event)` runs `_scan_details` on `details` and adds an error for any hit.
2. `TraceEmitter.emit(...)` runs `_scan_details` on `details` and RAISES `ValueError` before the line is
   written, so a leaking event never reaches disk in the first place.

What the scanner flags:

```text
category            pattern (from emit_trace.py)
─────────────────── ─────────────────────────────────────────────────────────────────
OpenAI-style key    sk-<16+ alnum>
AWS access key id   AKIA<16 upper-alnum>
GitHub PAT          ghp_<30+ alnum>
xAI key             xai-<16+ alnum/->
PEM private key      -----BEGIN ... PRIVATE KEY-----
host-absolute path  a path under /home, /Users, or /root, or a /.ssh /.aws /.gnupg dir
```

The walker recurses through nested objects and lists, so a secret buried three levels deep in `details`
is still caught. The remediation it suggests is the right one: reference sensitive evidence by
`evidence_hash` (a SHA-256 digest you can verify against the run-archive) instead of inlining the secret,
and use repo-relative paths instead of host-absolute ones.

A `details` payload that will be rejected at emit time:

```json
{
  "details": {
    "log_path": "/Users/alice/.ssh/run.log",
    "token": "ghp_0123456789abcdef0123456789abcdef"
  }
}
```

The same payload, fixed:

```json
{
  "details": {
    "log_path": "logs/run.log",
    "evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  }
}
```

> This was a real review finding. An earlier draft of the engine documented the no-secrets rule in prose
> only and left enforcement to good intentions. The framework's own review caught that the rule was not
> enforced in code, and the fix wired `_scan_details` into both `validate_event` and `emit()`. The rule
> is now a code path, not a comment. That is the review discipline working on the framework itself, see
> [Roles and blindness](08-roles-and-blindness.md).

## What is emitted today vs the roadmap

Read this section before you build a dashboard against the stream, because the honest state today is
sparse.

The schema covers 11 primitives. Production code today wires exactly one of them. The single in-code
reference emitter is `fleet_run.write_manifest(..., emitter=...)`, which emits the `T-FINAL` archive
transition (role `INTEGRATOR`, status `succeeded`) and emits it BEFORE the manifest write, per the
trace-first doctrine:

```python
# scripts/lib/fleet_run.py, inside write_manifest(...)
manifest_path = archive_root / "manifest.json"
# Doctrine (engine.md TRACE EMISSION): trace first, ledger second. Emit BEFORE write.
if emitter is not None:
    emitter.emit(
        "T-FINAL",
        "INTEGRATOR",
        "succeeded",
        details={"manifest": manifest_path.name, "files": len(file_list)},
    )
manifest_path.write_text(
    json.dumps(payload, indent=2, sort_keys=False) + "\n",
    encoding="utf-8",
)
```

So in production today, a run's `trace.jsonl` typically contains one event: the `T-FINAL` archive seal.
The stream is intentionally sparse while per-transition emission rolls out. The other 10 primitives are
emitted by the coordinator and the adapters at their transitions per the engine TRACE EMISSION doctrine,
and that wiring is in progress, not finished. This is by design: the enforcement boundary is the schema
plus `validate_event` plus the schema-drift test plus the trace mutations, NOT auto-wiring, because the
file ledger is coordinator-driven and each adapter calls `emit()` itself at the transitions it owns.

A dashboard should therefore be built to render a stream that is correct but partial today, and grows
denser as emission rolls out. Do not assume a fully-populated lifeline per worker yet. Do assume that
whatever events you do see are schema-valid and ordered trace-first.

One more honest note on robustness: a failure to emit a trace event is NOT a hard error. The run
continues with degraded telemetry, and the coordinator records `trace_emission_degraded: true` in
`fleet-outcome.yaml` so a post-hoc audit knows the stream is incomplete (see
[fleet-outcome schema](17-fleet-outcome-schema.md)). Hard-failing on a telemetry I/O error would let the
dashboard veto real work, which inverts the dependency. As a corollary, the reader
`iter_trace_file()` tolerates malformed lines: a half-written trace from a crashed run is still partially
renderable, and the count of skipped lines is recorded on the generator. Treat malformed lines as
degraded telemetry, never as a run failure.

## Versioning and the `$id` policy

`schema_version` is the constant string `"1.0"` for this release, and the `$id` is
`https://autonomous-fleet.dev/schemas/fleet-trace.schema.json`. The versioning policy is strict and
worth internalizing:

- A breaking change requires a NEW `$id`, plus a synchronous update of the emitter library and the
  consumers. Consumers pin to the version they understand, so you do not silently break a dashboard by
  changing the meaning of a field under the same id.
- Adding a value to the `primitive`, `role`, or `status` enum is a breaking change, for the same reason.
  The enums are closed on purpose. A consumer that pattern-matches on a closed enum is entitled to assume
  the set does not grow underneath it.
- Adding a new optional top-level property is the non-breaking path for typed data. If a field inside
  `details` proves load-bearing, promote it to a top-level optional property in a new `$id` rather than
  asking consumers to parse `details`.

The schema and the emitter constants (`SCHEMA_VERSION`, `PRIMITIVES`, `ROLES`, `STATUSES`,
`_REQUIRED_FIELDS`, `_OPTIONAL_FIELDS`) are kept in lockstep by the drift test in
`tests/test_emit_trace.py`. If you change one and not the other, that test fails. That is the mechanism
that makes this chapter trustworthy: the schema cannot quietly diverge from the code that emits and
validates against it.

## Consumer guide: how to read the stream

If you are building a dashboard, here is the loop. It works against today's sparse stream and against the
denser stream emission rolls out to.

```text
1. Watch  .fleet/runs/*/trace.jsonl  for appended lines.
2. Parse each non-empty line as JSON. Skip blank lines.
3. Validate against fleet-trace.schema.json, or mirror emit_trace.validate_event.
4. Group by run_id, then order within a run by ts.
5. Render lanes / timelines from task_id, primitive, role, and status.
6. Sum cost_delta per run when present (treat absent as 0).
7. Treat malformed lines as degraded telemetry, not a run failure.
```

You do not need Python to consume the stream, but if you have it, the checked-in CLI is the fastest way
to sanity-check a file. `scripts/emit_trace.py` has two subcommands:

```bash
# Validate every non-empty line of a trace file against the schema-compatible validator.
# Exit 0 = all valid, 1 = at least one invalid line, 2 = usage error (missing/unreadable file).
python scripts/emit_trace.py validate .fleet/runs/20260623T000000Z-doc-sync-abc123/trace.jsonl

# Print counts by primitive, role, and status for a run directory.
python scripts/emit_trace.py summary .fleet/runs/20260623T000000Z-doc-sync-abc123
```

`validate` prints, for each bad line, the file, line number, and the specific constraint that failed, so
it doubles as a quick way to learn the schema by breaking it. `summary` reads `<run_dir>/trace.jsonl` and
prints the by-primitive, by-role, by-status histogram, which is the same shape a timeline renderer wants.

If you want to validate without shelling out, mirror `validate_event`: it is a single pure function that
takes a parsed event and returns a list of human-readable error strings (empty list means valid). It has
no third-party dependency, so it is cheap to port to whatever language your dashboard is written in. The
schema is the integration boundary; the validator is one reference implementation of it.

## The vibe-kanban integration doc

There is a companion note at `docs/external-dogfood/vibe-kanban-integration.md`. Read it alongside this
chapter, with one caveat: it describes the trace CONTRACT and the consumption loop, not a shipped
dashboard adapter. It says so itself in its status line ("It does not claim that a dashboard adapter is
already checked in"), and it describes the same rollout-in-progress this chapter does: today
`fleet_run.write_manifest` is the reference emitter (the `T-FINAL` event), and the coordinator and
adapters emit the rest per the engine doctrine as that wiring lands.

What the integration doc accurately covers: the file location (`.fleet/runs/<run_id>/trace.jsonl`), the
required and optional fields, the schema id and version, the `details` best-effort rule, the `emit()`
mechanics, the two CLI subcommands, and the seven-step consumption loop. What it does not provide, and
does not claim to: a turnkey vibe-kanban or Agent View renderer. The schema is the boundary. A renderer
can change without touching the fleet run loop as long as it keeps consuming the same JSONL contract.

So the practical reading order for a dashboard author is: this chapter for the field-level contract and
the honest emission state, the integration doc for the consumption recipe, and
`fleet-trace.schema.json` plus `emit_trace.py` as the ground truth both defer to.

---

← [Run-archive anatomy](15-run-archive.md) · [Guide Index](README.md) ·
[fleet-outcome schema](17-fleet-outcome-schema.md) →
