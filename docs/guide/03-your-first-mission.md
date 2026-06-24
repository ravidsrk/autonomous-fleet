<!-- title: Your first mission | description: Run doc-sync end-to-end on a tiny repo and read every artifact it leaves behind | sidebar_order: 3 -->

# Your first mission

**On this page:** [The example repo](#the-example-repo) · [The kickoff](#the-kickoff) ·
[The plan file](#the-plan-file) · [The workers spawn](#the-workers-spawn) ·
[The PRs appear](#the-prs-appear) · [The run-archive](#the-run-archive) ·
[What "done" means](#what-done-means) · [Where to go next](#where-to-go-next)

The [Quickstart](01-quickstart.md) got you a green PR. The [Installation](02-installation.md)
chapter got the skills onto whichever runtime you picked. This chapter is the one that builds
trust: we run `doc-sync` on a small repo and stop at every step so you can see what the fleet is
doing, what it writes to disk, and how to read it back. By the end you will recognize every file
under `.fleet/runs/<id>/` and know which two lines of `fleet-outcome.yaml` actually mean "this run
is done."

We use `doc-sync` because it is the safest mission to learn on. It only touches documentation, never
application logic, and it has the highest cross-agent merge-success rate of any AI-agent PR category
(~84% in the AIDev dataset of ~33k PRs, arXiv:2601.15195, Ehsani et al., MSR 2026). Its own SKILL.md
calls it "safe to run unattended." If you are going to watch a mission once before trusting it, this
is the one.

> This chapter walks the mission as a reader and an observer. It does not explain how the engine
> decides what to do under the hood, that is the [Mental model](04-mental-model.md) chapter and
> [The engine](06-the-engine.md). Here we stay on the surface: what you type, what you see, what
> lands on disk.

```
  YOU TYPE                  THE FLEET WRITES                  YOU READ BACK
  ─────────                 ────────────────                  ─────────────
  /doc-sync ...      ─►     docs/doc-sync-progress.md   ─►    the plan (abort here if wrong)
                           (the ledger + DRIFT INDEX)
                                    │
                                    ▼
                           workers spawn in their own  ─►    terminal output / agent panel
                           terminals (build, review)
                                    │
                                    ▼
                           one PR per doc area         ─►    GitHub PR list
                           + a readiness doc
                                    │
                                    ▼
                           .fleet/runs/<id>/           ─►    the run-archive (this chapter)
                           manifest.json + fleet-outcome.yaml
```

## The example repo

You do not need a special repo to follow along, `doc-sync` runs against whatever repo you invoke it
from. But the cleanest way to learn what "stale docs" look like to the fleet is a small repo where
the drift is obvious. So we describe a dummy repo with deliberately-planted drift, and you can
either build it or just read along.

The shape: a ~30-file repo, a real-ish small CLI tool, with documentation that has fallen behind the
code on purpose. Concretely:

```
my-stale-tool/
├── README.md                 # claims the CLI flag is --out; code renamed it to --output
├── AGENTS.md                 # references a `make test` target that no longer exists
├── CONTRIBUTING.md           # setup steps point at Node 16; package.json says >=18
├── docs/
│   ├── usage.md              # example command block: `tool build --out dist`  (broken: --out gone)
│   ├── config.md             # documents 3 config keys; code reads 4
│   └── api.md                # signature for run() is one arg behind the source
├── src/
│   ├── cli.js                # the real flag is --output
│   ├── config.js             # reads 4 keys
│   └── run.js                # run(input, opts), docs still say run(input)
├── package.json              # "engines": { "node": ">=18" }
├── Makefile                  # has `build` and `lint`, no `test`
└── ...                       # ~20 more source + fixture files
```

Every one of those is a drift item: the doc and the code disagree, and the code is the truth. That
is exactly what `doc-sync` exists to find and fix. From its GOAL (verbatim from
`skills/doc-sync/SKILL.md`):

> Make the repository's documentation TRUE to its current code. Find every place docs and code
> disagree and fix the DOCS (never bend the code to match stale docs).

The "never bend the code" half matters. If `doc-sync` finds a doc that reveals an actual code bug
(say, the docs describe the _correct_ behavior and the code is wrong), it does NOT touch the code. It
records the bug as a finding in `DECISIONS.md` and routes it to a different mission (`bug-batch`).
For our example repo there are no code bugs, every disagreement is the docs being behind, so this
run produces only doc PRs.

> Build the example or not, your choice. If you want a real run to follow along with, `git init` a
> throwaway repo with a few of these planted disagreements, install the skills per
> [Installation](02-installation.md), and run the kickoff below. If you would rather just read, the
> rest of this chapter shows you the real artifacts from the autonomous-fleet repo's own dogfood
> run of `doc-sync`, so every path and field below is true of the repo on `main` today.

## The kickoff

You start a mission the same way you saw in the Quickstart: plain English in your agent's chat, or
the slash form. Both of these do the same thing, they activate the `doc-sync` skill and hand it
your repo:

```
/doc-sync update the docs to match the code
```

or, with no slash UI (Grok, Orca), paste the skill name as a natural-language instruction:

```
Run doc-sync: update the docs to match the code
```

or the plainest form, which the umbrella `autonomous-fleet` skill routes to `doc-sync` for you:

```
The docs are out of date, fix them
```

What happens next is fully autonomous. The engine's ORCHESTRATOR DIRECTIVE says to operate without
asking you anything except the single final report and any hard external dependency it cannot
self-grant (an OAuth grant, for example). It will not stop to ask "shall I proceed?" or "should I
merge this?", the answer is always yes, it acts. So once you press enter, the coordinator:

1. Runs SELF-ORIENTATION: resolves the repo root, reads `README.md` + `package.json` to learn the
   stack, derives the maintainer identity from `git config user.name`/`user.email` (that name gets
   stamped on every commit), picks a branch prefix (default `fleet/`, or your `BRANCH_PREFIX` from
   `docs/agents/fleet-config.md` if you ran `/setup-autonomous-fleet`).
2. Confirms the mission fits: greps for the anti-pattern `doc-sync` assumes (docs that disagree with
   code). If the repo had perfectly synced docs, the coordinator would say so and adapt rather than
   invent work.
3. Initializes the ledger and freezes a plan. That plan is the next thing you read.

You do not babysit any of this. But you can, and on your first run you should, read the plan before
the workers do anything irreversible.

## The plan file

The first artifact `doc-sync` writes is its ledger, `docs/doc-sync-progress.md`. This is the file to
open the moment the run starts. It is the coordinator's external brain (the engine calls the ledger
"your EXTERNAL BRAIN"), and it is also your abort handle.

Two things live in this file that you care about as a first-time observer:

The DRIFT INDEX. This is the frozen list of every doc-vs-code disagreement the audit phase
(`T-AUDIT`) found, each tagged `OPEN` or `CLOSED via PR#n`. For our example repo it would read
something like:

```
## DRIFT INDEX
- README --out flag → code uses --output (src/cli.js)            | OPEN
- AGENTS.md `make test` → no test target in Makefile             | OPEN
- CONTRIBUTING Node 16 → package.json engines >=18               | OPEN
- docs/usage.md `tool build --out dist` example broken           | OPEN
- docs/config.md 3 keys → config.js reads 4                      | OPEN
- docs/api.md run(input) → run(input, opts) in src/run.js        | OPEN
```

The task rows. Each doc area becomes one task, with per-task flags the mission defines:
`WRITTEN=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f> MERGED=<t/f>`. A task is only done when its flags read
true _in the file_, not when the agent "believes" it is done. This is the engine's boolean exit
gate, and it is why the ledger is authoritative: the loop reconstructs its state from this file
every turn, never from memory.

Here is what a real `doc-sync` ledger looks like, taken verbatim from this repo's own dogfood run
(`docs/doc-sync-progress.md`), so you can see the real shape rather than a mockup:

```
# doc-sync progress (dogfood of the new disciplines, 2026-06-21)

PHASE: DONE
MISSION: doc-sync   REPO: autonomous-fleet   BASE: ravidsrk/dogfood-doc-sync (off main@1e14409)
COORDINATOR: this Claude Code session

## SELF-ORIENTATION
- REPO_ROOT resolved; product = autonomous-fleet (orchestration framework); MAINTAINER = Ravindra
  Kumar. Test cmd = pytest; lint = validate-all.sh.
- MISSION-FIT: doc-sync premise (docs drifted from code) CONFIRMED by grep ...

## PLAN / DAG VALIDATION GATE (SPOQ, before any worker spawns)
Frozen work units:
- U1 README scripts/ Layout block: add run-sandboxed.sh, coupling-graph.py, render-dashboard.py.
- U2 README capabilities note: research discipline, cost routing, ...
U1 + U2 both touch README.md (one hot file) -> ONE task unit, no inter-task dependencies.
GATE: no cycles (trivial), dependencies resolvable (none), parallelism width = 1. PASS.

## TASK ROW
TASK doc-sync-readme | FILE=README.md | PLACE=container-use(independent) | WORKER=codex | ...
```

Notice the PLAN / DAG VALIDATION GATE block. Before a single worker spawns, the engine runs a cheap
structural check on the frozen task graph: no cycles, every dependency resolvable, and it computes
the parallelism width (how many tasks can run at once). In the dogfood run the width was 1 because
both work units touched the same hot file (`README.md`), so they collapsed into one serialized task.
On the example repo, the six drift areas touch six different files, so the width would be higher and
several PRs could be built in parallel.

When to abort. Read the DRIFT INDEX and the task rows. You should abort if:

- The audit found drift you know is wrong (e.g. it wants to "fix" a doc that is actually correct).
- The plan is going to touch files outside documentation. `doc-sync` is scoped to docs only; a task
  row pointing at `src/cli.js` is a red flag, the engine's FROZEN SCOPE BOUNDARY says reviewers fail
  any PR that adds out-of-boundary work, but you should not wait for the reviewer if you can see it
  in the plan.
- The maintainer identity it derived is wrong (commits would be misattributed).

How to abort. Close the chat. Workers check in with the ledger and exit, and the file ledger
survives, so nothing is half-merged and you can resume in a fresh chat later. There is no "kill"
command to learn, closing the session is the stop.

## The workers spawn

Once the plan is frozen and the DAG gate passes, the coordinator spawns workers. This is the part
that feels different from a normal coding agent: the workers are separate processes in separate
terminals, not threads inside one chat. You see this directly, each worker shows up as its own
terminal pane (Orca), its own agent in the Agent View (Claude Code), or its own subprocess (Codex,
Grok), depending on your runtime.

The role pipeline for `doc-sync` (verbatim from its SKILL.md):

```
@claude  AUDITS (finds drift)  ──►  the frozen DRIFT INDEX
@codex   WRITES the doc fixes   ──►  one branch, one PR per doc area
@claude  (FRESH, build-blind)   ──►  REVIEWS each PR: doc now matches code,
         REVIEWS each PR              examples run, links resolve
@claude  is the INTEGRATOR      ──►  opens the PR, merges (conflict-aware),
                                      cleans the worktree
```

Two things are worth watching for, because they are the framework's whole point:

The reviewer is a different process than the builder, and it never saw the build. The engine hands
the reviewer the diff plus the acceptance contract as text only, never the builder's worktree or
session. This is "build-blindness," and it is structural, not just instructed: the reviewer
literally cannot rationalize the builder's reasoning because it does not have it. When more than one
vendor is available, the reviewer is a _different_ vendor than the builder (a Codex build reviewed by
Claude, in the pipeline above), so a vendor's blind spot is not its own grader.

The reviewer commits its own fix before reading the candidate. Before opening the builder's diff, the
reviewer writes its own independent proposed fix to a file. Only then does it open the candidate and
compare. This anti-anchoring step leaves a real artifact on disk (we read it in
[the run-archive](#the-run-archive) below), and the framework can prove the order it happened in.

What you actually see in the terminal is undramatic: a worker spawns, it reads the repo, it edits a
doc file, it runs the example command in that doc to confirm it works (the mission requires
verifying every example/command actually runs before claiming it correct), it commits in small
increments authored as the maintainer, it pushes, and it reports done. Then a fresh reviewer worker
spawns and grades the PR. You can read each worker's output, but you do not need to, the ledger is
the summary.

> A timeout or an empty result while waiting on a worker is a checkpoint, NOT a failure. The engine
> re-issues the wait across 15 to 60 minutes; heartbeats mean the worker is alive, not done. A task
> only fails if its worker exits/crashes or a 3-failure circuit-breaker trips. So if the run looks
> idle for a minute, it is almost certainly fine, give it time.

## The PRs appear

`doc-sync` opens one PR per doc area, not one giant PR for the whole run. This is deliberate: small
per-area PRs have a much higher merge-success rate than one sweeping docs PR, and they are far easier
for you to review. On the example repo you would see PRs appear in GitHub roughly like:

```
#12  docs: align README --out flag with --output            fleet/...  ✓ reviewed
#13  docs: fix CONTRIBUTING Node version (16 → >=18)         fleet/...  ✓ reviewed
#14  docs: update usage.md example to use --output           fleet/...  ✓ reviewed
#15  docs: document the 4th config key                       fleet/...  ✓ reviewed
#16  docs: fix run() signature in api.md (add opts arg)      fleet/...  ✓ reviewed
#17  docs: remove stale `make test` reference from AGENTS.md fleet/...  ✓ reviewed
```

Each PR body carries what changed, why, and an acceptance checklist, public information only (IDs and
`file:line`, never secrets). And critically, by the time a PR shows up as ready, a different agent
than the one that built it has already signed off on the review. You are the final reviewer; the
first reviewer was a fresh build-blind agent who never saw the builder's session.

> If `gh` is not authenticated on the host, the engine does not stop. It falls back to local
> merge-commits into BASE (commits preserved, branches deleted, conflicts resolved locally) and
> records the fallback in `DECISIONS.md`. So a missing `gh auth` degrades the output from "PRs in
> GitHub" to "merge-commits on your BASE branch," it does not fail the run.

The readiness doc. The final PR of a `doc-sync` run ships `docs/doc-sync-readiness.md`. This is the
human-readable summary of the whole run, and it starts with a `fleet-outcome` YAML block (the
machine-readable status, which we read in detail below). Here is the real one from this repo's
dogfood run:

```yaml
---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: ravidsrk/autonomous-fleet
  base_branch: ravidsrk/docsync-fresh
  prs_merged: 0
  metrics:
    drift_open: 0
    code_bug_findings: 0
  deferred_missions: []
  unverified_assumptions: 0
  sources_logged: 0
  cost_estimate: 0.1
  run:
    duration_min: 6
    note: doc-sync dogfood after the close-gaps merge (20 gaps + new inference-cost mission)
---
```

Below the YAML, prose: what drift was closed, how it was verified, and a "Recommended next missions"
section. In the dogfood run that prose reads, in part: "The close-gaps merge (PR #30) added a mission
and a batch of engine disciplines but left the README behind. Closed that drift." That is the whole
job of a readiness doc, to let a human (or a downstream campaign) understand the run without replaying
it.

## The run-archive

Every run that emits any first-class artifact leaves an audited file trail under
`.fleet/runs/<run_id>/`. The `<run_id>` is deterministic and sortable:

```
YYYYMMDDTHHMMSSZ-<mission>-<short-hash>
```

A UTC timestamp (so runs sort by time), the mission slug (so you can grep), and a 6-char random hex
suffix (so two runs in the same second do not collide). Example:
`20260623T141522Z-adversarial-review-and-fix-3a9c2f`.

To make this concrete, the repo ships a canonical example archive at
`.fleet/runs/example-fixture/` that every validator in `validate-all.sh` runs against in CI. It is
intentionally named `example-fixture` (not the timestamp form) so it is obviously not a real run,
but its internal `run_id` field IS a regex-valid id. We will walk it file by file, because it
contains exactly one of each kind of artifact a run produces.

> The example fixture is an `adversarial-review-and-fix` archive, not a `doc-sync` one, because it is
> built to exercise every verification layer (findings, blind-fixes, the verifier, the stop-verify
> hook). A `doc-sync` run produces the same _kinds_ of file (manifest, trace, fleet-outcome,
> readiness) but not the findings/blind-fix files, those only appear when a mission has a review
> phase that files schema-checked findings. The fixture is the most complete archive, so it is the
> best one to learn the layout from.

Here is every file in `.fleet/runs/example-fixture/`, each with its one-line purpose. This table is
the one in the fixture's own `README.md`, verified against the directory on `main`:

```
FILE                            PURPOSE
─────────────────────────────   ────────────────────────────────────────────────────────────
manifest.json                   The audit trail: every file the run produced, with sha256,
                                mtime, kind, producer, byte size. The provenance index.
p0-review-findings.json         The reviewer's findings (schema-checked). F-001 is a real
                                verified bug; F-002 is a simulated hallucination.
reviewer-blind-fix-F-001.md     The reviewer's independent fix for F-001, written BEFORE it
                                read the candidate patch (anti-anchoring).
reviewer-blind-fix-F-002.md     Same, for F-002.
p0-verify-summary.json          The verifier's output: verified=1, unverified=1, and which
                                finding id was downgraded (F-002).
stop-verify-decisions.log       The stop-verify hook's decision log: one `block`, one `allow`.
p1-fix-attestation.json         The fixer's attestation that F-001's fix landed, with the
                                full blind-fix → fixer-draft → integration sha chain.
fleet-outcome.yaml              The T-FINAL outcome doc: status, metrics, archive_enabled.
trace.jsonl                     The dashboard contract stream: one JSON line per state
                                transition (SPAWN → INSPECT → FREEZE → COMMIT).
README.md                       Human notes on the fixture itself (not part of a normal run).
```

The manifest is the spine. `manifest.json` lists every file with its `path`, `kind` (one of
`findings`, `verify_summary`, `blind_fix`, `prompt`, `response`, `diff`, `readiness`, `progress`,
`other`), `sha256`, `mtime_utc`, `producer` (the worker/reviewer slug that wrote it), and `bytes`.
Without the manifest, the directory is just files with no provenance. With it, every artifact a run
produced can be checksummed and ordered. A real entry from the fixture:

```json
{
  "path": "p0-review-findings.json",
  "kind": "findings",
  "sha256": "91a7ca0885bd414613bbf11c2d02d9eb1bab48e66a0ceefca0d006b3cbbabf06",
  "mtime_utc": "2026-06-23T00:05:00Z",
  "producer": "p0-reviewer-claude",
  "bytes": 2570
}
```

The mtime ordering is not cosmetic, it encodes the disciplines. The validator enforces that certain
kinds appear in a causal order, because the order _is_ the discipline:

```
blind-fix  (00:01:00, 00:01:30)   <   findings  (00:05:00)   <   verify-summary (00:06:00)
   │                                      │                            │
   │ written BEFORE the reviewer          │ filed AFTER the            │ audits the findings,
   │ saw the candidate patch              │ blind-fix                  │ so it must be newer
   │ (anti-anchoring)                      │
```

Concretely: a `blind_fix` must have an mtime _before_ every `findings` file from the same reviewer
(the reviewer must commit its fix before reading the diff); a `verify_summary` must be _after_ the
findings it audits (a summary older than the findings would be a stale audit mis-archived); and the
`readiness` doc must have the _latest_ mtime in the archive (it is the last thing T-FINAL emits). A
manifest whose files violate these orderings FAILS validation even when every checksum matches. The
discipline is not "the files exist," it is "the files exist in the order the discipline demands."

The findings file shows the substrate catching a hallucination. Open `p0-review-findings.json` and
you see two findings. F-001 is real: it cites `scripts/coupling-graph.py:107`, quotes the exact
offending line, and is marked `verified: true`. F-002 is a deliberately planted fake, its
`quoted_line` is not actually in the cited file, and the verifier marks it `verified: false` with the
reason "quoted_line not found in cited file." This is the framework demonstrating its own immune
system on the fixture: a reviewer can hallucinate a finding, and the verifier downgrades it before it
can drive a bogus fix. `p0-verify-summary.json` records the tally: `total_findings: 2`,
`verified_findings: 1`, `unverified_findings: 1`, `unverified_ids: ["F-002"]`.

The blind-fix file is the anti-anchoring artifact. `reviewer-blind-fix-F-001.md` is the reviewer's
own proposed fix, naming the point of creation (`scripts/coupling-graph.py:_iter_imports:107`), the
shape of the change in prose, and a pre-commit confidence score (78/100). It was written before the
reviewer opened the builder's patch, and the manifest's mtime ordering proves it.

The trace stream is the dashboard contract. `trace.jsonl` is one JSON line per state transition,
schema-pinned at `schema_version: "1.0"`. Each line carries the mission, the primitive, the role, the
run_id, a status, and a timestamp. The fixture's four lines are SPAWN_WORKER → INSPECT → FREEZE →
COMMIT:

```json
{"mission": "adversarial-review-and-fix", "primitive": "SPAWN_WORKER", "role": "REVIEWER", "status": "started", ...}
{"mission": "adversarial-review-and-fix", "primitive": "INSPECT", "role": "REVIEWER", "status": "succeeded", ...}
{"mission": "adversarial-review-and-fix", "primitive": "FREEZE", "role": "COORDINATOR", "status": "succeeded", ...}
{"mission": "adversarial-review-and-fix", "primitive": "COMMIT", "role": "FIXER", "status": "succeeded", ...}
```

This stream is the contract a dashboard reads (vibe-kanban, Claude Code's Agent View, or a custom
one); owning the format rather than the renderer is what keeps live observability free of UI debt.
The `details` object on an event is free-form but must never carry secrets or host-absolute paths,
that redaction is enforced by the validator (`emit_trace.validate_event` plus `emit()`), not left to
a prose rule.

> Honest scope note (true of `main` today): the fixture's `trace.jsonl` has four events because a
> fixture can be hand-built to show the full contract. In _production_ runs today, exactly one trace
> event is wired in code: the `T-FINAL` archive transition, emitted by `fleet_run.write_manifest`
> (and emitted BEFORE the manifest write, per the "trace first, ledger second" doctrine). The schema
> covers 11 primitives and the stream is intentionally sparse while per-transition emission rolls
> out across the coordinator and adapters. So on a real run, do not expect a dense trace yet, expect
> the `T-FINAL` event and the rest of the archive. We say more in the [Trace schema](16-trace-schema.md)
> reference. This is the contract being shipped ahead of the full emission, not a broken stream.

Retention. The fleet never garbage-collects run-archives. You decide retention out of band (delete
`.fleet/runs/` directories older than N days if you like); the engine loop never prunes. An old
archive stays auditable for as long as it sits on disk.

## What "done" means

A green test suite is necessary but not sufficient, and the engine is emphatic about this: it will
NOT declare a run done on green checkmarks alone. "Done" is a state recorded in two files, and you
verify it by reading them, not by trusting the agent's last message.

First, the ledger's per-task flags must all read true in the file:
`WRITTEN=t PR_OPEN=t REVIEWED=t MERGED=t` for every task, plus the worktree-clean gate. A merged but
uncleaned task is not terminal.

Second, and this is the field you check, `fleet-outcome.yaml` (embedded at the top of the readiness
doc). For a `doc-sync` run, the fields that mean "done" are:

```
FIELD                       MEANS                                            DONE WHEN
─────────────────────────   ──────────────────────────────────────────────  ─────────────
status                      The overall verdict.                             done
metrics.drift_open          DRIFT-INDEX items still unfixed.                 0
metrics.code_bug_findings   Code bugs found (routed out, not fixed here).    (informational)
unverified_assumptions      External facts the build used without a source.  0
prs_merged                  PRs merged into BASE.                            (run-dependent)
cost_estimate               Rough spend for the run.                         (informational)
```

The two that gate "done" are `status: done` and `metrics.drift_open: 0`. If `drift_open` is nonzero,
the run is not finished, there is still a doc that disagrees with the code. If `status` is anything
other than `done` (for example `blocked` or `partial`), read the prose below the YAML to find out
why. `unverified_assumptions: 0` is the research-discipline gate: it means every external fact the
build leaned on was logged with a source; a reviewer fails any PR that codes against an unverified
external fact.

You can also let a script check the outcome for you instead of reading by eye:

```bash
./scripts/validate-fleet-outcome.sh
```

This is part of `validate-all.sh`, which runs the full validator suite (skills, fleet-outcome,
goal-condition, run-archive, plus pytest). If you want the single source of truth on whether a run's
artifacts are well-formed, that is the command.

> One subtlety worth internalizing now: the ledger is your loop memory, but the external SCM/CI fact
> is ground truth at a terminal edge. Before writing any terminal flag (MERGED / DONE), the engine
> re-verifies the real fact directly (`gh pr view <n> --json state,mergedAt`) and lets it override
> the ledger if they disagree. So if your ledger says MERGED but GitHub says the PR is still open,
> GitHub wins, the run is not done. You inherit the same rule: trust the SCM over the flag at the
> finish line.

So the full "is this run actually done?" check, the one you run the first few times before you trust
it:

1. Open `docs/doc-sync-readiness.md`. Confirm `status: done` and `metrics.drift_open: 0` in the YAML.
2. Skim the prose: did it close the drift you expected, and route (not fix) any code bugs?
3. Open `.fleet/runs/<id>/manifest.json`. Confirm a manifest exists (a run that shipped artifacts but
   no manifest ships as `partial`, not `done`, because it is not auditable).
4. Spot-check the PRs in GitHub: each one small, scoped to docs, authored as you (the maintainer),
   with a different agent's review already on it.

When all four hold, the run is done in the way the framework means it, not "the agent thinks it is
done" but "the files on disk prove it is done."

## Where to go next

You have now watched a mission from kickoff to archive and you can read every file it leaves behind.
The natural next question is the one this chapter deliberately did not answer: _what is the engine
actually doing under the hood, and why is it built this way?_ That is the [Mental model](04-mental-model.md)
chapter, what a "run" really is, why workers are separate processes, why the reviewer is build-blind,
and why it is one PR per unit instead of one giant blob. Read that next.

For the surrounding reference material this chapter touched:

- [Run-archive anatomy](15-run-archive.md), every file kind and the manifest schema field by field.
- [Trace schema (v1)](16-trace-schema.md), the full dashboard contract and what is emitted today.
- [fleet-outcome schema](17-fleet-outcome-schema.md), every outcome field and what downstream
  campaigns check.
- [Troubleshooting](14-troubleshooting.md), when a run does not reach `done`.

---

← [Previous: Installation](02-installation.md) ·
[Guide Index](README.md) ·
[Next: Mental model](04-mental-model.md) →
