---
title: "The engine"
description: "The coordinator primitives (13 core plus the optional CONTINUE_WORKER), the TRACKER/SCM binding split, the file-based ledger with hash-namespaced placement, the coordinator/adapter split, signal reconciliation, anti-flap, evidence-hash, trace causal lineage, and the plan/DAG validation gate that make a fleet run deterministic and auditable."
sidebar:
  order: 6
---

# The engine

You have run a mission. You have seen the run-archive appear under `.fleet/runs/<id>/`. Now you
want to know how the sausage is made: what the coordinator actually does between "go" and the final
PR, why nothing happens by magic, and why the framework keeps insisting on files over memory.

This is the densest chapter in the guide. Read it once end-to-end, then keep it open as a reference
while you read [The substrate](/07-the-substrate/) and
[Roles and blindness](/08-roles-and-blindness/).

The engine is tool-agnostic. It never types a CLI command. It calls a small set of named
PRIMITIVES, and an ADAPTER for your runtime (Claude Code, Codex, Grok, Orca) resolves each one into
the real mechanics. Three things compose every run:

```
  CORE (the method)        MISSION (the work)           ADAPTER (the mechanics)
  ─────────────────        ──────────────────           ───────────────────────
  tool-agnostic loop       goal, role pipeline,         how THIS tool spawns a
  + 13 core primitives     phase/task structure,        worker, dispatches a task,
  + 1 optional (14th)      ledger filename + flags,     waits, inspects, places
  + all the doctrine       done condition, defaults     work, opens/merges a PR
  blocks in this chapter
```

The CORE only ever calls primitives by name. It never hard-codes a tool command. If a runtime
offers a primitive in two syntaxes across versions, the adapter says "try X, fall back to Y." That
separation is what lets the same engine drive four different agent runtimes without a rewrite.

The engine does not float free: it sits on a four-layer verification substrate that turns "done"
from self-attestation into on-disk evidence. L1 is schema-verified findings (every cited quote
re-verified against source), L2 is the opt-in strict-mode runtime gate that refuses to end a session
without fresh evidence, L3 is the anti-anchoring blind-fix (the reviewer commits its own fix before
reading the candidate patch), and L4 is the manifest-audited run-archive. Each layer has a library,
a validator, and a `FLEET_DISABLE_*` kill-switch. This chapter references those layers where the
engine leans on them; [The substrate](/07-the-substrate/) is the layer-by-layer reference.

