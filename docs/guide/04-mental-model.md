<!-- title: Mental model | description: What a run is: frozen plan, worker fleet, file ledger, and why review is build-blind | sidebar_order: 4 -->

# Mental model

You ran your first mission in [chapter 03](03-your-first-mission.md). You watched a plan file
appear, terminals spawn, PRs open, and a `.fleet/runs/<id>/` directory fill with artifacts. This
chapter answers the question that always comes next: wait, what is this actually doing?

The honest answer is that `autonomous-fleet` is small. It is not a model, not a daemon, not a
hosted service. It is a protocol written down as a skill, plus a directory of files on disk that
records what the protocol decided. Once you see those two things clearly, every behavior in the
framework stops being magic and starts being obvious.

This chapter is the map. It stays at the altitude of concepts. When you want the actual machinery
(the primitive contracts, the validator code, the ledger field layouts), [chapter 06, The
engine](06-the-engine.md) has it. Read this first so the engine chapter has somewhere to land.

**On this page:** [A run is a frozen plan + a fleet + an audit trail](#a-run) ·
[The ledger is files, not a database](#the-ledger) ·
[Workers are processes, not threads](#workers-are-processes) ·
[PRs are the unit of work](#prs-are-the-unit) ·
[The framework is the protocol; the agents are interchangeable](#protocol-not-agents) ·
[Where to go next](#where-next)

<a id="a-run"></a>

## A run is a frozen plan + a worker fleet + an audit trail

A "run" is one invocation of a mission against your repo. It has exactly three parts, and you can
hold all three in your head at once:

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  A RUN                                                               │
  │                                                                     │
  │   1. A FROZEN PLAN          2. A WORKER FLEET       3. AN AUDIT TRAIL│
  │   ─────────────────         ───────────────────     ───────────────│
  │   The task DAG, decided      Separate agent          .fleet/runs/   │
  │   once, up front, then       processes that build,   <id>/, every   │
  │   validated and locked.      review, and ship one    file the run   │
  │   No re-planning             task each. Spawned,     produced, with │
  │   mid-flight.                waited on, retired.      a manifest.    │
  └─────────────────────────────────────────────────────────────────────┘
```

The frozen plan comes first. Before any worker spawns, the coordinator decomposes your request into
a task DAG (a set of tasks plus the dependency edges between them) and freezes it. "Frozen" is
literal: the plan caps the whole run's scope. The coordinator does not bolt on a newly discovered
feature halfway through, does not refactor an adjacent module because it looked messy, does not
expand the work because a worker had an idea. New ideas get routed to `DECISIONS.md` and a
"recommended next missions" list, not into the current build.

The freeze is not a suggestion. There is a structural check that runs once, right before the first
worker spawns, that asserts the DAG has no cycles, that every declared dependency names a task that
actually exists, and that computes the parallelism width (how many tasks can run at once). A
malformed plan is rejected here, cheaply, before it costs you a wave of agents. This is the
PLAN/DAG VALIDATION GATE, and the relevant point for your mental model is: the plan is checked
before it is trusted.

The worker fleet comes second. Each task in the frozen DAG is handed to a worker, which is its own
agent process. Workers build, review, and ship. They report back. They get retired the moment their
PR merges. There is no long-lived worker accreting state across the whole run, because a fresh
worker session per task is cheaper to reason about and harder to corrupt.

The audit trail comes third, and it is not optional. Every run that produces a first-class artifact
(a findings file, a verifier summary, a reviewer blind-fix file, a readiness doc) lands those
artifacts under `.fleet/runs/<id>/` with a deterministic run id of the shape
`YYYYMMDDTHHMMSSZ-<mission>-<short-hash>`, alongside a `manifest.json` that names every file and its
sha256. The archive is what lets anyone (you, a teammate, a future re-run, a dashboard) reconstruct
what happened without trusting anyone's memory of it.

> The discipline is not "files exist." It is "files exist in the order the discipline demands."
> The manifest validator enforces causal ordering between artifact kinds (for example, a reviewer's
> blind-fix file must be older than the findings file it precedes). That ordering IS the proof that
> the protocol was followed. More on this in [run-archive anatomy](15-run-archive.md).

The mental shorthand: a run is a plan you can't change, run by processes you can't see into, leaving
a trail you can't fake. The constraints are the point.

<a id="the-ledger"></a>

## The ledger is a directory of files, not a database

The single most useful thing to internalize about this framework is that there is no database. There
is no server holding run state in memory. There is no queue. The coordinator's entire memory of a
run lives in plain files on disk, and that is deliberate.

Two file surfaces matter:

```
  REPO_ROOT/
  ├── docs/
  │   ├── <mission>-progress.md     ← the LEDGER: phase marker + per-task rows + flags
  │   ├── DECISIONS.md              ← every default the coordinator picked, and why
  │   ├── research-notes.md         ← external facts the run verified, one line each
  │   └── <mission>-readiness.md    ← the final report: what shipped, status, evidence
  └── .fleet/
      └── runs/<run_id>/            ← the run-archive: artifacts + manifest.json (gitignored)
```

The ledger is the progress file under `docs/`. It holds a phase marker, one row per task with the
flags the mission defines (`BUILT`, `PR_OPEN`, `REVIEWED`, `MERGED`, `WT_CLEAN`, and the like), the
PR number, the reviewed SHA, the worktree path, and the next ready wave of work. The coordinator
reads this file FIRST, every single turn, before it does anything else. It reconstructs state from
the file, never from memory.

This sounds like a small implementation detail. It is actually the load-bearing design decision,
and it has three consequences you will feel:

1. A task is done when its flags read true IN THE FILE, not when the coordinator "believes" it is
   done. Belief is not a state. The file is the state. A green test run that the coordinator
   remembers but did not write down does not advance the task.

2. A fresh coordinator with zero prior context can resume a run by reading the ledger. If the
   coordinator hits its context limit mid-run, it writes a handoff block into the ledger and a new
   coordinator picks up exactly where the old one left off, because everything it needs (branches,
   PR numbers, reviewed SHAs, live worker handles, the next action) is in the file. The ledger is
   the coordinator's external brain. Compaction can drop conversational memory; it cannot drop a
   file.

3. You can read it. Open `docs/<mission>-progress.md` in any editor, on any machine, with no tools
   installed, and see exactly where the run is. No dashboard required, no API call, no log
   aggregator. `cat` works.

The run-archive under `.fleet/runs/<id>/` is the second surface, and it is the durable evidence
trail (the ledger is working memory; the archive is the receipt). It is gitignored by default,
because `.agents/` and the fleet's run output are local artifacts, not things you commit. The
manifest inside each archive directory is what makes the trail auditable rather than just a pile of
files.

> One ground truth wins at the edges. The ledger is the coordinator's loop memory, but at any
> terminal moment (marking a task `MERGED` or `DONE`) the external fact overrides the file. The
> coordinator re-checks the actual PR state directly before writing a terminal flag, and the SCM
> wins when they disagree. The file is memory; GitHub is ground truth. This is signal
> reconciliation, covered in [the engine](06-the-engine.md).

<a id="workers-are-processes"></a>

## Workers are processes, not threads: terminal separation is the blind-spot defence

When you watch a run, you see terminals open. A builder in one. A reviewer in another. An integrator
in a third. It is tempting to read this as cosmetic, a nice way to show you parallel progress. It is
not cosmetic. The separation is the defence.

Here is the topology of a single task moving through the pipeline:

```
   TASK: "add a regression test for the parser bug"

   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
   │   BUILDER     │        │   REVIEWER    │        │  INTEGRATOR   │
   │  (process A)  │        │  (process B)  │        │  (process C)  │
   │               │        │               │        │               │
   │ writes the    │  diff  │ NEVER saw the │  PASS  │ checks        │
   │ fix + test,   │ + spec │ build conv-   │ + SHA  │ conflicts,    │
   │ opens a PR    │──text─▶│ ersation;     │──────▶│ merges with a │
   │               │  only  │ grades the    │        │ merge commit, │
   │               │        │ diff alone    │        │ deletes branch│
   └──────────────┘        └──────────────┘        └──────────────┘
        builds                   judges                   ships
```

The reviewer is a separate process that never saw the builder's conversation. It is handed the PR
diff and the acceptance contract as TEXT ONLY. It does not get the build worktree, the builder's
session, or any of the reasoning the builder used to convince itself the work was good. This is the
single most important idea in the whole framework, so it gets its own section ([chapter
08, Roles and blindness](08-roles-and-blindness.md)), but the mental-model version is short:

Build-blindness is structural, not instructed. You cannot reliably tell an agent "review this as if
you didn't write it." It wrote it. It is anchored on its own solution, and rationalizing an existing
artifact is cognitively cheaper than independently re-deriving the correct one. The only way to get
an honest second opinion is to make the second opinion come from a process that genuinely never saw
the first one's reasoning. Separate terminal, separate session, ideally a separate model vendor.
The wall between the processes is the thing that makes the review real.

Two reinforcing disciplines live on top of this:

- The reviewer commits its own independent fix in writing BEFORE it opens the candidate diff. It
  writes what it would do to a `reviewer-blind-fix-<id>.md` file first, then reads the patch, then
  compares. A candidate that agrees with the pre-committed fix earns weight; one that diverges
  triggers a harder look. The filesystem records the order: the blind-fix file is older than the
  findings file, and the archive validator checks it.

- Cross-vendor by default. When more than one agent vendor is available, the reviewer should be a
  different vendor than the builder, so a vendor's blind spot is not grading its own work. You can
  run single-vendor (the framework says so honestly in `DECISIONS.md` and uses a fresh same-vendor
  reviewer), but you give up the cross-vendor diversity when you do.

Why processes and not threads, concretely: threads share memory. Shared memory is exactly the
contamination you are trying to prevent. The point of spawning a worker is to get a clean room. A
thread would defeat the purpose.

<a id="prs-are-the-unit"></a>

## PRs are the unit of work, never one giant blob

A run might touch twelve files across five concerns. It does not produce one enormous pull request.
It produces one PR per task, each independently reviewable, each independently mergeable, each its
own branch and its own merge commit.

```
   ONE RUN                          NOT THIS                  THIS
   (5 tasks)                        ────────                  ────

   task-1 ─▶ PR #41 ─▶ review ─▶    ┌───────────────┐         PR #41  (task-1)
   task-2 ─▶ PR #42 ─▶ review ─▶    │  one 60-file  │         PR #42  (task-2)
   task-3 ─▶ PR #43 ─▶ review ─▶    │   mega-PR     │   vs    PR #43  (task-3)
   task-4 ─▶ PR #44 ─▶ review ─▶    │  nobody can   │         PR #44  (task-4)
   task-5 ─▶ PR #45 ─▶ review ─▶    │   review      │         PR #45  (task-5)
                                    └───────────────┘
```

The reason is the same reason a human team does not ship a 60-file PR: a reviewer cannot honestly
grade a blob. Acceptance criteria blur, regressions hide in the noise, and a single conflict blocks
everything. One PR per task keeps each unit small enough that the build-blind reviewer can actually
fail it on the merits, which is the only kind of review worth having.

The pipeline for each unit is fixed: build, open PR, review, fix, ship. The integrator merges with a
merge commit and never squashes, so every commit the builder made is preserved in history.
Review-fix rounds add commits; they never rewrite history. The branch is deleted after merge, the
worktree is cleaned, and only then does the task count as terminal.

Note what "done" means here, because it trips people up. Merging is not deploying. The framework
merges reviewed work into your integration branch (BASE). It does not push to production, does not
run `terraform apply`, does not deploy. The promotion from your integration branch to `main` (and
any actual deploy) stays a human decision. The fleet ships code into a branch; it does not ship code
into the world.

Also note: the unit caps the scope. A reviewer fails a PR that adds work outside the task's frozen
boundary, even when the tests pass. "It passes" is necessary; it is not sufficient. The PR has to be
the change the task asked for and nothing more.

<a id="protocol-not-agents"></a>

## The framework is the protocol; the agents are interchangeable

This is the idea that ties the rest together, and it is the reason the framework is shaped the way
it is.

`autonomous-fleet` does not contain an agent. It contains a method, written down. The method names a
set of PRIMITIVES (spawn a worker, dispatch a task, wait for completion, inspect state, place work
in a worktree, open and merge a PR) and a set of disciplines that say how those primitives compose
into a safe, auditable run. The method is tool-agnostic on purpose.

```
   ┌───────────────────────────────────────────────────────────────────┐
   │  THE METHOD (tool-agnostic)                                        │
   │  freeze the plan · spawn workers · build-blind review · file       │
   │  ledger · PR-per-task · audit trail · signal reconciliation        │
   └───────────────────────────────────────────────────────────────────┘
            │ calls PRIMITIVES by name; never hard-codes a tool command
            ▼
   ┌──────────────┬──────────────┬──────────────┬──────────────────────┐
   │  ADAPTER:    │  ADAPTER:    │  ADAPTER:    │  ADAPTER:             │
   │  Claude Code │  Codex       │  Grok        │  Orca                 │
   │              │              │              │                       │
   │  resolves    │  resolves    │  resolves    │  resolves the same    │
   │  SPAWN_WORKER│  SPAWN_WORKER│  SPAWN_WORKER│  primitives to ITS    │
   │  to its own  │  to its own  │  to its own  │  own real commands    │
   │  command     │  command     │  command     │                       │
   └──────────────┴──────────────┴──────────────┴──────────────────────┘
```

A run is composed from three pieces, and only one of them is the agent:

- The CORE is the method above. Tool-agnostic. It only ever calls primitives by name.
- A MISSION is the work: the goal, the role pipeline, the task structure, the ledger filename and
  flags, the done condition. ([Chapter 05](05-missions-vs-campaigns.md) covers missions in depth.)
- An ADAPTER is the mechanics: how THIS tool spawns a worker, dispatches a task, waits, inspects
  state, places work in a worktree or branch, and opens or merges a PR. The adapter implements the
  primitives the core calls.

The payoff is that the agent is a swappable part. The repo ships adapters for Claude Code, Codex,
Grok, and Orca, plus a template adapter for adding a new runtime. The core never hard-codes a tool's
command line. It calls `SPAWN_WORKER` by name and lets the active adapter resolve it to whatever
that tool actually does. Change the adapter, run the identical method on a different agent fleet,
get the same disciplines.

This is also why cross-vendor review is even possible. Because the method does not care which vendor
is behind a primitive, a Codex builder reviewed by a Claude reviewer is just two adapters resolving
the same primitives. The protocol is the constant; the vendors are variables.

> One mission per repo at a time. The framework runs one mission against a given repo at a time, on
> purpose: concurrent missions would race on the same files, the same branches, and the same ledger.
> Chaining missions is a real thing, but it is done by sequencing them through a campaign with hard
> gates between nodes, not by running them at once. That distinction is the whole of
> [chapter 05](05-missions-vs-campaigns.md).

<a id="where-next"></a>

## Where to go next

You now have the map. Five ideas, and everything else hangs off them:

```
   A RUN          = frozen plan + worker fleet + audit trail
   THE LEDGER     = files on disk, read first every turn, not a database
   WORKERS        = separate processes; the wall is the blind-spot defence
   THE PR         = the unit of work, one per task, scope-capped, merge ≠ deploy
   THE FRAMEWORK  = a protocol; the agents are interchangeable adapters
```

A note on honesty, because this guide refuses to oversell. Two things are genuinely partial today,
and your mental model should account for them:

- The trace stream is sparse in production right now. The framework defines a trace event for every
  state transition (one JSONL line per transition, the contract a dashboard reads), but only one
  event is wired in production code today: the `T-FINAL` archive event emitted when a run writes its
  manifest. Per-transition emission across the coordinator and adapters is rolling out; the schema
  already covers all eleven of its trace-enum primitives, the stream does not fill them yet. The trace contract is
  real; the full stream is in progress. Details in [trace schema](16-trace-schema.md).

- Headless campaign mode is not yet fully validated end-to-end. The supported path today is the
  interactive one: drive a mission from chat or via a `/goal`-style native goal loop. The
  `run-campaign.sh` headless driver exists but is not yet proven end-to-end, and it carries an auth
  caveat. Run interactively for now. See [safety and secrets](12-safety-and-secrets.md) for the
  headless caveat in full.

Neither of these changes the mental model. They tell you where the edges are, which is exactly what
an honest map should do.

From here, follow the concepts in order:

- [Missions vs campaigns](05-missions-vs-campaigns.md): the unit of work, and when to chain several.
- [The engine](06-the-engine.md): the primitives, the ledger layout, signal reconciliation, and the
  frozen DAG, in full mechanical detail.
- [The substrate](07-the-substrate.md): the four verification layers that catch bad work.
- [Roles and blindness](08-roles-and-blindness.md): why build-blind review is structural, in depth.

---

← [Your first mission](03-your-first-mission.md) ·
[Guide Index](README.md) ·
[Missions vs campaigns](05-missions-vs-campaigns.md) →
