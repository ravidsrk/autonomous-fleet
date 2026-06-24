<!-- title: Glossary | description: Every framework-specific term in autonomous-fleet, defined once, with a link to the chapter that goes deep. | sidebar_order: 20 -->

# Glossary

**On this page:** [How to use this glossary](#how-to-use-this-glossary) ·
[Engine and orchestration](#engine-and-orchestration) ·
[The run-archive](#the-run-archive) ·
[The substrate](#the-substrate) ·
[Roles and topology](#roles-and-topology) ·
[Missions and campaigns](#missions-and-campaigns) ·
[Running and safety](#running-and-safety) ·
[Extending](#extending)

This is the lookup table. Every term the rest of the guide uses with a specific, load-bearing
meaning is defined here once, in one paragraph, with a pointer to the chapter that goes deep. If
you hit a word in another chapter and it does not click, this is where you come back to.

## How to use this glossary

The terms are grouped by where they live in the system, not alphabetically, because that is how
they make sense: engine terms cluster, substrate terms cluster, role terms cluster. Inside each
group the order is roughly "you meet this first" to "you meet this last". Every definition ends
with a `see` link to the chapter where the term is used in anger.

One honesty note up front, because two terms below carry a caveat the rest of the docs repeat:
the trace stream is real and schema-pinned, but in production code today exactly one event is
wired (`T-FINAL`); and headless campaign mode exists but is not yet validated end to end. Both
are flagged at their entries so you do not read more into them than is true on `main` today.

## Engine and orchestration

### primitive

One of the operations the engine calls but never implements itself. The core defines them by name;
each runtime adapter supplies the real command. There are 13 in `engine.md`: `SPAWN_WORKER`,
`DISPATCH`, `WAIT`, `INSPECT`, `PLACE`, the `WORKER_DONE` / `ASK` / `REPLY` trio, `OPEN_PR` /
`MERGE_PR` / `CLEANUP`, `SYNC_TASK_STATE`, and the optional goal/loop set (`SET_GOAL`,
`UPDATE_GOAL`, `GOAL_COMPLETE`, `GOAL_BLOCKED`, `LOOP_POLL`). The core only ever calls primitives,
so the same orchestration logic runs on Claude Code, Codex, Grok, or Orca without change.
See [The engine](06-the-engine.md).

> Note: the trace schema's primitive enum is a separate, smaller list of 11 transition labels
> (the events a dashboard sees), not the same set as the 13 engine primitives. Do not conflate the
> two: the engine primitives are what an adapter implements; the trace primitives are what the
> stream reports. See [Trace schema](16-trace-schema.md).

### coordinator

The single long-running agent loop that owns a run. It reads the ledger, decides the next action,
calls primitives, and never ends its turn while work remains. It does not write code: it sequences
builders, reviewers, and integrators and waits on them. The coordinator runs at the strong model
tier because its judgment is high-leverage and low-volume. See [The engine](06-the-engine.md) and
[Mental model](04-mental-model.md).

### runtime adapter

The skill that maps the engine's abstract primitives to one tool's real commands: how Claude Code
(or Codex, Grok, Orca) spawns a worker, dispatches a task, waits, inspects, places work in a
worktree, and opens or merges a PR. Adapters are interchangeable because the engine only speaks
primitives. See [Installation](02-installation.md) and [Extending](13-extending.md).

### ledger

The directory of files that is the run's memory, not a database. Per-task status rows with boolean
flags, PR numbers, branch names, reviewed SHAs, worker handles, and the `DECISIONS.md` rationale
all live as plain files the coordinator re-reads at the start of every turn. The file is
authoritative; the coordinator's memory is not. A fresh coordinator with zero prior context can
resume a run from the ledger alone. See [Mental model](04-mental-model.md) and
[The engine](06-the-engine.md).

### frozen DAG

The task decomposition, fixed before the first worker spawns. "Frozen" means the run does not
re-plan mid-flight: the freeze emits a directed acyclic graph of task units with dependency edges,
and the engine builds exactly what is inside it. The frozen artifact caps the whole run's scope;
reviewers fail any PR that adds work outside it. See [The engine](06-the-engine.md).

### plan/DAG validation gate

The cheap structural check the coordinator runs once, right before the first `SPAWN_WORKER`, over
the frozen DAG. It rejects three things: cycles in the dependency edges, edges that name a task not
in the frozen set, and (informationally) a parallelism width of 1 on a multi-task mission, which is
a smell that the decomposition over-serialized. It is `O(tasks+edges)`, spends no model budget, and
catches a malformed plan before it costs a wave of workers. See [The engine](06-the-engine.md).

### signal reconciliation

The rule that you never transition a task on a single read. Three signals report task health and
they disagree in normal operation: worker liveness (`INSPECT`), the ledger flag you wrote, and the
external SCM/CI fact (`gh pr view`, CI conclusion). The coordinator holds a contested task in a
`DETECTING` state and only transitions after consistent polls or a timeout, and it re-verifies the
external fact directly before writing any terminal flag (`MERGED` / `DONE`). The SCM wins when it
disagrees with the ledger. See [The engine](06-the-engine.md).

### anti-flap

The mechanism inside signal reconciliation that stops a flapping signal from oscillating a task
between states. A contested task holds in `DETECTING` until N consecutive consistent polls
(default 3) or a hard timeout (default 5 min). The counter is keyed to a hash of the contested
signals with volatile fields (timestamps, activity counters) stripped, so unchanged weak evidence
re-presenting does not reset the counter and genuinely new evidence resets it to 1.
See [The engine](06-the-engine.md).

### T-FINAL

The terminal transition of a run. It runs the worktree-orphan sweep, writes the run-archive
manifest as its final step, and sets `archive_enabled: true` in the fleet-outcome. T-FINAL is also
the one trace event wired in production code today (emitted by `fleet_run.write_manifest`, and
emitted BEFORE the manifest write per the trace-first doctrine). See [The engine](06-the-engine.md),
[Run-archive anatomy](15-run-archive.md), and [Trace schema](16-trace-schema.md).

## The run-archive

### run-archive

The per-run directory under `.fleet/runs/<run_id>/` that holds every first-class artifact a run
produced, with a manifest naming each file and its sha256. The `<run_id>` follows a fixed shape,
`YYYYMMDDTHHMMSSZ-<mission>-<short-hash>` (UTC timestamp, mission slug, 6-char hex), and the
run-archive validator rejects freeform ids. The fleet never garbage-collects archives; operators
prune out of band. See [Run-archive anatomy](15-run-archive.md).

### manifest

The `manifest.json` at the root of each run-archive. It lists every file the run produced, each
entry carrying `path`, `kind` (one of `findings`, `verify_summary`, `blind_fix`, `prompt`,
`response`, `diff`, `readiness`, `progress`, `other`), `sha256`, `mtime_utc`, `producer`, and
`bytes`. The manifest is the audit trail: without it the directory is files with no provenance. Its
schema ships at `skills/autonomous-fleet-core/assets/fleet-run-manifest.schema.json`.
See [Run-archive anatomy](15-run-archive.md).

### mtime ordering

The causal-ordering invariants the run-archive validator enforces between manifest entries, because
the orderings ARE the substrate disciplines. A `blind_fix` must be mtime-before every `findings`
file from the same reviewer in the same run; a `verify_summary` must be mtime-after the `findings`
it audits; the `readiness` doc must have the latest mtime in the archive. A manifest whose files
do not satisfy these fails validation even when every checksum matches.
See [Run-archive anatomy](15-run-archive.md) and [The substrate](07-the-substrate.md).

### evidence-hash

The `evidence_hash` field a trace event uses to reference sensitive evidence by hash instead of
inlining it, because the trace stream is meant for publication to external dashboards and must not
carry secrets or host-absolute paths. See [Trace schema](16-trace-schema.md).

### EVID

The standard close-test boolean for any item lifted from a frozen artifact (an audit, dossier,
finding set). `EVID` is true only when the finding's own evidence reproduction, re-run, no longer
reproduces, or the acceptance criterion the artifact states is demonstrated. Belief, green CI, and
"the diff looks right" do not clear EVID; only the artifact's own repro does. A run terminates only
when every ID in its close-index is closed. See [The engine](06-the-engine.md) and
[Mission catalog](09-mission-catalog.md).

### attestation

A self-attested completion claim a worker writes (for example EVID=true or status:done in a
readiness doc). By default the engine trusts attestations; strict mode replaces that trust with a
disk scan. The fix-attestation file is the specific attestation a fixer writes after closing a
finding. See [Strict mode](11-strict-mode.md) and [Run-archive anatomy](15-run-archive.md).

### findings

The schema-verified output of a reviewer: a structured list of issues against a PR, each with a
category, a quoted line, and a verdict (`approve` / `request_changes`). The shape is pinned by
`skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json`, and a verifier rejects a
finding whose `quoted_line` it cannot locate or whose category requires a missing field (a
`root_cause_depth` finding without `cascade_impact`, for instance). See [The substrate](07-the-substrate.md)
and [Mission catalog](09-mission-catalog.md).

### verify-summary

The output of the findings verifier (`verify_findings.py`): a summary that audits a findings file
and is archived with `kind: verify_summary`. By the mtime-ordering invariant it must be mtime-after
the findings file it audits, because the verifier runs against an existing findings doc.
See [Run-archive anatomy](15-run-archive.md) and [The substrate](07-the-substrate.md).

### fix-attestation

The record a builder writes when it closes a finding: which finding, which PR, and the EVID repro
result. It is the builder's claim that the finding's own reproduction no longer reproduces, which
the build-blind reviewer then verifies against the same frozen artifact. See [Run-archive anatomy](15-run-archive.md).

### seat

The "earns its seat" lens: per-run contribution metrics computed from a run-archive by
`analyze_seat.py`, used to surface roles or models whose findings do not survive blind-fix at a
meaningful rate. It answers "is this reviewer or model worth its cost on this run?". The library is
runtime-dependency-free and reads `run_id`, `archive_enabled`, and `cost_estimate` from the
fleet-outcome. See [CLI reference](18-cli-reference.md).

## The substrate

### the substrate

The four-layer verification stack that catches bad work: Layer 1 schema-enforced findings, Layer 2
the stop-verify hook, Layer 3 the blind-fix mechanical guard, Layer 4 the mutation gate. The layers
compose, each catching what the one below cannot. See [The substrate](07-the-substrate.md).

### stop-verify hook

The Layer 2 mechanism shipped by the Claude Code adapter: a Stop hook that scans for evidence on
disk and emits `{decision:"block", reason:"..."}` so Claude Code refuses to end a worker session
until verifiable evidence exists in a freshness window. It is fail-open by design: any internal gate
error allows session end with a stderr warning, because a broken gate trapping a worker is worse
than a missed gate. It is the reference implementation behind strict mode.
See [Strict mode](11-strict-mode.md) and [The substrate](07-the-substrate.md).

### blind-fix

The Layer 3 anti-anchoring protocol. Before the reviewer opens the candidate diff, it writes its
own independent proposed fix to `reviewer-blind-fix-<finding-id>.md` (point of creation, shape of
change, pre-commit confidence 0-100), and only then reads the patch. A candidate that agrees with
the blind fix at the same call-stack depth earns weight; one at a different depth triggers the
root-cause-depth rule. The filesystem must reflect the order: a blind-fix file mtime-after the
findings is structurally suspect. See [The substrate](07-the-substrate.md) and
[Run-archive anatomy](15-run-archive.md).

### mutation gate

The Layer 4 check: a manifest of code mutations (`tests/mutations.yaml`) where each mutation pins a
specific behavior by asserting that flipping a line makes a test fail. It catches regressions across
all three lower layers and is why mutation testing matters more than line coverage here: a passing
test that does not actually exercise behavior is caught when the mutation does not fail it.
See [The substrate](07-the-substrate.md).

### schema-drift test

The test that pins documentation and code against the shipped schemas: it fails if a primitive,
role, or status named in the docs or in `emit_trace.py` no longer matches the trace schema's closed
enums. It is how the docs that describe schemas stay enforceable rather than aspirational.
See [Trace schema](16-trace-schema.md) and [The substrate](07-the-substrate.md).

### kill switch

The operator escape hatch on each substrate layer: a `FLEET_DISABLE_*` env var that, when set
truthy (`1`/`true`/`yes`/`on`), makes that layer's CLI exit 0 with a `DISABLED` notice before arg
parsing, treating its verdict as PASS for the run. The registry is `FLEET_DISABLE_VERIFY_FINDINGS`
(L1), `FLEET_DISABLE_STOP_VERIFY` (L2), `FLEET_DISABLE_BLIND_FIX` (L3), `FLEET_DISABLE_RUN_ARCHIVE`
(L4). The strict truthy allow-list prevents a typo from silently disabling a layer. Full doctrine
in `references/substrate-disable-knobs.md`. See [The substrate](07-the-substrate.md).

### strict mode

The opt-in discipline level where the stop-verify hook is installed and enforcing, so a Claude Code
worker cannot end its session without evidence on disk. Today it is Claude Code only and, at its
strictest configured level, exits non-zero if `unverified_assumptions > 0` at run end. Loose (the
default) is trust-based; strict requires one evidence kind in a freshness window; paranoid requires
both progress flags and three distinct kinds. See [Strict mode](11-strict-mode.md).

## Roles and topology

### role topology

The builder / reviewer / integrator division of labor, each in its own terminal and usually its own
model family. The shape is structural, not a suggestion: the reviewer never sees the build
conversation, so build-blindness is enforced by separation rather than by instruction.
See [Roles and blindness](08-roles-and-blindness.md).

### builder

The role that writes code: it implements one task unit on its own branch, commits in small logical
increments authored as the maintainer with no agent trailers, adds the regression-catching test the
mission calls for, and pushes. Bulk builders run at the mid model tier; build-failure triage runs at
the cheap tier. See [Roles and blindness](08-roles-and-blindness.md).

### reviewer

The fresh, build-blind role that grades a PR against the unit's acceptance criteria only, with no
edit rights and no access to the builder's session or worktree. When more than one vendor is
available it should be a different vendor than the builder, so a vendor's blind spot is not its own
grader. It runs at the strong tier and actively tries to fail the PR.
See [Roles and blindness](08-roles-and-blindness.md).

### integrator

The role that ships: it opens the PR, and on a passing review confirms the branch HEAD still equals
the reviewed SHA, checks for conflicts against BASE, resolves them preserving both intents, merges
with a merge commit (never squash, all commits preserved), deletes the branch, and cleans the
checkout. See [Roles and blindness](08-roles-and-blindness.md).

### build-blindness

The property that the reviewer cannot see how the code was built, only the diff and the acceptance
contract as text. It is the defense against a model rationalizing its own work, and it is structural
(separate terminals, no shared session) rather than instructed. See [Roles and blindness](08-roles-and-blindness.md).

### single-vendor mode

Running builder and reviewer on the same vendor because only one is installed. You lose cross-vendor
blind-spot diversity (a vendor grading its own family); you keep a fresh, build-blind, same-vendor
reviewer and every other discipline. The run records the single-vendor choice in `DECISIONS.md`.
See [Roles and blindness](08-roles-and-blindness.md).

## Missions and campaigns

### mission

One discrete engineering job: a goal, a role pipeline, a phase/task structure, a ledger filename and
flag set, a done condition, and decision defaults. The shipped missions are `doc-sync`,
`test-coverage`, and `adversarial-review-and-fix`. A mission is the unit you invoke.
See [Mission catalog](09-mission-catalog.md) and [Missions vs campaigns](05-missions-vs-campaigns.md).

### campaign

A DAG of missions with hard verification gates between nodes, where a later node can branch on the
previous node's fleet-outcome. Use a campaign when one repo-health pass means chaining several
missions with gates between them. See [Missions vs campaigns](05-missions-vs-campaigns.md) and
[Campaigns](10-campaigns.md).

### campaign preset

A shipped, ready-to-run campaign YAML under `scripts/campaigns/`. The presets on `main` include
`repo-health`, `ship-with-proof`, and `quality-gate` (the three the guide treats as the active
set), alongside others in the directory. A preset names the missions, their order, and the gates.
See [Campaigns](10-campaigns.md).

### fleet-program

The skill that runs campaigns: it chains missions with gates, reading each node's fleet-outcome to
decide whether the next node runs. It is the campaign-level counterpart to a single mission.
See [Campaigns](10-campaigns.md).

### fleet-outcome

The `fleet-outcome.yaml` a run writes to report its result: status (`done` / `partial` / `blocked`),
metrics like `e2e_verified`, `archive_enabled`, `unverified_assumptions`, `cost_estimate`, and
`deferred_missions`. A campaign gate reads these fields to decide whether to proceed. It is the
machine-readable "what happened". See [fleet-outcome schema](17-fleet-outcome-schema.md).

### exploratory mission

A mission that lives under `docs/exploratory/missions/` rather than `skills/`: it has the doctrine
written but has not earned promotion to a shipped skill. It does nothing until promoted.
See [Mission catalog](09-mission-catalog.md) and [Extending](13-extending.md).

### promotion criteria

The bar an exploratory mission must clear to move back into `skills/`: the three-artifact rule.
Doctrine alone, and tests inherited from `autonomous-fleet-core`, are not enough; the promotion PR
must cite a real coding-agent run. See [Extending](13-extending.md).

### three-artifact rule

The exact promotion bar: a progress doc (`docs/<mission>-progress.md` from a real run, not a stub),
a readiness doc (`docs/<mission>-readiness.md` with a `fleet-outcome` block), and an external
archive (a `.fleet/runs/<run_id>/` the mission produced, or a referenced archive under
`docs/external-dogfood/`). All three must exist and be referenced in the promotion PR.
See [Extending](13-extending.md).

## Running and safety

### headless mode

Driving a runtime's CLI non-interactively (via `run-campaign.sh` / `run-mission-headless.sh`) so a
campaign runs without a chat session, which requires that CLI to be authenticated on the host.

> This path is not yet validated end to end on `main`. The supported flow today is interactive:
> chat, or the host's native `/goal`. Treat headless campaign mode as in-progress.

See [Installation](02-installation.md) and [Campaigns](10-campaigns.md).

### sandbox wrapper

`scripts/run-sandboxed.sh`: the wrapper operators should put around untrusted-target headless runs.
It scrubs credential-shaped env vars before exec and refuses a deny-list of production/publish
command lines (`terraform apply`, `kubectl`, `aws `, `gcloud `, `npm publish`, `cargo publish`,
`gh release`, `git push --tags`). It is best-effort, not a general OS sandbox: it does not confine
filesystem or network reach, so pair it with a real OS-level sandbox.
See [Safety and secrets](12-safety-and-secrets.md).

### blast radius

The scope of damage a run can do. The framework limits it structurally: merge is not deploy, workers
run on testnet/staging/fixtures only, infra changes are written as code but applied as ops out of
band, and the sandbox wrapper plus optional containers cap reach. See [Safety and secrets](12-safety-and-secrets.md).

### `--yolo`

The flag that makes agents auto-approve all tool calls against a repo (Grok only; default off). With
`--yolo`, untrusted inputs become a full remote-code-execution surface, so `--yolo-untrusted-acknowledged`
is required when `--repo` is outside the local clone. Never use it on a repo or inputs you do not
trust. See [Safety and secrets](12-safety-and-secrets.md).

### container-use

The optional sandboxed variant of independent worker placement: when the container-use MCP is
configured (needs Docker), each independent worker runs in its own isolated Linux container on its
own git branch (`container-use/<env>`), instead of a host `git worktree`. It closes the OS-sandbox
gap and the isolation gap in one move. Absent it, placement falls back to plain host worktrees.
See [Safety and secrets](12-safety-and-secrets.md) and [Installation](02-installation.md).

## Extending

### agentskills.io

The skills marketplace and compliance standard the fleet's skills target, so a skill you add stays
installable and discoverable the same way the shipped skills are. Keeping a new skill
agentskills.io-compliant is part of the extending workflow. See [Extending](13-extending.md).

---

← [Previous: FAQ](19-faq.md) ·
[Guide Index](README.md)