**On this page:** [Primitives](#primitives) · [The ledger](#the-ledger-a-directory-not-a-database) ·
[Coordinator vs adapter](#coordinator-vs-adapter) · [Signal reconciliation](#signal-reconciliation) ·
[Anti-flap](#anti-flap) · [Evidence-hash](#evidence-hash) · [Plan/DAG validation](#plandag-validation-gate) ·
[Trace first, ledger second](#trace-first-ledger-second) · [Write-lock discipline](#write-lock-discipline) ·
[What is and isn't emitted today](#what-is-and-isnt-emitted-today)
## Real-world use cases

### Example — eleven-primitive fixture trace

`.fleet/runs/example-fixture/trace.jsonl` has 11 lines exercising every primitive enum
(`DISPATCH`, `SPAWN_WORKER`, `WAIT`, `GOAL_BLOCKED`, `INSPECT`, `SYNC`, `MERGE`, `FREEZE`,
`COMMIT`, `ABORT`, `T-FINAL`) with parent_event links on INSPECT and COMMIT. Validate:

```bash
python scripts/emit_trace.py validate .fleet/runs/example-fixture/trace.jsonl
```

### Invocation — representative emission without auth

```bash
python scripts/emit_representative_trace.py --mission doc-sync   --run-id 20260626T120000Z-doc-sync-dryrun01   --out /tmp/fleet-trace-demo
```

### Worked example — write-lock + archive ordering

`.fleet/runs/example-fixture/manifest.json` enforces blind_fix mtime < findings mtime <
verify_summary mtime; `python scripts/validate_run_archive.py .fleet/runs/example-fixture` passes on
the committed archive.

---

## Primitives

A primitive is a verb the engine knows how to call but does not know how to perform. The adapter
performs it. The engine's job is to sequence primitives and wait; the adapter's job is to make each
one real for its runtime.

There are two vocabularies you will meet, and the single most common confusion about this engine is
treating them as one list. They are not. Keep them straight from the start:

- The **coordinator primitives** in `engine.md` are the full interface the adapter implements, and
  there are **thirteen** core ones: `SPAWN_WORKER`, `DISPATCH`, `WAIT`, `INSPECT`, `PLACE`,
  `WORKER_DONE` / `ASK` / `REPLY` (counted as one primitive, #6), `OPEN_PR` / `MERGE_PR` / `CLEANUP`
  (one primitive, #7), `SYNC_TASK_STATE`, and the optional goal/loop family `SET_GOAL`,
  `UPDATE_GOAL`, `GOAL_COMPLETE`, `GOAL_BLOCKED`, `LOOP_POLL`. A **fourteenth**, `CONTINUE_WORKER`,
  is optional on the same footing as the goal/loop family: an adapter whose runtime exposes a
  session-restore command implements it, and one without aliases it to `SPAWN_WORKER`. These are the
  verbs the coordinator sequences and the adapter resolves into real commands. This whole section
  describes them.
- The **trace primitives** are a SEPARATE, closed eleven-value enum the observability stream uses to
  name a ledger transition. That list lives in `scripts/lib/emit_trace.py` and belongs to the
  [Trace schema](/16-trace-schema/) reference, not here.

The two enums overlap but neither is a subset of the other. The trace records ledger
state-transition verbs the coordinator never dispatches as primitives (`SYNC`, `MERGE`, `FREEZE`,
`T-FINAL`, `COMMIT`, `ABORT`) plus a `FIXER` role, and it omits coordinator-only primitives the
trace never emits (`PLACE`, `WORKER_DONE`, `OPEN_PR`, `CLEANUP`, `LOOP_POLL`, `CONTINUE_WORKER`). So
do not read the eleven trace values as "the engine's primitives": the engine has thirteen core
coordinator primitives plus the optional `CONTINUE_WORKER`; the trace enum is its own vocabulary,
covered field-by-field in [Trace schema](/16-trace-schema/).

> Both enums are closed on purpose. For the trace side, adding a value is a breaking change to the
> dashboard contract (see [Trace first, ledger second](#trace-first-ledger-second)). The mapping
> between the two: trace `SYNC` corresponds to the coordinator's `SYNC_TASK_STATE`, trace `MERGE` to
> `MERGE_PR`, and `FREEZE` / `COMMIT` / `ABORT` / `T-FINAL` name coordinator lifecycle transitions
> with no one-to-one primitive.

The [Trace schema](/16-trace-schema/) reference covers the trace enum field-by-field; this section
gives you the conceptual meaning of each coordinator primitive and what an adapter has to implement.

### SPAWN_WORKER(role, placement)

Returns a worker handle, in the chosen placement, running in auto / max mode (no per-action
permission prompts). The adapter decides what a "worker" physically is: a fresh terminal session, a
detached agent process, a container. The engine only holds the handle.

What an adapter must implement: launch a worker for the named role, in the named placement, with the
runtime's auto / skip-permissions flag applied, and return something the engine can later
`INSPECT()` and `DISPATCH()` to. Every spawn receives `REPO_ROOT` explicitly; the engine never
relies on a worker's current working directory, because isolated checkouts live elsewhere.

### DISPATCH(task, handle)

Hands a task spec to a worker so it will report completion. The engine attaches the operating
preamble (state assumptions, stop and ASK on conflict, prefer the boring solution, touch only this
task's files) and, when the mission lists worker skills, a Worker-skills block telling the worker
which installed skills to activate. The research preamble ships on every DISPATCH.

What an adapter must implement: deliver the task spec to the worker and wire the worker's completion
back to a `WAIT()`-able event.

### WAIT(types, timeout)

Blocks for completion / escalation / question events, non-busy. This is how the coordinator yields
instead of spinning. A `WAIT()` timeout or empty result is a checkpoint, not a failure, and never a
reason to involve you. The coordinator re-issues across a 15 to 60 minute cadence. Heartbeats and
worker activity mean alive, not done: the engine never kills a live worker.

### INSPECT()

Reads current task / worker / message state without consuming it. Non-destructive. This is the first
thing the coordinator does every turn, after re-reading the ledger file. State is reconstructed from
the file first, then cross-checked against `INSPECT()`, never from memory.

### PLACE(kind)

Produces a placement. Two kinds:

```
  PLACE(independent)              PLACE(dependent)
  ─────────────────              ────────────────
  isolated checkout / worktree    SAME checkout / branch,
  on its own branch off BASE,     a FRESH worker session
  for a parallel PR
```

The decision rule is dependency on uncommitted state. Work that is self-contained and does not need
another in-flight task's uncommitted state goes `independent`, for a parallel PR. Work that needs
the current branch's uncommitted state, must validate or PR the current branch, or is a review-fix
cycle on an open PR goes `dependent`. "Fresh worker" is not the same as "new isolated checkout"; a
dependent placement reuses the checkout but always starts a clean worker session.

The optional sandboxed variant of `PLACE(independent)` runs the worker inside a `container-use`
environment instead of a host `git worktree`, closing the OS-sandbox gap. See
[Safety and secrets](/12-safety-and-secrets/) for when to reach for it.

### WORKER_DONE / ASK / REPLY

The worker-to-coordinator completion (`WORKER_DONE`), the worker's blocking question (`ASK`), and
the coordinator's answer (`REPLY`). A worker never asks you a question. It asks the coordinator over
`ASK`, and the coordinator answers from the mission's DECISION DEFAULTS over `REPLY`. The one
exception is `draft-both-and-gate`: an editorial, brand-truth-sensitive, or disclosure-sensitive
decision the fleet must not fabricate halts for a human instead of taking a default.

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP(worktree)

The ship primitives. `OPEN_PR` opens a PR against BASE with public information only (IDs and
file:line, never secrets). `MERGE_PR` is conflict-aware: it rebases onto an updated BASE, resolves
preserving both intent and what landed since fork, and merges with a merge commit. Commits are
preserved, never squashed. `CLEANUP` removes the merged checkout only after guard clauses pass:
never the active worktree, never an unmerged branch, never a worktree with uncommitted changes.

These ship verbs are the SCM binding. `engine.md` names two distinct adapter bindings here: the SCM
binding (open a PR against BASE, conflict-aware merge, cleanup) and a separate TRACKER binding (read
an issue, derive a branch name from it, mark the issue done). `gh` / GitHub is the DEFAULT for both,
not the contract. The contract is "open a PR against BASE and conflict-aware merge it," which `gh`,
`glab`, or a Linear-tracker-plus-GitHub-SCM pairing all satisfy. An adapter declares its TRACKER and
its SCM independently, so a Linear tracker driving a GitHub SCM is a legal pairing. Splitting the
binding does not relax anything: the conflict-aware, never-squash, and SHA-pin rules bind whatever
SCM is used.

### SYNC_TASK_STATE(task, status)

Keeps the runtime's native task view aligned with the ledger. The ledger is the source of truth;
`SYNC_TASK_STATE` mirrors it into whatever task UI the runtime exposes so a human watching the tool
sees the same state the file holds. In the trace stream this transition is named `SYNC`.

### The goal / loop family (optional)

`SET_GOAL`, `UPDATE_GOAL`, `GOAL_COMPLETE`, `GOAL_BLOCKED`, and `LOOP_POLL` bind a host's native
goal / loop API to the mission's DONE condition. They are optional: a runtime with no goal API (Orca
relies on a ledger plus a `check --wait` loop) simply omits them. When present, `SET_GOAL` records
the condition under `## Runtime goal` in the ledger, `UPDATE_GOAL` pings progress without
completing,
`GOAL_COMPLETE` ends goal mode only after the same termination checks the coordinator runs by hand,
and `GOAL_BLOCKED` pauses the goal and maps to `fleet-outcome.status: blocked`. `GOAL_BLOCKED` is
also one of the eleven trace primitives, because a blocked goal is a transition a dashboard wants to
see. See `references/runtime-goals.md` for the binding details.

> Adapters without a scheduler fall back to a foreground `check --wait` loop. The engine never
> assumes a primitive exists; it calls it by name and lets the adapter decide whether it has one.

### CONTINUE_WORKER (optional, the fourteenth)

`CONTINUE_WORKER(role, placement, session_handle)` re-attaches an EXISTING resumable agent session
for an in-flight task instead of spawning a fresh worker. It exists so a run that crashed or
compacted mid-task can pick the worker back up rather than redo its work. Adapters whose runtime
exposes a restore command (a Grok `sessionId`, a Codex thread, an opencode session) implement it;
adapters without one ALIAS it to `SPAWN_WORKER`, which is the documented idempotent-relaunch
fallback. Like the goal/loop family, it is optional: an adapter that cannot restore a session is
fully conformant without it.

Two guard rails bound when the coordinator may call it:

- It is constrained to `live`-classified rows only. The recovery scanner
  (`scripts/lib/recovery_scan.py`, see [Resume and recovery](#resume-and-recovery) below)
  classifies each ledger row `live` / `dead` / `partial` / `orphan`; only a `live` row gets a
  `CONTINUE` recommendation. The engine never re-attaches a session whose PR already merged or whose
  branch is gone.
- The resume budget is bounded. Each row tracks a `RESUME_COUNT`, and when it reaches
  `MAX_RESUME_ATTEMPTS` (3, defined in `recovery_scan.py`) the scanner downgrades the recommendation
  from `CONTINUE` to `ESCALATE_TO_DECISIONS` instead of another continue, so a perpetually-failing
  task escalates to a human decision rather than looping resume attempts forever.

In the trace stream a resumed worker does not introduce a new trace verb: `CONTINUE_WORKER` is a
coordinator primitive the trace never emits, so a resumed session's events still record under the
existing transition verbs.

---

## The ledger: a directory, not a database

The first instinct most people have about an autonomous agent fleet is "there must be a queue, or a
database, tracking all of this." There is not. The ledger is a directory of plain files under your
repo, and that is a deliberate design choice, not a shortcut.

Two locations matter:

```
  REPO_ROOT/
  ├── docs/
  │   ├── <mission-ledger>.md      ← the loop's external brain (per-task rows + flags)
  │   ├── DECISIONS.md             ← every silent default, recorded with rationale
  │   └── research-notes.md        ← one line per external fact verified during the run
  └── .fleet/runs/<run_id>/        ← the audited artifact archive for THIS run
      ├── manifest.json            ← every file the run produced, with sha256 + mtime
      ├── trace.jsonl              ← one JSONL line per state transition
      ├── locks/                   ← {owner, acquired_at, pid} lock files
      ├── reviewer-blind-fix-*.md  ← the reviewer's pre-committed independent fix
      ├── <findings>.json          ← schema-verified review findings
      └── <readiness>.md           ← the run's final artifact
```

Why a directory and not a database:

1. **It survives the coordinator.** The coordinator's context window is finite. When it fills, the
   coordinator does not push through and does not ask you to continue. It writes a CONTEXT HANDOFF
   block into the ledger and a fresh coordinator with zero prior context resumes from the file. A
   database would need a process to serve it; a directory just sits there.

2. **It is the external brain.** The first action of every coordinator turn is to read the ledger
   file, then `INSPECT()` the tool state. State is reconstructed from the file first, never from
   memory. The exit gates are file-based: a task advances only when its flags read true in the file,
   not when the coordinator believes it is done.

3. **It is auditable forever.** The run-archive is a manifest-audited file trail. Every artifact the
   run produced lives at a deterministic path with a sha256 in the manifest. You can `cat` it, grep
   it, diff it, and hand it to a different tool. The fleet never garbage-collects archives;
   retention is an out-of-band operator decision.

The run-id format is itself part of the discipline:

```
  YYYYMMDDTHHMMSSZ-<mission>-<short-hash>

  example: 20260623T141522Z-adversarial-review-and-fix-3a9c2f
```

A sortable UTC timestamp, a greppable mission slug, and a 6-character random hex suffix
(`secrets.token_hex`) so two runs on the same coordinator-pid in the same second still get distinct
ids. The run-archive validator accepts only this shape; operator pet names break sort-by-time
auditability and are rejected. The same pattern is pinned in code as a regex (`_RUN_ID_RE` in
`emit_trace.py`), so a trace event carrying a malformed run-id fails validation.

For the full anatomy of every file in a run-archive, see [Run-archive anatomy](/15-run-archive/).

### Per-task rows and boolean exit gates

The mission defines the ledger filename and its flag set. The per-task row carries, at minimum: the
task ID, the branch, the PR number, the reviewed SHA, the worktree path or environment id, the
placement, and the flags `BUILT`, `PR_OPEN`, `REVIEWED`, `MERGED`, `WT_CLEAN`.

The reviewed SHA is not just recorded, it is enforced. A reviewer that returns PASS writes
`.fleet/runs/<run_id>/sha-pin.json` with `{reviewed_sha, branch, verdict}`, and
`scripts/verify_sha_pin.py` (run by validate-all, with a `FLEET_DISABLE_SHA_PIN` kill-switch)
re-resolves the branch HEAD and flips `REVIEWED` to OUTDATED when it diverges from `reviewed_sha`,
so a PASS graded against a SHA the branch has since moved past cannot ship even if the coordinator
forgets to clear it. A task whose branch was deleted but is provably merged is N/A, not a fail.

A task is terminal only when `MERGED=true` AND `WT_CLEAN=true`. The coordinator's last check before
ending a turn is to re-read the ledger and `INSPECT()`: any non-terminal task, any unmerged branch,
any open PR means it is not done, and it takes the next action in the same turn. A merged-but-
uncleaned task is explicitly not terminal; `T_FINAL` runs a worktree-orphan sweep before the run can
close.

### Hash-namespaced placement

Every isolated branch and worktree a run creates carries the active run's 6-character suffix, so two
runs, or two checkouts of the same mission, never collide on a bare slug. The shape is fixed:

```
  branch    <prefix><slug>-<run_short>      e.g. fleet/auth-fix-3a9c2f
  worktree  ../<repo>-<slug>-<run_short>     e.g. ../myrepo-auth-fix-3a9c2f
```

`run_short` is the 6-hex tail of the run-id, derived by `namespace.derive_run_short()`
(`scripts/lib/namespace.py`), and `namespaced_branch()` / `namespaced_worktree()` are the helpers
that build the two strings. This is the placement counterpart to the run-id discipline above: the
run-id makes the archive sortable and greppable; the `-<run_short>` suffix makes the branches and
worktrees of concurrent runs distinguishable on disk. `scripts/validate_namespacing.py` (wired into
validate-all, with a `FLEET_DISABLE_NAMESPACING` kill-switch) reads the manifest's progress ledgers
and rejects any recorded task-row branch or worktree path that does not end in `-<run_short>`, so a
bare `<prefix><slug>` cannot slip through.

### Resume and recovery

At resume, after a compaction or a crash, the coordinator runs `scripts/recovery_scan.py` over the
ledger before driving more work. The scanner is advisory and never executes: it classifies each task
row `live` / `dead` / `partial` / `orphan` against the live `git worktree list` and `gh pr list`,
and emits one of `CONTINUE` / `CLEANUP_WORKTREE` / `RE_DRIVE` / `ESCALATE_TO_DECISIONS` /
`ARCHIVE_ORPHAN` per row. The coordinator reads those recommendations and decides; the scanner only
reports. A `live` row recommends `CONTINUE`, which is exactly the row class that authorizes
`CONTINUE_WORKER` (the fourteenth primitive above). The `RESUME_COUNT` / `MAX_RESUME_ATTEMPTS` (3)
budget lives here too: an exhausted budget flips a `CONTINUE` or `RE_DRIVE` recommendation to
`ESCALATE_TO_DECISIONS`.

---

## Coordinator vs adapter

The cleanest way to understand the engine is to separate who decides from who acts.

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  COORDINATOR  (decides)                                               │
  │  ──────────────────────                                               │
  │  • reads the ledger, INSPECT()s, reconciles signals                  │
  │  • freezes the task DAG, validates it, computes parallelism width    │
  │  • routes model tier by role, tracks cost estimate                   │
  │  • answers worker ASKs from DECISION DEFAULTS via REPLY              │
  │  • sequences primitives, waits, never busy-loops                     │
  │  • NEVER types a tool command                                       │
  └───────────────────────────────┬──────────────────────────────────────┘
                                  │ calls primitives by name
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  ADAPTER  (acts)                                                      │
  │  ────────────────                                                    │
  │  • resolves SPAWN_WORKER → the runtime's spawn command               │
  │  • resolves DISPATCH/WAIT/INSPECT → the runtime's messaging API      │
  │  • resolves PLACE → git worktree or container-use environment        │
  │  • resolves OPEN_PR/MERGE_PR/CLEANUP → gh + git on the host          │
  │  • "try X, fall back to Y" across tool versions                      │
  └──────────────────────────────────────────────────────────────────────┘
```

The coordinator is the same code regardless of runtime. The adapter is the only thing that changes
between Claude Code, Codex, Grok, and Orca. This is why a new runtime is "write an adapter," not
"fork the engine." The adapter chapter of [Extending](/13-extending/) walks the primitive-by-
primitive mapping.

The coordinator operates fully autonomous. It does not ask you anything except (a) the single FINAL
report and (b) a hard external dependency a mission explicitly names, like an OAuth grant the agent
cannot self-issue. For every other choice (placement, parallelism, libraries, merge policy) it
silently picks the recommended default from its judgment plus the mission's DECISION DEFAULTS,
records it in `DECISIONS.md`, and proceeds. A reasonable default now beats stopping.

> The single biggest failure mode for an autonomous coordinator is ending its turn while work
> remains, or asking you to continue. The engine treats that instinct as a bug and suppresses it
> mechanically: read the ledger first every turn, never end on belief, terminate only when the
> mission's DONE condition is true in the file and the readiness doc exists.

---

## Signal reconciliation

Here is the subtlety that separates a robust loop from a flaky one. Three signals report the health
of a task, and in normal operation they disagree:

```
  signal 1: worker-liveness     (INSPECT)            is the worker process alive?
  signal 2: the ledger flag      (what you wrote)     what does the file say?
  signal 3: the external SCM/CI  (gh pr view, CI)     what does GitHub say?
```

A worker process can be dead while the runtime is alive. The ledger can say `PR_OPEN` while CI has
already gone red. The SCM can show merged while your flag still reads `REVIEWED`. Any one of these,
read once, is not a decision.

The rule: do not advance, escalate, or declare a task stuck on the first read that disagrees. A
single poll is a data point, not a verdict.

Two reconciliation disciplines flow from this:

1. **External fact overrides the ledger at a terminal edge.** Before writing any terminal flag
   (`MERGED`, `DONE`), the coordinator re-verifies the external fact directly (`gh pr view <n>
--json state,mergedAt`, the CI conclusion) and lets it override the ledger when they disagree.
   If the SCM says merged but your flag does not, the SCM wins: record `MERGED`. If your flag says
   merged but the SCM says open or closed-unmerged, the SCM wins: do not mark `DONE`, record the
   discrepancy in `DECISIONS.md`, and re-drive the task. The ledger is loop memory; the SCM and CI
   are ground truth at a terminal edge.

2. **A disagreement is a checkpoint, not a failure.** Reassignment happens only after the 3-failure
   circuit-breaker trips, a worker is confirmed exited, or a DETECTING timeout elapses, never on a
   single poll. The circuit-breaker counts confirmed hard failures per task (a worker crash, a build
   that comes back red after the worker reported done, a DETECTING-timeout reassignment). It does
   not increment on a `WAIT()` timeout, a heartbeat gap, or a transient tool error. It resets to 0
   on a clean `WORKER_DONE`. At 3, it runs the compensation rollback then reassigns once more; a
   second trip defers the task rather than looping forever.

---

## Anti-flap

Signal reconciliation says "do not transition on one read." Anti-flap is the mechanism that makes
that concrete and stops a noisy signal from oscillating a task forever.

A contested task is held in a DETECTING state. It transitions only after N consecutive consistent
polls (default 3) OR a hard timeout (default 5 minutes) elapses, whichever comes first.

```
  poll 1: signals disagree  → enter DETECTING, counter = 1
  poll 2: same evidence     → counter still 1 (weak evidence re-presenting does NOT advance)
  poll 3: NEW evidence      → counter resets to 1 (genuinely new evidence restarts the clock)
  poll 4: consistent        → counter = 2
  poll 5: consistent        → counter = 3  → TRANSITION
                                            (or: 5-minute timeout fires first → TRANSITION)
```

The counter is keyed to an evidence hash of the contested signals, not to wall-clock time. This is
the part that matters: unchanged weak evidence re-presenting must not reset the stuck clock, and
genuinely new evidence must reset it to 1. Without the hash key, a flapping signal would either
oscillate the task between states or reset the stuck clock forever, and the loop would never
terminate or never progress. The hash is what makes "three consistent polls" mean something.

---

## Evidence-hash

The evidence-hash shows up in two places, doing two related jobs. It is worth pinning down because
the same idea anchors both anti-flap and the audit trail.

**In anti-flap (above):** the counter is keyed to a hash of the contested signals, with volatile
fields stripped before hashing. The doctrine is explicit that you strip volatile fields (timestamps,
activity counters) before computing the hash, so that re-presenting the same underlying state
produces the same hash and does not reset the counter.

**In the run-archive and trace stream:** evidence is referenced by `evidence_hash`, a 64-character
hex sha256, instead of inlining the raw artifact. The trace `details` object is free-form but must
not carry secrets or host-absolute paths; sensitive evidence is referenced by its hash. The
validator enforces the shape: `_EVIDENCE_HASH_RE = re.compile(r"^[0-9a-f]{64}$")` in `emit_trace.py`
rejects anything that is not a 64-char hex digest.

The run-archive manifest takes this one step further. Every file entry carries a `sha256`, and the
validator enforces causal mtime ordering between kinds, because those orderings are the disciplines
from the substrate layers made physical:

```
  blind_fix      mtime BEFORE  every findings file from the same reviewer  (anti-anchoring)
  verify_summary mtime AFTER   the findings file it audits                 (real audit, not stale)
  readiness      mtime LATEST  of everything in the archive                (final artifact)
```

A manifest whose files do not satisfy these orderings fails validation even when every checksum
matches. The discipline is not "files exist"; it is "files exist in the order the discipline
demands." The hash proves the file was unmodified; the mtime ordering proves it was produced in the
right sequence. See [Run-archive anatomy](/15-run-archive/) for the manifest field reference.

---

## Plan/DAG validation gate

Before the first `SPAWN_WORKER`, the coordinator runs one cheap structural check on the already-
frozen task DAG. The decomposition is frozen by the time you spawn; validating it before any worker
launches catches a malformed plan before it costs a wave of workers.

The gate runs once, over the frozen task DAG in the ledger, and checks three things:

```
  ┌────────────────────────────────────────────────────────────────────┐
  │  1. NO CYCLES                                                       │
  │     The dependency edges form a DAG. A cycle means the freeze is    │
  │     wrong → STOP, name it in DECISIONS.md, re-decompose.            │
  │     Never spawn into a deadlock.                                    │
  │                                                                     │
  │  2. DEPENDENCIES RESOLVABLE                                         │
  │     Every declared dependency names a task that exists in the      │
  │     frozen set. A dangling / typo'd edge means a task can never     │
  │     become ready → fix the freeze.                                  │
  │                                                                     │
  │  3. PARALLELISM WIDTH COMPUTED                                      │
  │     The max set of tasks with all dependencies satisfied at once.  │
  │     Recorded in the ledger; bounds the initial spawn wave (with    │
  │     the concurrency cap) and feeds WORKER PLACEMENT.                │
  │     A width of 1 on a multi-task mission is a smell:               │
  │     the decomposition over-serialized.                             │
  └────────────────────────────────────────────────────────────────────┘
```

This is a structural check on an already-frozen artifact, not re-planning. It is O(tasks + edges),
no workers, no model spend. The alternative to one extra coordinator pass is failed workers and
burned spend on a plan that was wrong from the start. A mission that declares no inter-task
dependencies passes trivially.

The frozen artifact (the plan, audit, review, or boundary doc) caps the whole run's scope. The
coordinator builds what is inside it and routes newly discovered ideas, optional features, and
refactors to `DECISIONS.md` plus a Recommended-next-missions list. Reviewers fail any PR that adds
out-of-boundary work, even when tests pass.

---

## Trace first, ledger second

This is the doctrine that makes the whole thing auditable, and it is now enforced in code, not just
prose.

The trace stream is one JSONL line per state transition, written to `.fleet/runs/<run_id>/trace.jsonl`.
The schema (`skills/autonomous-fleet-core/assets/fleet-trace.schema.json`, pinned at `schema_version: "1.0"`) is the contract:
vibe-kanban, Claude Code Agent View, and custom dashboards are interchangeable consumers. Owning the
format, not the renderer, is what keeps live observability free of UI debt.

The rule: every state transition that writes to the ledger must emit a trace event BEFORE the ledger
write commits. The trace is the source of truth for "what happened"; the ledger is derived state.
Trace first, ledger second, never the reverse. If you wrote the ledger first and the coordinator
crashed before emitting, you would have a row with no externally-visible cause.

The reference in-code integration is `fleet_run.write_manifest`, which emits the `T-FINAL` archive
transition. The ordering is visible in the source, and it is the right way around:

```python
# scripts/lib/fleet_run.py, write_manifest()
manifest_path = archive_root / "manifest.json"
# Doctrine (engine.md TRACE EMISSION): trace first, ledger second, never the reverse,
# or a crash leaves the manifest on disk with no externally-visible cause. Emit BEFORE write.
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

The `emitter.emit(...)` call comes before `manifest_path.write_text(...)`. The trace lands first;
the manifest follows. This is the doctrine made mechanical at the one production integration point.

> Worked example of the review discipline catching itself: an early post-merge audit flagged that
> the manifest was being written before the trace emitted, inverting this doctrine. That was fixed
> (the emit now precedes the write, as shown above). The framework found and closed its own bug
> through the same review gate it applies to your repo. This is no longer an open issue; it is the
> reason the comment in the source is so emphatic about ordering.

### Causal lineage: id and parent_event

A flat list of transitions tells you what happened but not which worker caused which event. The
trace closes that gap with two fields. `emit()` stamps every event with a unique `id` and RETURNS
it (the return is the whole point: the caller keeps the id to wire children to it). A worker's later
events, its `COMMIT` and the like, then set `parent_event` to that worker's `SPAWN_WORKER` id, so a
consumer can walk parent links and reconstruct one worker's lifeline from spawn to commit.
`fleet_run` wires the reference SPAWN to COMMIT edge.

Two design choices keep this from being a breaking change:

- `id` is an optional field in the schema but is always generated at emit time, so adding lineage did
  not bump the pinned `1.0` schema or break a consumer that ignores `id`. `parent_event` is likewise
  optional, validated as a non-empty string only when present.
- The id factory is injectable. `TraceEmitter(..., id_factory=...)` defaults to `uuid.uuid4`, but a
  fixture can pass a deterministic factory so the trace stays reproducible byte-for-byte in tests.
  The emitter rejects a factory that returns a non-string or empty id with a `ValueError`.

### Why nothing is auto-emitted

A reasonable question: if trace-first is doctrine, why is it not wired automatically into every
ledger write? Because the file ledger is coordinator-driven, and the coordinator is a model, not a
deterministic state machine you can wrap with a decorator. There is no single chokepoint that every
transition passes through. So the discipline is enforced by a different mechanism than auto-wiring:

```
  the schema (fleet-trace.schema.json)
    + emit_trace.validate_event       ← structural validation of every event
    + the schema-drift test            ← PRIMITIVES/ROLES/STATUSES stay in lockstep with the schema
    + the trace mutations              ← mutation gate proves the validator actually rejects bad events
```

`emit_trace.validate_event(event)` returns a list of error messages and is empty only for a valid
event. It checks the required fields, rejects unknown fields (`additionalProperties not allowed`),
pins `schema_version` to `"1.0"`, validates the timestamp and run-id shapes, and confirms
`primitive`, `role`, and `status` are members of the closed enums. The enums are closed on purpose:
adding a primitive, role, or status is a breaking change to the contract and would require a new
`$id`, because consumers pin to the version they understand.

### The details redaction rule, enforced

The trace stream is meant for publication to external dashboards, so the `details` object must not
carry secrets or host-absolute paths. This is no longer a prose-only rule. It is enforced at two
call sites in `emit_trace.py`:

- `validate_event()` runs `_scan_details(details)` when `details` is present and appends any
  violation to its error list.
- `emit()` runs the same `_scan_details(details)` and raises `ValueError` if it finds a secret or a
  host-absolute path, before the line is ever written to disk.

The scanner walks the payload recursively and flags strings that match a secret pattern. Examples
include OpenAI `sk-`, AWS `AKIA`, GitHub `ghp_`, xAI `xai-`, and a PEM private-key header, among
others. It also flags host-absolute paths such as `/home/`, `/Users/`, `/root/`, or a `.ssh` /
`.aws` / `.gnupg` directory, among others. Sensitive evidence is
referenced by `evidence_hash` instead. So a worker that accidentally puts a token in `details` gets
a hard `ValueError` at emit time, not a leaked secret on a public dashboard.

### Failure to emit is not a hard error

Telemetry must never veto real work. If a trace emission fails (an I/O error on the JSONL file), the
run continues with degraded telemetry and the coordinator records `trace_emission_degraded: true` in
`fleet-outcome.yaml` so the post-hoc audit knows the stream is incomplete. Hard-failing on a
telemetry write would let the dashboard veto real work, which inverts the dependency. The reader side
matches this posture: `iter_trace_file()` tolerates malformed lines so a half-written trace from a
crashed run is still partially renderable.

For the full field-by-field schema, the role and status enums, and the consumer guide, see the
[Trace schema](/16-trace-schema/) reference.

---

## Write-lock discipline

Status first, because it matters: the lock library (`scripts/lib/locks.py`) exists and is tested,
but it has NO single-coordinator call-site today. A single-coordinator run serializes through the
file ledger, so it never needs a lock. The discipline below is for parallel-coordinator or
shared-archive multi-writer setups, where two writers can race the same path; wire the locks then.

A worker that mutates shared state (the run-archive, a worktree branch, an external API) acquires a
lock before the mutation and releases it after. Two locks, two lifetimes:

```
  CONSTRUCTION LOCK                         REQUEST LOCK
  ────────────────                          ────────────
  acquired before a worker BUILDS           acquired before a worker calls an
  artifacts in its task slot                external write API (gh pr merge,
  (worktree, branch, attestation file)      terraform apply, git push)
  released only on COMMIT or ABORT          released immediately after the call returns
  long-held                                 short-held, taken just-in-time
  prevents two workers racing to write      prevents a runaway worker issuing
  the same archive path                     duplicate side-effectful API calls
```

A worker holding a construction lock may briefly hold a request lock; the reverse, a long-held
request lock, is forbidden. Lock files live under `.fleet/runs/<run_id>/locks/` with contents
`{owner, acquired_at, pid}` for diagnostics. The implementation is `scripts/lib/locks.py`.

A lock whose holder process is dead may be stolen by another worker, but only after the signal-
reconciliation dead-worker discipline has confirmed the holder is gone. The lock library exposes the
steal mechanism; the coordinator's circuit-breaker decides when it is safe to invoke. The steal path
itself refuses to steal from a live local holder: `FileLock.steal()` reads the lock's `pid`, and if
that pid resolves to a live local process (`_pid_alive(pid)` returns true), the steal is rejected
with a `LockStealError`. Lock age never authorizes stealing a live holder. Stealing without a
confirmed-dead signal is a protocol violation.

---

## What is and isn't emitted today

This guide does not hide current limitations, so here is the honest state of the trace stream.

The trace schema covers all eleven of its primitives (the trace enum, not the thirteen coordinator
primitives above). The stream is intentionally sparse in production today:
exactly one trace event is wired into production code, the `T-FINAL` archive transition emitted by
`fleet_run.write_manifest` (shown in [Trace first, ledger second](#trace-first-ledger-second) above,
test and mutation covered). Per-transition emission for the other primitives is a rollout in
progress. The coordinator and adapters emit the rest per the engine's TRACE EMISSION doctrine as that
rollout lands; the enforcement (schema, `validate_event`, the schema-drift test, the trace mutations)
is already in place, so events emitted today and events emitted after the rollout are validated the
same way.

```
  what the TRACE SCHEMA defines  what production code emits TODAY
  ───────────────────────        ───────────────────────────────
  11 trace primitives            1 primitive: T-FINAL
  6 roles, 5 statuses            from fleet_run.write_manifest
  full details contract          (test + mutation covered)
                                 → the rest is per-transition rollout in progress
```

The `docs/external-dogfood/vibe-kanban-integration.md` integration doc describes this contract plus
the rollout-in-progress, not a shipped full stream. When you read it, read it as "here is the format
a dashboard can consume, and here is what is wired so far," not "here is a live firehose." The
[Trace schema](/16-trace-schema/) reference has the authoritative "what's emitted today vs the
roadmap" section.

One more current limitation worth naming here because it touches the engine's invocation path:
headless campaign mode (`run-campaign.sh`, which drives each runtime's CLI in headless mode) is not
yet fully validated end-to-end. The supported path today is interactive: chat, or the `/goal`
binding. See [Safety and secrets](/12-safety-and-secrets/) for the headless-mode caveat and the
auth requirement it carries.

---

## Where to go next

You now know how the engine sequences work and proves what it did. Two chapters build directly on
this one:

- [The substrate](/07-the-substrate/) covers the four verification layers that catch bad work. The
  mtime orderings in [Evidence-hash](#evidence-hash) above are those layers made physical in the
  manifest.
- [Roles and blindness](/08-roles-and-blindness/) covers why the reviewer never sees the build
  conversation, why workers run in separate terminals, and why cross-vendor review is structural
  rather than instructed.

And for the formats this chapter referenced: [Run-archive anatomy](/15-run-archive/) for every file
in `.fleet/runs/<id>/`, and [Trace schema](/16-trace-schema/) for the event ledger format
field-by-field.

---

← [Previous: Missions vs campaigns](/05-missions-vs-campaigns/) ·
[Guide Index](/) ·
[Next: The substrate →](/07-the-substrate/)
