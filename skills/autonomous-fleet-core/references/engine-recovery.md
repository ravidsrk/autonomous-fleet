# Engine recovery and termination gates

Load when resuming a run, deciding whether a task/turn/run may terminate, checking strict-mode/archive evidence, validating the frozen task DAG before the first spawn, or writing handoff state.

<!-- moved from engine.md by the instruction-budget split; preserve doctrine semantics. -->

═══════════════════════════════════════════════════════════
AUTONOMY ENFORCEMENT — overrides your default turn-ending behaviour.
═══════════════════════════════════════════════════════════
Top failure mode: ENDING YOUR TURN while work remains, or asking the user to continue. That
instinct is a BUG. Suppress it mechanically:
- FIRST action EVERY turn: READ the ledger file (the mission names it), then INSPECT() the
  tool state non-destructively. Reconstruct state from the FILE first — never memory.
  AT RESUME (after compaction or a crash), run `python3 <SUBSTRATE>/recovery_scan.py` (ledger + `git
  worktree list` + `gh pr list`): it classifies each task row live/dead/partial/orphan and
  recommends CONTINUE / CLEANUP_WORKTREE / RE_DRIVE / ESCALATE / ARCHIVE_ORPHAN. It is ADVISORY:
  act on a destructive action only via the existing cleanup guard clauses (never the
  active/unmerged/dirty worktree); ESCALATE ambiguous rows to DECISIONS.md, never guess.
- BOOLEAN EXIT GATES (file-based): the ledger holds per-task status lines you WRITE/UPDATE with
  the flags the mission defines. A task advances only when its flags read true IN THE FILE — not
  when you "believe" it's done.
- LAST check before ending a turn: re-read the ledger + INSPECT(). Any non-terminal task, any
  unmerged branch, any open PR, any work item still open → YOU ARE NOT DONE. Take the next action
  IN THE SAME TURN.
- TERMINATE ONLY when the mission's DONE condition is met in the file AND the final readiness doc
  exists. Then send the single FINAL report.
- TERMINATE rejects merged-but-uncleaned tasks: every shipped task row must read MERGED=true and
  WT_CLEAN=true, and T_FINAL must have run the worktree-orphan sweep. A merged but uncleaned task
  is NOT terminal.
- LEDGER CONTRADICTIONS are checkable, not just narrated: a task row that reads MERGED=true with
  BUILT=false, MERGED=true with WT_CLEAN=false, or REVIEWED=true with PR_OPEN=false is a protocol
  violation. `<SUBSTRATE>/lib/fleet_outcome.py` rejects these over the readiness `tasks:` block. The
  dashboard (`scripts/render-dashboard.py`, framework clone only) renders the ledger to attention zones; `--watch` re-
  renders on ledger mtime change in the FOREGROUND (a convenience that dies with the terminal, NOT
  a daemon).
- RUNTIME GOAL (when adapter supports primitives 9–12): after SELF-ORIENTATION and ledger init,
  SET_GOAL with a condition that paraphrases the mission DONE gates (must reference the LEDGER_DIR ledger
  and readiness paths — `docs/` by default, the relocated dir per SELF-ORIENTATION step 6 (`engine-autonomy.md`) otherwise). UPDATE_GOAL at major phase transitions. GOAL_COMPLETE only after TERMINATE
  checks pass (re-read ledger, readiness exists, the readiness fleet-outcome validates (`python3 <SUBSTRATE>/validate_fleet_outcome.py <readiness>`) when
  available). Never GOAL_COMPLETE on belief — files are authoritative; the native goal is the turn-
  continuation harness. GOAL_BLOCKED when the mission names a hard external dependency or circuit-
  breaker trips with no recovery path.
- NEVER ask "shall I continue?", "proceed?", "keep waiting?", "merge this?". Always YES; act.
- Worker blocking question → arrives via the adapter's ASK channel; answer with REPLY from the
  mission's DECISION DEFAULTS, keep waiting. Never relay a worker's question to the user.
- A WAIT() timeout / empty result = checkpoint, NOT failure, NOT a reason to involve the user.
  Re-issue across 15–60 min. Heartbeats/worker activity = alive, not done — never kill a live
  worker. A task fails only if its worker exits/disappears or the 3-failure circuit-breaker
  trips — then reassign, never stop.
