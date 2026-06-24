<!-- title: Extending | description: Add a mission, a runtime adapter, a campaign preset, or a mutation to the gate without touching the engine. | sidebar_order: 13 -->

# Extending autonomous-fleet

**On this page:** [The extension surface](#the-extension-surface) ·
[Adding a mission](#adding-a-mission) · [Adding an adapter](#adding-an-adapter) ·
[Adding a campaign preset](#adding-a-campaign-preset) ·
[Adding a mutation](#adding-a-mutation-to-the-gate) ·
[Promotion criteria](#promotion-criteria) · [agentskills.io compliance](#staying-agentskillsio-compliant)

You extend autonomous-fleet in four places, and none of them is the engine. The whole point of the
design is that the engine (`autonomous-fleet-core`) is tool-agnostic and mission-agnostic: it calls
a fixed set of PRIMITIVES and never hard-codes a runtime command or a mission's logic. So when you
want it to do something new, you add a leaf, not a branch.

This chapter is for the person who has read the engine ([Chapter 06](06-the-engine.md)) and the
substrate ([Chapter 07](07-the-substrate.md)), has run a mission from the catalog
([Chapter 09](09-mission-catalog.md)), and now wants to:

- run an existing mission on a runtime the repo does not ship an adapter for, or
- teach the fleet a new kind of engineering job (a new mission), or
- chain missions into a repeatable pass (a new campaign preset), or
- pin a new safety mechanism so a future refactor cannot silently break it (a new mutation).

> Modifying the engine itself (the primitives, the ledger format, the coordinator loop) is
> contributor scope, not extension scope. It is out of bounds for this chapter. If you find
> yourself wanting to change `skills/autonomous-fleet-core/references/engine.md`, you are no
> longer extending the framework, you are forking its contract. Open an issue first.

## The extension surface

Here is the entire surface, and which directory owns each piece:

```
                    autonomous-fleet repo
                              │
   ┌──────────────┬──────────┴──────────┬───────────────────┐
   │              │                      │                   │
 MISSION        ADAPTER              CAMPAIGN             MUTATION
   │              │                      │                   │
skills/<name>/  skills/             scripts/             tests/
SKILL.md        autonomous-fleet-   campaigns/           mutations.yaml
                adapter-<tool>/     <name>.yaml           (+ a guard test)
                SKILL.md
   │              │                      │                   │
 "a new          "an existing          "an existing        "a mechanism
  job"            job on a new           set of jobs         that must
                  runtime"               in a DAG"           stay caught"
```

Each one has a starting point you copy, a contract you fill in, and a gate that proves you did it
right. The contract is the load-bearing part. The engine reads these files the same way every run,
so if your file is malformed the framework will reject it before it spawns a single worker.

A quick map of what depends on what, so you know how far the blast radius of each change reaches:

```
+----------------+---------------------------+--------------------------------+
| You add a...   | Engine changes?           | Other missions/adapters affec? |
+----------------+---------------------------+--------------------------------+
| Mission        | No                        | No (missions are independent)  |
| Adapter        | No                        | No (every mission runs on it)  |
| Campaign       | No                        | No (references missions by name|
| Mutation       | No                        | No (pins one mechanism)        |
+----------------+---------------------------+--------------------------------+
```

That table is the design thesis in one frame: every extension is additive and isolated. You never
have to read the engine source to add a mission, and you never have to read a mission to add an
adapter.

## Adding a mission

A mission is one discrete engineering job: "sync the docs", "raise coverage on this module",
"red-team and patch". The three shipped missions (`doc-sync`, `test-coverage`,
`adversarial-review-and-fix`) all share the same shape, and a new mission must too. The engine and
the substrate do not change for your mission. You write one `SKILL.md` that declares its GOAL, its
role pipeline, its ledger, and its task structure, and the core runs it.

### Where the scaffold lives

The mission scaffold is documented in the adapter template at
`skills/autonomous-fleet-adapter-template/SKILL.md`, under the "Mission authoring (if you add a
mission skill)" section. That section is the authoritative checklist for what a mission `SKILL.md`
must contain. Read it before you write anything. It is short and it is the contract.

To start a new mission, create a directory `skills/<your-mission>/` with a single `SKILL.md`. The
fastest way to get the shape right is to copy an existing mission and rewrite it. `doc-sync` is the
cleanest reference because it is Tier 1 and self-contained:

```bash
cp -r skills/doc-sync skills/<your-mission>
# then rewrite SKILL.md top to bottom: frontmatter name, GOAL, ROLE PIPELINE, LEDGER, TASK STRUCTURE
```

### The SKILL.md contract

Per the adapter template's mission-authoring section, every mission `SKILL.md` MUST include these
sections. This list is verbatim from
`skills/autonomous-fleet-adapter-template/SKILL.md`:

```
## Required skills    — core + one adapter; pointer to references/composition.md
## Optional skills    — coordinator-only; "Activate when" / "If unavailable"
## Worker skills      — per role (@grok builder, etc.); injected via DISPATCH
## Deferred missions  — table routing out-of-scope work
T-FINAL readiness doc — fleet-outcome YAML first, then Recommended next missions
```

And one hard rule, also verbatim from the template:

> Do not author a second mission loader. Chains and conditional DAGs belong in `fleet-program`.

That rule matters. A mission never loads another mission in the same run. If your mission's GOAL
needs another mission's work, you record that under `## Deferred missions` and let a campaign
([the next section but one](#adding-a-campaign-preset)) chain them. The "one mission per run" rule
is what keeps the run-archive auditable: one run, one frozen plan, one outcome.

Here is the skeleton, matching the section order the shipped missions use (compare against
`skills/doc-sync/SKILL.md`):

```markdown
---
name: your-mission
description: >-
  [Tier N · one-line positioning] What this mission does, when to trigger it,
  and the hard scope boundary (what it will NOT touch). Trigger phrases at the end.
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "your-handle"
  version: "1.0.0"
  tier: "N"
  fleet-component: "mission"
---

# Mission: your-mission

## Required skills

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md`
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill           | Activate when                          | If unavailable                     |
| --------------- | -------------------------------------- | ---------------------------------- |
| `skill-creator` | Editing/validating skills in this repo | Run `./scripts/validate-skills.sh` |

## Worker skills

Inject per role on DISPATCH (workers load these; coordinator does not):

| Role                                      | Skills | If unavailable               |
| ----------------------------------------- | ------ | ---------------------------- |
| @codex (build)                            | —      | Repo README + manifests only |
| @claude (audit, fresh review, integrator) | —      | Repo README + manifests only |

## Deferred missions

| Finding type                       | Route to        |
| ---------------------------------- | --------------- |
| Code bug surfaced but out of scope | `bug-batch`     |
| Undertested area flagged           | `test-coverage` |

## GOAL

State the single job. State the IN scope set and the OUT-of-scope set explicitly. If the mission
surfaces work it is not allowed to do, record it as a finding, do not do it.

## ROLE PIPELINE

- @claude AUDITS (finds the work) — the frozen index.
- @codex BUILDS each unit.
- A fresh build-blind @claude REVIEWS each PR.
- @claude is the INTEGRATOR: opens the PR, merges (conflict-aware), cleans the worktree.

## LEDGER

`docs/<your-mission>-progress.md`. Per-task flags and a frozen index of every unit found in audit.

## TASK STRUCTURE

- T-AUDIT [@claude] — the only discovery task; freeze it, then build.
- T-BUILD… [per unit, loop] — one PR per unit; build → fresh build-blind review → merge.
- T-FINAL [@claude] — verify every index item closed; write docs/<your-mission>-readiness.md
  starting with the fleet-outcome YAML, then Recommended next missions. Ship as the final PR.
```

The `## Worker skills` block is not optional decoration. The engine's WORKER SKILLS doctrine (see
`skills/autonomous-fleet-core/references/engine.md`) requires the adapter to prepend the mission's
per-role `## Worker skills` to the task spec on every DISPATCH. If your mission omits the block, the
adapter has nothing to inject and your workers run skill-blind. Even an empty table (with `—` for
skills) is a deliberate declaration that the role needs no extra skills, and it is what `doc-sync`
ships.

### The fleet-outcome readiness gate

The last thing your mission does is write `docs/<your-mission>-readiness.md`, and the first thing in
that file is a `fleet-outcome` YAML block. This is the machine-readable result a campaign reads to
decide its next node. The schema lives at
`skills/autonomous-fleet-core/references/fleet-outcome.md`; the common fields every mission emits
are:

```yaml
---
fleet-outcome:
  mission: your-mission # required, must match the skill name
  status: done # done | partial | blocked
  repo: <REPO_ROOT> # absolute path
  base_branch: <BASE> # integration branch used
  prs_merged: <n> # count merged this run
  deferred_missions:
    - id: bug-batch
      reason: "..."
      blocker: null
---
```

If your mission introduces a metric that a campaign should branch on (the way `doc-sync` emits
`drift_open`), add it under a `metrics:` key and document it in the mission's own readiness doc. The
`fleet-outcome` validator (`scripts/validate_fleet_outcome.py`) enforces the common-field types, and
a campaign's conditional edges parse the metric values. Do not rely on prose: a campaign reads the
YAML, never the surrounding text.

### Verifying your mission

A new mission must pass the same skill validation every shipped skill passes:

```bash
./scripts/validate-skills.sh          # agentskills.io spec check for every skill, including yours
./scripts/validate-all.sh             # the full gate (skills + schemas + mutations + more)
```

`validate-skills.sh` runs skill-creator's `quick_validate.py` against each directory under
`skills/`. If skill-creator is not installed it tells you the install command, or you can set
`VALIDATE_SKILLS_OPTIONAL=1` to skip it (only do that locally; CI runs it for real). See
[agentskills.io compliance](#staying-agentskillsio-compliant) below for what the validator checks.

> A new mission directory lives in `skills/` ONLY once it has real-run evidence. Until then it
> belongs in `docs/exploratory/missions/`. The [promotion criteria](#promotion-criteria) section
> below is the rule. Do not put an unproven mission in `skills/` just because the SKILL.md
> validates. Validation proves the prompt is well-formed; it does not prove the mission works.

## Adding an adapter

An adapter teaches the core how to drive one specific runtime. The missions never change. The core
never changes. You write one `SKILL.md` that maps each PRIMITIVE the core calls to your tool's real
commands, and then every mission in the library runs on your tool.

The repo ships four adapters (`autonomous-fleet-adapter-claude-code`,
`autonomous-fleet-adapter-codex`, `autonomous-fleet-adapter-grok`,
`autonomous-fleet-adapter-orca`) plus the template you copy
(`autonomous-fleet-adapter-template`).

### Start from the template

```bash
cp -r skills/autonomous-fleet-adapter-template skills/autonomous-fleet-adapter-<your-tool>
# then in SKILL.md: set frontmatter `name` to match the directory, fill in every PRIMITIVE section
```

The template's own instructions are explicit about this (from
`skills/autonomous-fleet-adapter-template/SKILL.md`):

> Copy `skills/autonomous-fleet-adapter-template/` to `skills/autonomous-fleet-adapter-<tool>/`,
> set frontmatter `name` to match the directory, and fill each section below with your tool's real
> commands. Then any mission runs by loading the core + your adapter.

Two decisions you make first, before filling in any primitive, both called out by the template:

1. Pick a branch prefix default for your tool.
2. State your tool's CONCURRENCY MODEL. Does it have a persistent orchestration daemon (like Orca),
   or is the coordinator itself a session (like Claude Code)? That choice decides whether `WAIT()`
   is a real blocking call or ledger-polling, and whether the file ledger is the sole source of
   truth or a daemon also holds state.

### The primitive-by-primitive mapping

The core calls primitives by name and lets your adapter resolve each to a command. The
authoritative list is in `skills/autonomous-fleet-core/references/engine.md` under "THE PRIMITIVES";
the template's "PRIMITIVE → <TOOL> MAPPING" section is the form you fill in. Here is the mapping
surface, with what the core means by each and what your adapter must supply:

```
+----------------------------+----------------------------------------------------------------+
| PRIMITIVE                  | What your adapter must implement                               |
+----------------------------+----------------------------------------------------------------+
| PLACE(kind)                | independent → isolated checkout on its own branch off BASE;    |
|                            | dependent → fresh worker in the current checkout/branch.       |
|                            | Optional: independent via container-use (needs Docker + MCP).  |
| SPAWN_WORKER(role,placement| create a worker in that placement, in auto/max mode. Declare    |
|                            | CAPABILITY TIERS richest-first; map ROLE → AGENT CLI.          |
| DISPATCH(task, handle)     | hand a task spec to a worker so it reports completion.          |
|                            | REQUIRED: prepend the mission's `## Worker skills` for the role.|
| WAIT(types, timeout)       | block if you have a daemon; else poll the file ledger.          |
|                            | A timeout is a checkpoint, not a failure.                       |
| INSPECT()                  | read task/worker/PR/ledger state WITHOUT consuming it.         |
| WORKER_DONE / ASK / REPLY  | worker→coordinator completion, blocking question, the answer.  |
| OPEN_PR / MERGE_PR / CLEANUP| usually gh via your shell. KEEP the conflict-aware merge rule  |
|                            | verbatim. Merge commit, NEVER squash. Clean the checkout.      |
| SYNC_TASK_STATE(task,status| keep the tool's native task view aligned with the ledger.      |
| SET_GOAL / UPDATE_GOAL /   | bind native goal/loop APIs to ledger DONE, if the host has     |
| GOAL_COMPLETE/GOAL_BLOCKED | them. If no goal API (daemon coordinator), map ledger-only.    |
+----------------------------+----------------------------------------------------------------+
```

The goal/loop primitives (`SET_GOAL`, `UPDATE_GOAL`, `GOAL_COMPLETE`, `GOAL_BLOCKED`, and the
`LOOP_POLL` polling primitive in engine.md) are optional. The core says so directly: they are
optional when the host has no goal/loop API, and an Orca-style daemon coordinator using the ledger
plus a `check --wait` loop is sufficient. Document the exact command for each primitive you do
support, and if your tool offers a primitive in several syntaxes across versions, the template's
convention is "try X, fall back to Y." See
`skills/autonomous-fleet-core/references/runtime-goals.md` for the goal-mode binding.

### The role-to-CLI mapping

This is where the cross-vendor blindness rule lives. The template's SPAWN_WORKER section spells it
out: map each role to a concrete agent CLI honouring the cross-vendor rule. Builder is `@codex` (or
`@grok` for design missions), the reviewer is a fresh build-blind `@claude`, the integrator is
`@claude`. If only one vendor is available, you still keep terminal separation (a fresh reviewer
session) and you record that you are in single-vendor mode. The blindness is structural, not
instructed: a reviewer that never saw the build is a different process in a different terminal, not
the same agent told to "pretend you didn't write this."

### The non-negotiables you cannot weaken

The template lists the rules that come from the core and that your adapter must NOT relax. These are
verbatim from `skills/autonomous-fleet-adapter-template/SKILL.md`:

- One PR per unit, commits preserved, NEVER squash, authored by MAINTAINER, no agent/tool trailers.
- Conflict-aware merge (never force a merge over conflicts or a red suite).
- Checkout cleanup on every merge.
- Safety rails (testnet/staging/fixtures only; merge is not deploy; infra-is-code).
- Secret hygiene (gitleaks / self-check before every commit/push).
- File ledger is the durable source of truth; the coordinator never ends its turn with work
  remaining and never asks the user to continue.
- One in-flight unit per hot file; parallelize across non-overlapping files; chains 3 to 4 deep.

If your adapter cannot honour one of these (say your runtime cannot block cross-worker for an
`ASK`), the template tells you the substitute: record a BLOCKED item in the ledger with a DECISION
DEFAULT, never escalate to the user. The contract bends to the ledger, never to a human prompt.

### What "ready" and "done" mean

The template asks you to state, in the SPAWN_WORKER and WAIT sections, exactly what "ready" means
for a spawned worker (how the coordinator waits for it before DISPATCH) and the distinction the
core insists on: an active worker is alive, not done. A timeout in `WAIT()` is a checkpoint, not a
failure. Getting these two definitions right is what separates an adapter that hangs from one that
makes progress, so do not leave them implied.

### Verifying your adapter

Same gate as a mission, since an adapter is a skill:

```bash
./scripts/validate-skills.sh    # your adapter SKILL.md must pass agentskills.io validation
./scripts/validate-all.sh       # full gate
```

There is no "run every mission against your adapter" automated test in the repo today; the adapter
is proven the same way a mission is, by a real run that produces an archive (see
[promotion criteria](#promotion-criteria)). The diagnostics section of the template tells you to
document how to diagnose a worker that finished without reporting, and how the coordinator survives
its own context limit via the CONTEXT HANDOFF block in the ledger. Fill those in; they are what you
will reach for the first time a run stalls.

## Adding a campaign preset

A campaign is a DAG of missions with verification gates between nodes. A preset is a named campaign
YAML the framework ships under `scripts/campaigns/`. Adding a preset does not touch the engine, the
missions, or the adapters: it references missions by name and wires their edges.

> Campaign presets reference missions that must already exist in `skills/`. A preset that names a
> mission still sitting in `docs/exploratory/missions/` will not run, and the repo's convention is
> to comment that node out (with a pointer to the promotion criteria) rather than bind an edge to an
> undefined mission. Every archived preset in the repo is archived for exactly this reason.

### The preset shape

The shipped presets live at `scripts/campaigns/*.yaml`. Three are active today (`repo-health`,
`ship-with-proof`, `quality-gate`); three more (`align-then-ship`, `secure-ship`,
`handoff-to-product`) are archived because their missions moved to `docs/exploratory/`. The simplest
active preset, `scripts/campaigns/repo-health.yaml`, shows the whole shape:

```yaml
campaign: repo-health
repo: single
base: fleet/repo-health-base
start: docs
nodes:
  docs: { mission: doc-sync }
  tests: { mission: test-coverage }
edges:
  docs: [{ to: tests, if: always }]
  tests: []
```

The fields:

```
+-----------+------------------------------------------------------------------------+
| Key       | Meaning                                                                |
+-----------+------------------------------------------------------------------------+
| campaign  | the preset name (matches the filename)                                 |
| repo      | single (one repo): the repo placement model                            |
| base      | the integration branch the whole campaign builds onto                  |
| start     | the node id the DAG begins at                                          |
| nodes     | id → { mission: <skill-name> }; every mission must exist in skills/    |
| edges     | id → [ { to: <id>, if: <condition> } ]; the DAG wiring + gate per edge |
| post_gates| optional list of gate skills run after the DAG completes (e.g. ship)   |
+-----------+------------------------------------------------------------------------+
```

`ship-with-proof` shows a three-node chain plus post-gates:

```yaml
campaign: ship-with-proof
repo: single
base: fleet/ship-with-proof-base
start: audit
nodes:
  audit: { mission: adversarial-review-and-fix }
  tests: { mission: test-coverage }
  docs: { mission: doc-sync }
post_gates:
  - ship
  - qa
edges:
  audit: [{ to: tests, if: always }]
  tests: [{ to: docs, if: always }]
  docs: []
```

### The gates between nodes

Each edge carries an `if` condition. `if: always` runs the next node unconditionally. A conditional
gate branches on a metric from the previous node's `fleet-outcome` block, which is exactly why your
mission emits that YAML. The repo's archived `secure-ship` preset documents the canonical form in its
header comment: the audit-gated edge `if: findings_open == 0` is "the load-bearing part to
preserve." So a conditional edge looks like:

```yaml
edges:
  audit: [{ to: deps, if: findings_open == 0 }] # only proceed if the audit closed every finding
```

The left side of the comparison is a metric key the upstream mission wrote into its `fleet-outcome`
`metrics:`; the campaign runner evaluates the expression against that value. This is the mechanism
that makes a campaign a gated pipeline rather than a blind sequence: a node that comes back
`blocked` or fails its gate halts the chain instead of cascading bad work forward.

### Running and dry-running your preset

Validate the plan before you spend any agent budget:

```bash
./scripts/run-campaign.sh grok --preset <your-preset> --dry-run
```

`--dry-run` prints the plan only and does not invoke agents (`run-campaign.sh` Usage:
`run-campaign.sh <grok|claude|codex> (--preset NAME | --campaign PATH) [options]`). The first
positional argument is the runtime, then either `--preset NAME` for a shipped preset or
`--campaign PATH` for an arbitrary YAML you wrote outside `scripts/campaigns/`.

> Headless campaign mode (`run-campaign.sh` driving each runtime's CLI non-interactively) is not yet
> fully validated end-to-end. The supported path today is the interactive one: invoke a mission or
> the campaign skill (`fleet-program`) from a chat / `/goal` session. Use `--dry-run` to inspect the
> plan, and treat a full headless campaign run as experimental. See
> [Chapter 12, Safety and secrets](12-safety-and-secrets.md) for the headless-auth caveat in full,
> and [Chapter 10, Campaigns](10-campaigns.md) for running campaigns the supported way.

Adding a brand-new preset to the shipped set under `scripts/campaigns/` is a contributor task: it
ships with the repo, so it belongs in a PR with a CONTRIBUTING-style review. For your own one-off
chains, write the YAML anywhere and pass it with `--campaign PATH`. You do not have to land a file
in `scripts/campaigns/` to chain missions.

## Adding a mutation to the gate

The mutation gate is Layer 4 of the substrate ([Chapter 07](07-the-substrate.md)). It is the
mechanism that proves your tests actually test something. Every entry in `tests/mutations.yaml`
introduces a representative bug into the code and asserts that a named guard test FAILS. A mutation
whose guards still pass SURVIVED, which means the test is weak or tautological. You add an entry
every time you add a mechanism, so that "if this breaks, a test notices" is pinned forever.

The manifest header states the doctrine directly (from `tests/mutations.yaml`):

> Each entry: a representative bug (`find` -> `replace`) in the code-under-test, and the `guards`
> that MUST catch it. The gate applies the mutation, runs the guards, and asserts they FAIL. A
> mutation whose guards still pass SURVIVED = a weak/tautological test. Add an entry whenever you
> add a mechanism: it pins "if this breaks, a test notices." Keep `find` strings exact and unique.

### The entry shape

Each entry has five keys. Here is a real one from `tests/mutations.yaml`, the trace-event
validation pin:

```yaml
- id: trace-event-validation-off
  file: scripts/lib/emit_trace.py
  find: "primitive not in PRIMITIVES"
  replace: "False"
  guards: [tests/test_emit_trace.py]
```

```
+---------+----------------------------------------------------------------------------+
| Key     | Meaning                                                                    |
+---------+----------------------------------------------------------------------------+
| id      | a unique, descriptive slug (kebab-case; says what breaks)                   |
| file    | the file the mutation is applied to, repo-relative                         |
| find    | an EXACT, UNIQUE substring in that file (the correct code)                  |
| replace | what to swap it for (the representative bug)                               |
| guards  | the test file(s) that MUST fail once the bug is applied                     |
+---------+----------------------------------------------------------------------------+
```

The `find` string is the part people get wrong. It must be exact and unique in the target file, or
the gate cannot apply the mutation deterministically. The convention across the manifest is to pick
the smallest distinctive fragment of the line, often a condition: `'unverified == 0'`,
`'if blind_mt >= findings_mt:'`, `"isinstance(holder_pid, int) and _pid_alive(holder_pid)"`. The
`replace` is the inversion or neutering that represents the bug: flipping a comparison, swapping a
guard to `False`, or relaxing a bound (`'"$VISITS" -ge 3'` to `'"$VISITS" -ge 99999'`).

### Picking a good mutation

A mutation is only as good as the bug it represents. The shipped manifest groups them by mechanism
(fleet-outcome validators, sandbox blast-radius classifier, campaign DAG runner, the 4-layer
verification substrate, trace emission, lock safety, kill-switch convention). When you add a
mechanism, find the single line whose inversion would be the most damaging silent failure, and pin
that. For example the lock second-liveness check is pinned by:

```yaml
- id: lock-steal-second-liveness-check-off
  file: scripts/lib/locks.py
  find: "if _pid_alive(current_holder_pid):"
  replace: "if False:"
  guards: [tests/test_locks_review_fixes.py, tests/test_review_fixes_2.py]
```

Note that a single mutation can list multiple guards. List every test that should catch the bug, not
just one; if the mechanism is important enough to pin, it is important enough to be defended by more
than a single assertion.

### Writing the guard first

The discipline is the same as a bug fix: write the failing test that catches the bug before you
trust the mutation. Add (or confirm) a guard test that asserts the correct behaviour, then add the
mutation entry pointing at it, then run the gate and confirm the mutation is CAUGHT (the guard
fails under the bug). A mutation you add without first confirming the guard catches it can SURVIVE
silently, which is the exact failure the gate exists to prevent.

### Running the gate

```bash
./scripts/mutation-check.sh                       # every mutation in the manifest
./scripts/mutation-check.sh --id <your-id>        # just yours, while iterating
./scripts/mutation-check.sh -q                    # quiet: print only survivors / stale entries
```

`mutation-check.sh` is a thin wrapper over `scripts/mutation_check.py`, which reads
`tests/mutations.yaml` by default (override with `--manifest PATH`), applies each mutation, runs its
guards, and asserts they fail. The `--id` flag is repeatable, so you can scope a run to a few
entries while iterating. The full gate runs as part of `./scripts/validate-all.sh`.

> A mutation entry is also how you catch DOC drift against code, not just test weakness. The manifest
> already pins prose rails: it mutates a sentence in `engine.md` (for example inverting `FROZEN SCOPE
BOUNDARY`) and asserts a structural test rejects the inversion. If your extension adds a doctrine
> sentence that a test depends on, pin it the same way.

## Promotion criteria

A mission lives in `skills/` only once it has real-run evidence. Until then it lives in
`docs/exploratory/missions/`. This is the three-artifact rule, and it is the gate that keeps the
framework's shipped surface area mapped 1:1 to missions that have actually run. The authority is
`docs/exploratory/missions/README.md`.

### The three-artifact rule

From `docs/exploratory/missions/README.md`, a mission stays in `skills/` only if ALL three are true:

```
+----+--------------------------------------------------------------------------------+
| #  | Artifact                                                                       |
+----+--------------------------------------------------------------------------------+
| 1  | docs/<mission>-progress.md:  written from a REAL run on a real repo             |
| 2  | docs/<mission>-readiness.md: with a valid fleet-outcome block from that run     |
| 3  | An external-repo run-archive: either .fleet/runs/<id>/ in this repo naming      |
|    | the mission, OR a reference under docs/external-dogfood/                        |
+----+--------------------------------------------------------------------------------+
```

A mission that fails any one of these checks is moved out of `skills/` and into
`docs/exploratory/missions/<mission>/`. The README is blunt about why doctrine is not enough:

> Doctrine alone is not sufficient. Tests inherited from `autonomous-fleet-core` are not sufficient.
> The promotion PR must cite a real coding-agent run that produced the archive.

So a well-formed SKILL.md that passes `validate-skills.sh` is necessary but not sufficient.
Validation proves the prompt is well-formed. Promotion requires a run. That is the difference
between "documented" and "shipped," and the directory split (`skills/` vs
`docs/exploratory/missions/`) is the framework being honest about which is which.

### The promotion process

When your exploratory mission earns its three artifacts, the README lays out the exact sequence to
move it back into `skills/`:

```
1. Run the mission on a real repo via a campaign; it must produce a valid fleet-outcome block.
2. Archive the run to .fleet/runs/<run_id>/ with a passing validate_run_archive.py.
   (External repo? Reference it under docs/external-dogfood/<mission>-<repo>.md.)
3. Write docs/<mission>-progress.md documenting the run end-to-end.
4. Write docs/<mission>-readiness.md with the fleet-outcome block from the run.
5. git mv docs/exploratory/missions/<mission> skills/<mission>
6. Remove `status: exploratory` from the SKILL.md frontmatter; strip the exploratory admonition.
7. Update consumers: skills/autonomous-fleet/SKILL.md, its references/missions.md, README.md's
   mission list, and any scripts/campaigns/*.yaml that should re-include it.
8. Update the marketplace packet to mention the newly promoted mission.
9. Open a PR citing the run id, the archive path, the progress doc, and the readiness doc.
```

The README's closing line is the whole philosophy in one sentence:

> A demotion can be reversed; doctrine alone cannot promote. The artifact is the gate.

The same evidence bar applies to a new adapter, by the same logic. An adapter that has never driven
a real run is an unproven claim. Prove it with an archived run before you present it as shipped.

> The nine demoted missions currently in `docs/exploratory/missions/` (for example `bug-batch`,
> `cleanup`, `dependency-update`, `legacy-rebuild`) are the worked examples of this rule. Each one's
> entry in the README states exactly which of the three artifacts it is missing. Read them before
> you write a new mission; they show you what "not yet proven" looks like in practice.

## Staying agentskills.io compliant

Every skill you add, mission or adapter, is validated against the agentskills.io spec the same way
the shipped skills are. The gate is `./scripts/validate-skills.sh`, which runs skill-creator's
`quick_validate.py` against each directory under `skills/`. To keep yours passing:

- Frontmatter is required. Your `SKILL.md` opens with a YAML block: `name` (must match the
  directory name exactly), `description`, `license`, and the `metadata` map the shipped skills use
  (`author`, `version`, `fleet-component`, and `tier` for missions). Match the shape in
  `skills/doc-sync/SKILL.md` or `skills/autonomous-fleet-adapter-template/SKILL.md`.
- The `name` in frontmatter MUST equal the directory name. When you copy a template, renaming the
  directory without updating `name` is the single most common validation failure.
- An adapter that is a reference, not a runnable mission, declares it: the template sets
  `metadata.runnable: "false"` and `compatibility` says "not a runnable mission." Carry that forward
  if your adapter is a template; clear it if it is a real, runnable adapter.
- Keep the description a real description: what the skill does, when to trigger it, the scope
  boundary, and trigger phrases. The validator and the routing layer (`autonomous-fleet`) both read
  it.

Run the validator locally before you push:

```bash
./scripts/validate-skills.sh
# Output is "OK <name>" or "FAIL <name>: <reason>" per skill. CI runs this for real.
```

If skill-creator is not installed, the script prints the install command
(`npx skills add https://github.com/anthropics/skills --skill skill-creator -y -p`), or you can set
`VALIDATE_SKILLS_OPTIONAL=1` to skip it locally. Do not rely on that escape hatch in CI; the gate is
there so a malformed skill never reaches `main`.

Once your skill validates and (for a mission or adapter) has earned its promotion evidence, it is a
first-class part of the framework: every campaign can reference it, every adapter can run it, and
the mutation gate stands ready for the next mechanism you pin.

---

← [Prev: Safety and secrets](12-safety-and-secrets.md) ·
[Guide Index](README.md) ·
[Next: Troubleshooting](14-troubleshooting.md) →