- 3-FAILURE CIRCUIT-BREAKER (definition). Keep a failure counter PER TASK. It increments on a
  CONFIRMED hard failure of that task: a worker exit/crash, a build/test that comes back red after
  the worker reported done, or a DETECTING-timeout reassignment (see SIGNAL RECONCILIATION). It does
  NOT increment on a WAIT timeout, a heartbeat gap, or a transient tool error (those are
  checkpoints), and it is SEPARATE from REVIEW's "max fix rounds" counter (a reviewer returning
  CHANGES is normal iteration, not a task failure). The counter RESETS to 0 on a clean WORKER_DONE
  for that task. At 3, the breaker TRIPS: clean up the task's partial side-effects directly — close
  the orphan PR, delete the dead branch, and revert any partial commit on BASE (each via the same
  cleanup guard clauses: never touch an active/unmerged/dirty worktree) — THEN reassign once more;
  if those side-effects can't be cleanly undone, record them in DECISIONS.md and escalate instead
  of guessing. If a reassigned task trips again, defer it via `fleet-outcome.deferred_missions`
  rather than looping forever.
If about to message the user anything but the FINAL report (or a named hard-dependency gate):
stop, re-read this block, read the ledger, take the orchestration action instead.

═══════════════════════════════════════════════════════════
RESULT-STATE TERMINATION GATE: green checks are not enough.
═══════════════════════════════════════════════════════════
A green test/validator suite is NECESSARY BUT NOT SUFFICIENT. NEVER terminate
(`GOAL_COMPLETE` / `DONE`) on green checkmarks alone. Verify the real end-to-end RESULT STATE:
query the actual result, not exit codes, and record the evidence in the readiness doc. Completion,
rebuild, and build missions gate on `fleet-outcome.metrics.e2e_verified == true`. Lesson source:
a validated gate can be inert; see `docs/secure-ship-e2e.md`.

═══════════════════════════════════════════════════════════
RUNTIME ENFORCEMENT GATE (optional, adapter-provided): make EVID/WT_CLEAN/e2e_verified enforceable.
═══════════════════════════════════════════════════════════
By default the engine's three discipline flags (EVID, WT_CLEAN, e2e_verified) are aspirational —
the builder self-attests in the readiness doc and the orchestrator trusts the attestation. This is
the second most common failure mode in fleet runs (after reviewer hallucination, addressed by
schema-verified findings): SELF-ATTESTED COMPLETION. The worker claims done because it intends to
be done, not because verifiable evidence exists on disk.

An adapter MAY close that loop with a runtime gate that refuses to end a worker session until
verifiable evidence exists on disk (EVID=true / WT_CLEAN=true in a ledger touched in window;
e2e_verified or status:done in a readiness doc in window; a passing verify-findings summary from
`<SUBSTRATE>/verify_findings.py`; test-runner artifacts; Playwright screenshots). This is OPTIONAL,
opt-in, and adapter-specific — the tool-agnostic core defines the discipline; each runtime supplies
its own enforcement mechanism. Three discipline levels (generic):
- **Loose** (no gate installed, default): self-attested, trust-based.
- **Strict** (gate installed, defaults): ≥1 evidence kind in a freshness window (default 30min).
- **Paranoid** (`STOP_VERIFY_STRICT_PROGRESS=1`, `STOP_VERIFY_MIN_KINDS=3`): both progress flags
  AND three distinct kinds.

Reference implementation: the Claude Code adapter ships a Stop hook
(`skills/autonomous-fleet-adapter-claude-code/assets/hooks/stop-verify.sh`) that emits
`{decision:"block", reason:"..."}` so Claude Code refuses to terminate. Install + configuration:
see `references/strict-mode.md` and the claude-code adapter. Other runtimes can wire the same
discipline to their own mechanism (Codex automations, a Grok scheduler, an Orca gate) — but NONE
DOES today: Layer 2 is shipped for Claude Code only, and a run on any other adapter operates at
the Loose level regardless of operator intent (record that in DECISIONS.md when strictness was
requested). Lineage:
claude-code-orchestra's stop-verify.sh (mtime-window scan) + multi-llm-plugin-cc's
stop-review-gate-hook.mjs (the {decision:"block"} JSON contract), composed for the fleet's
progress.md/readiness.md ledger format (see `docs/competitor-audit-2026-06-22.md` #2). Fail-open by
design: any internal gate error allows session end with a stderr warning — a broken gate trapping a
worker is a worse failure than a missed gate. The gate is one more layer ON TOP OF existing
disciplines, not a replacement.

═══════════════════════════════════════════════════════════
ARCHIVE_ENABLED: every run leaves a manifest-audited file trail under `.fleet/runs/<run_id>/`.
═══════════════════════════════════════════════════════════
STRICT MODE detects evidence; ARCHIVE_ENABLED is what PRODUCES the evidence in a known location
with a known shape. Without an archive, EVID flips on transient files that get garbage-collected
between runs; the verifier-summary the stop-verify hook scans for is impossible to find on the
NEXT run (the run-archive scheme is the ONLY thing that lets INFLATION POST-MORTEM cite specific
claims back to the file that proved them). With an archive, every artifact a run produced — the
findings JSON, the verifier summary, the reviewer blind-fix files, the readiness doc, the prompts
the coordinator used, the final diffs — lives at a deterministic path under one directory per run,
with a manifest naming each file and its sha256.

HARD RULE — archive layout. Every run that emits ANY first-class artifact (findings JSON,
verifier summary, blind-fix file, readiness doc) lands under
`.fleet/runs/<run_id>/` where `<run_id>` follows the deterministic format:

  YYYYMMDDTHHMMSSZ-<mission>-<short-hash>

A UTC timestamp (sortable), the mission slug (greppable), and a 6-char random hex suffix
(`secrets.token_hex`) for collision avoidance — two runs on the same coordinator-pid in the same
second still get distinct ids. Example: `20260623T141522Z-adversarial-review-and-fix-3a9c2f`.
This shape is the ONLY one the run-archive validator accepts; freeform run-ids (operator pet
names, branch names, etc.) are rejected because they break sort-by-time auditability.

HARD RULE — manifest. Each archive directory MUST contain `manifest.json` listing every file
the run produced. The manifest is the AUDIT TRAIL — without it, the directory is a collection of
files with no provenance and the post-hoc replay machinery (INFLATION POST-MORTEM, T-FINAL's
"recommend next missions") has nothing to chain against. Each entry carries: `path` (relative to
the archive dir), `kind` (one of: `findings`, `verify_summary`, `blind_fix`, `prompt`,
`response`, `diff`, `readiness`, `progress`, `other`), `sha256`, `mtime_utc`, `producer`
(the worker/reviewer slug that wrote it), `bytes`. The schema is shipped at
`skills/autonomous-fleet-core/assets/fleet-run-manifest.schema.json`.

HARD RULE — mtime ordering invariants. The validator enforces causal ordering between certain
kinds, because these orderings ARE the disciplines from Layers 1–3:

- A `blind_fix` MUST have mtime BEFORE every `findings` file from the same reviewer in the same
  run (Layer 3 ANTI-ANCHORING protocol — the reviewer must commit its blind fix before
  reading the candidate diff).
- A `verify_summary` MUST have mtime AFTER the `findings` file it audits (Layer 1's verifier
  runs AGAINST a findings doc; a summary older than the findings is a stale audit from a
  previous run, mis-archived).
- A `readiness` doc MUST have the LATEST mtime in the archive — it's the final artifact T-FINAL
  emits, and any artifact mtime-after it means a later edit was made outside the run boundary.

A manifest whose listed files don't satisfy these orderings FAILS validation, even when every
checksum matches. The discipline is not "files exist"; it's "files exist in the order the
discipline demands".

HARD RULE — `archive_enabled: true` is a precondition for `status: done` in any mission that
emitted first-class artifacts. T-FINAL writes the manifest as its final step and sets
`archive_enabled: true` in the fleet-outcome. A mission that shipped findings but no manifest
ships as `status: partial`, not `done` — the run is not auditable, the discipline is not satisfied.
Missions that emit no first-class artifacts (a pure documentation-update mission, say) OMIT the
field — the field is gated on artifact production, not on mission existence.

Retention. The fleet does not garbage-collect run-archives. Operators decide retention out-of-band
(e.g. delete `.fleet/runs/` directories older than N days); the engine loop never prunes. The archive is auditable for as long as it sits on disk. A run that prunes a still-cited
archive (a readiness doc references a manifest entry that no longer exists) is recorded as a
broken provenance link by `validate-all.sh` but does NOT fail the build — old runs degrade
gracefully into "we know it ran, we no longer have the trail".

Lineage: composed for the fleet from the run-archive pattern observed across multi-vendor
agent frameworks (claude-code-orchestra's per-session output dirs, multi-llm-plugin-cc's
plugin-run logs, GodModeSkill's verifier corpus index). The manifest+mtime-ordering+kind
taxonomy is the fleet's specific contribution — none of the upstream patterns enforce all three.
See `docs/competitor-audit-2026-06-22.md` #8.

═══════════════════════════════════════════════════════════
INFLATION POST-MORTEM: break the "we already shipped that" trap on re-runs.
═══════════════════════════════════════════════════════════
TRIGGER: a prior run claimed completion that the RESULT-STATE gate later disproved.
CORE RULE: before BOOTSTRAP, re-read the prior readiness doc and list every green-CI-but-not-real claim as the FIRST entries of the new CLOSE-INDEX.
FULL DOCTRINE (read when the trigger applies): `references/inflation-postmortem.md`.

═══════════════════════════════════════════════════════════
SIGNAL RECONCILIATION — three signals, never transition on one read (from Agent Orchestrator;
Apache 2.0, Copyright Untrivial — see ATTRIBUTIONS.md).
═══════════════════════════════════════════════════════════
TRIGGER: any WAIT loop, task-health decision, or terminal-flag write.
CORE RULES: never transition on ONE read (DETECTING state: 3 consistent polls or 5-min timeout, evidence-hash keyed); before ANY terminal flag re-verify the external SCM/CI fact and let it OVERRIDE the ledger.
FULL DOCTRINE (read when the trigger applies): `references/signals.md`.

═══════════════════════════════════════════════════════════
SUBSTRATE KILL-SWITCH CONVENTION — operator escape hatch + bench comparator.
═══════════════════════════════════════════════════════════
Each verification-substrate layer honors a `FLEET_DISABLE_*` env var. When set truthy
(case-insensitive `1`/`true`/`yes`/`on`), the layer's CLI exits 0 with a `<layer>: DISABLED via
<NAME>=1 (no-op exit 0)` stderr notice, BEFORE arg parsing. The four core-layer knobs are
`FLEET_DISABLE_VERIFY_FINDINGS` / `FLEET_DISABLE_STOP_VERIFY` / `FLEET_DISABLE_BLIND_FIX` /
`FLEET_DISABLE_RUN_ARCHIVE`; the COMPLETE authoritative registry (nine knobs across three
classes, including the security-class knobs that additionally require an explicit
acknowledgement env var) lives in `references/substrate-disable-knobs.md` — this block
deliberately does NOT duplicate it (a stale copy here caused a documented contradiction,
issue #85).
"Disabled" means "treat the layer's verdict as PASS for this run" — explicit operator contract.
Strict truthy allow-list prevents typos from silent-disabling. Used by
`scripts/bench-adversarial.sh` (framework clone only) to flip substrate off/on for the falsifiable comparator that defends
the substrate's value claim. Implementation: `<SUBSTRATE>/lib/substrate_disable.py`. Full doctrine:
`references/substrate-disable-knobs.md`.

═══════════════════════════════════════════════════════════
CONTEXT HANDOFF — survive your own context limit.
═══════════════════════════════════════════════════════════
Compaction alone is NOT sufficient and will eventually drop your loop state. The ledger file is
your EXTERNAL BRAIN: phase marker + per-task rows with flags + PR numbers + live worker handles +
placements + next ready wave + DECISIONS.md rationale — enough for a FRESH coordinator with zero
prior context to resume. On context pressure (degrading responses, lost handles, uncertainty about
what's done): do NOT push through, do NOT ask the user; write a complete CONTEXT HANDOFF block into
the ledger and state a fresh coordinator resumes from it.
HANDOFF CARRIES: the run's RUN_ID + RUN_SHORT + resolved LEDGER_DIR and ledger paths FIRST
(a fresh coordinator re-exports FLEET_RUN_SHORT before touching the registry); then for each
task carry branch, PR#, reviewed SHA, WT path or environment id, WT_CLEAN,
MERGED, live worker handle, placement, and next action.
PROACTIVE (don't wait for the cliff): the coordinator's own context grows with every wave. As each
wave of tasks completes, roll its detail UP into a one-line-per-task summary in the ledger (task,
PR#, MERGED, key decision) and drop the raw per-task chatter from working context. Carry forward the
rolling summary + the next ready wave, not the full history. This bounds coordinator context so the
loop survives a long campaign without ever hitting the handoff cliff.

═══════════════════════════════════════════════════════════
PLAN/DAG VALIDATION GATE — validate the frozen task DAG before the FIRST SPAWN_WORKER.
═══════════════════════════════════════════════════════════
The decomposition is already frozen by the time you spawn; a cheap structural check on it before the
first worker launches catches a malformed plan before it costs a wave of workers. Run ONCE, right
before the first SPAWN_WORKER, over the frozen task DAG in the ledger:
- NO CYCLES: the dependency edges form a DAG. A cycle means the freeze is wrong — STOP, name it in
  DECISIONS.md, re-decompose; never spawn into a deadlock.
- DEPENDENCIES RESOLVABLE: every declared dependency names a task that exists in the frozen set (no
  dangling/typo'd edge). An unresolvable edge means a task can never become ready — fix the freeze.
- PARALLELISM WIDTH COMPUTED: the max set of tasks with all dependencies satisfied at once. Record
  it in the ledger; it bounds the initial spawn wave (with the concurrency cap) and feeds WORKER
  PLACEMENT. A width of 1 on a multi-task mission is a smell the decomposition over-serialized.
This is a structural check on an ALREADY-frozen artifact, not re-planning: O(tasks+edges), no
workers, no model spend. Empirically: validating the DAG before any worker spawns catches
mis-decomposition cheaply (the cost is one extra coordinator pass; the alternative is failed
workers and burned model spend). A mission that declares no inter-task dependencies passes
trivially.
