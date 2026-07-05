<!-- title: Missions vs campaigns | description: When to run one mission and when to chain several into a conditional campaign DAG | sidebar_order: 5 -->

# Missions vs campaigns

**On this page:** [A mission is one job](#a-mission-is-one-job) ·
[A campaign is a DAG of missions](#a-campaign-is-a-dag-of-missions) ·
[The three shipped campaigns](#the-three-shipped-campaigns) ·
[Chain, sequence, or neither](#chain-sequence-or-neither) ·
[One mission per repo at a time](#one-mission-per-repo-at-a-time) ·
[Where conditional gates live](#where-conditional-gates-live)

You finished a run. It opened a few PRs, wrote a readiness doc, told you it was done. Now you have
a choice that the framework cares a lot about: do you run another mission, or do you stop?

This chapter draws the line between a mission (the unit of work) and a campaign (a chain of
missions with verification gates between them). It tells you which one to reach for, names the
three campaigns that ship in the box, and shows you exactly where the "go to the next node" decision
gets made. It does not teach you how to author your own campaign YAML from scratch. That is
[Campaigns](10-campaigns.md). Here we stay at the level of "what are these two things, and when do I
use each."

> If you have not read [Mental model](04-mental-model.md) yet, read it first. This chapter assumes
> you already know that a run is a frozen plan plus a worker fleet plus a file ledger, and that the
> readiness doc is the authoritative "done" record. Everything below builds on those three ideas.

## A mission is one job

A mission is one discrete engineering job, run to completion. `doc-sync` is a mission. So is
`test-coverage`. So is `adversarial-review-and-fix`. Each one has a single, bounded objective:

```
doc-sync                     make the docs match the code
test-coverage                raise coverage on a module to its gap-free state
adversarial-review-and-fix   red-team the code, then patch what you found
```

A mission owns one integration branch (its BASE), one ledger directory, and one readiness doc. It
spawns its own worker fleet, opens its own PRs, and writes a machine-readable result block when it
finishes. When the mission says DONE, it means: the ledger's task flags are all true, the readiness
doc exists, every PR is merged into BASE, and `validate-fleet-outcome.sh` passes against the
readiness doc.

The three missions above are the ones that actually live under `skills/<name>/` on `main` today:

```
skills/doc-sync/
skills/test-coverage/
skills/adversarial-review-and-fix/
```

Beyond those shipped three, twelve active exploratory mission docs live under
`docs/exploratory/missions/`: seven from the 2026-06-23 demotion (`dependency-update`, `cleanup`,
`bug-batch`, `targeted-migration`, `design-integration`, `take-product-to-completion`,
`inference-cost`), two active gstack-derived designs (`browser-qa-fix`, `incident-investigate`), and
three earlier demotions (`agents-layer`, `contract-first-build`, `scaffold-align`). They are not
shipped: you cannot invoke them as a mission until they are promoted. Parked designs live under
`docs/exploratory/missions/archive/`. The [Mission catalog](09-mission-catalog.md) covers the
shipped three in depth and explains what each active exploratory one would do if promoted.

The defining feature of a mission, the thing that makes the next section possible, is what it leaves
behind. Every mission's T-FINAL readiness doc begins with a `fleet-outcome` YAML block. That block is
the validated handoff. It is the only thing a campaign reads to decide what to do next.

```yaml
---
fleet-outcome:
  mission: doc-sync
  status: done # done | partial | blocked
  repo: /Users/me/my-app
  base_branch: fleet/repo-health-base
  prs_merged: 4
  metrics:
    drift_open: 0
    code_bug_findings: 2
  deferred_missions:
    - id: bug-batch
      reason: "found 2 real code bugs while syncing docs; out of doc-sync scope"
      blocker: null
---
```

Hold onto `status`, `metrics`, and `deferred_missions`. Those three fields are what campaign edges
branch on. The full field reference is [fleet-outcome schema](17-fleet-outcome-schema.md); here you
just need to know the block exists and is the contract.

## A campaign is a DAG of missions

A campaign is a directed graph of missions, with a hard verification gate between every node. The
gate is not "the agent felt good about it." The gate is: the previous node wrote a valid
`fleet-outcome` block, `validate-fleet-outcome.sh` passed against it, and an `if` expression read off
that block selected the next edge.

The orchestrator is the `fleet-program` skill. It is the engine, one level up. Same discipline as a
single run: a file ledger (`docs/fleet-program-progress.md`), frozen outcomes, no-stop autonomy, and
the iron rule of one active mission per repo at a time. Where a single mission coordinates workers,
the program coordinates missions.

Here is the shape of a campaign, with the gate drawn between nodes:

```
   START
     │
     ▼
 ┌─────────┐   node DONE  ┌──────────────────┐  edge `if`  ┌─────────┐
 │ mission │ ──────────▶  │ validate          │ ─────────▶ │ mission │ ──▶ ...
 │  (node) │              │ fleet-outcome.sh  │            │  (node) │
 └─────────┘              │ + read status     │            └─────────┘
                          │ + eval `if` edge  │
                          └──────────────────┘
                                   │
                                   │ status: blocked
                                   ▼
                              HALT (human gate)
```

Three things to read off that diagram:

1. A node is a mission. The campaign never runs two nodes at once on the same repo.
2. The gate between nodes is mechanical. It reads the `fleet-outcome` block and evaluates the edge
   expression. There is no "ask the human, continue?" step in the happy path.
3. A node that finishes `status: blocked` halts the whole campaign. Blocked is a valid outcome that
   passes validation; it is a deliberate human gate, not a crash and not a completed campaign.

A campaign spec is YAML. The minimum is a `start` node, a `nodes` map (node id to mission), and an
`edges` map (node id to a list of `{ to, if }` edges):

```yaml
campaign: repo-health
repo: single # one REPO_ROOT for every node
base: fleet/repo-health-base # the integration branch the first node forks from
start: docs
nodes:
  docs: { mission: doc-sync }
  tests: { mission: test-coverage }
edges:
  docs: [{ to: tests, if: always }]
  tests: []
```

Linear chains are just campaigns where every edge is `if: always`. There is no separate "linear"
file format you have to learn; a straight line is the degenerate DAG. The branching only shows up
when you write an edge whose `if` is a real condition. More on that in
[Where conditional gates live](#where-conditional-gates-live).

## The three shipped campaigns

Three campaign presets live under `scripts/campaigns/` and solve three distinct problems. Each is a
real YAML file you can read; each is invocable by name with `--preset`. Here is what each one is for
and exactly what is in it on `main` today.

```
            ┌──────────────────────────────────────────────────────────────┐
            │  preset           problem it solves                           │
            ├──────────────────────────────────────────────────────────────┤
            │  repo-health      first-pass health on a repo you just got    │
            │  ship-with-proof  harden a branch, then prove it before merge │
            │  quality-gate     "is this production-ready?" acceptance check │
            └──────────────────────────────────────────────────────────────┘
```

### repo-health

The default for a repo you have not run the fleet on before. It syncs docs first, then raises test
coverage. Two nodes, both `if: always`, a straight line:

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

> The on-disk `repo-health.yaml` has a third node, `tidy` (the `cleanup` mission), commented out. It
> stays commented until `cleanup` earns a promotion (a progress doc, a readiness doc, and an external
> archive). Restore the `tidy` node and its edges when that happens. The active campaign is two nodes
> today: docs then tests.

Use it when: you inherited a repo, or you want a recurring health pass, and you do not have a
specific target in mind. Docs-then-tests is the safe, low-blast-radius opening move.

### ship-with-proof

For "ship this branch safely," "harden then open the PR," "prove it before merge." It audits first
(red-team plus fix), then raises coverage, then syncs docs. Three nodes, all `if: always`, plus two
community post-gates that run after the last node:

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

The order is deliberate: find and fix the bugs before you write tests around the new behavior, and
sync the docs last so they describe the patched, tested code, not the code you started with.

> `post_gates` (and `pre_gates`) are community skills, not fleet mission nodes. The mechanical
> driver, `scripts/run-campaign.sh`, runs mission nodes only. A coordinator runs the gates by hand
> after the campaign reaches DONE. So `ship` and `qa` here are documentation of the intended
> hand-off, not steps the headless driver executes for you.

### quality-gate

For "is this production-ready?", "quality gate before release," "acceptance check." It is a lighter
ship-with-proof: audit then tests, no doc-sync node, with `qa-only` and `health` as post-gates:

```yaml
campaign: quality-gate
repo: single
base: fleet/quality-gate-base
start: audit
nodes:
  audit: { mission: adversarial-review-and-fix }
  tests: { mission: test-coverage }
post_gates:
  - qa-only
  - health
edges:
  audit: [{ to: tests, if: always }]
  tests: []
```

Use it when you are checking readiness rather than producing docs. It answers a question (are we
clean and covered?) instead of changing the documentation surface.

Here is the trio side by side so the differences are obvious:

```
preset           start    nodes                                 post_gates
---------------  -------  ------------------------------------  ----------------
repo-health      docs     doc-sync, test-coverage               (none)
ship-with-proof  audit    adversarial..., test-coverage,        ship, qa
                          doc-sync
quality-gate     audit    adversarial..., test-coverage         qa-only, health
```

You invoke a preset by name. The mechanical, headless driver is:

```bash
./scripts/run-campaign.sh grok --preset repo-health
./scripts/run-campaign.sh claude --preset ship-with-proof --max-turns 60
./scripts/run-campaign.sh grok --preset quality-gate --repo /tmp/my-app
```

Add `--dry-run` to print the plan (which node runs, which readiness doc is expected, which node comes
next) without invoking any agent. That is the cheapest way to see a campaign's shape before you spend
a single turn:

```bash
./scripts/run-campaign.sh grok --preset repo-health --dry-run
```

> Headless campaign mode (`run-campaign.sh`) drives each runtime's CLI in headless mode and is not
> yet fully validated end-to-end. The supported path today is the interactive one: invoke the
> `fleet-program` skill in chat and let it bind to the runtime's `/goal` loop. Treat `run-campaign.sh`
> as the mechanical reference driver, including `--dry-run` for planning, and reach for the
> interactive flow when you actually want a campaign to run. The headless caveat is covered in full in
> [Safety and secrets](12-safety-and-secrets.md).

## Chain, sequence, or neither

Three missions in front of you. Do you chain them into a campaign, run them one after another by
hand, or run one and stop? Decide by what the next step depends on.

```
                Does the next mission's PLAN depend on the
                previous mission's OUTCOME (status / metrics)?
                                    │
              ┌─────────────────────┴─────────────────────┐
             yes                                          no
              │                                            │
   Do you want the decision                   Is there even a next
   made mechanically, gated                   mission you want to run?
   on fleet-outcome?                                       │
              │                              ┌─────────────┴──────────┐
      ┌───────┴────────┐                    yes                       no
     yes               no                    │                         │
      │                 │            Run them as a linear        Run ONE mission,
  CAMPAIGN          Run each          chain (campaign with        read its readiness,
  (conditional      mission by        all `if: always` edges)     STOP. Re-evaluate
   DAG, gated)      hand, eyeball     OR by hand, your call        with fresh context.
                    each readiness
                    before the next
```

Concrete calls:

- Chain into a campaign when one mission's result should pick the next mission. "Audit, and if the
  audit defers dependency work, run dependency-update; otherwise go to tests." That branch is a
  campaign edge. Encoding it as a campaign means the decision is reproducible and gated on the
  `fleet-outcome` block, not on a human re-reading a readiness doc and guessing.
- Run sequentially by hand when the order is fixed but you want to inspect each readiness doc before
  committing to the next. This is the right move when you are still building trust in the fleet on a
  repo you care about. You get the same docs-then-tests effect as `repo-health`, but you are the gate.
- Run one and stop when there is no dependent next step, or when the first mission's result might
  change your mind about what to do next. A single `doc-sync` after a refactor is a complete unit. Do
  not invent a campaign just because campaigns exist.

A campaign earns its complexity when there is a real branch (an `if` that is not `always`) or when
you want the chain to run unattended. A straight line of "always" edges you babysit by hand is not
buying you much over just running the missions yourself.

## One mission per repo at a time

This is the hard rule, and it is not a style preference. Two missions on the same repo at the same
time is forbidden:

```
Same repo, two missions     ──▶  FORBIDDEN (no shared lock manager)
Tasks inside one mission    ──▶  OK (the mission's hot-file + placement rules)
Different repos             ──▶  OK (separate sessions, one ledger each)
```

The reason is mechanical, not philosophical. There is no cross-mission file-lock manager. Two
missions would share one repo's working tree, one BASE branch concept, and two ledgers that know
nothing about each other. They would race on the same files, fork conflicting integration branches,
and corrupt each other's "done" conditions. So the framework simply does not allow it. The program
coordinator runs each node to completion (DONE plus a readiness doc) before it even looks at the next
node.

If you genuinely need parallelism, parallelize across repos, not within one:

- Same mission, several repos: run separate coordinator sessions, one program ledger per repo, and
  aggregate the final reports at the end. There is no shared BASE across repos. This is the
  `parallel_repos` shape; it is separate sessions, not concurrent missions on one tree.
- Inside a single mission, the workers do run in parallel. That is the mission's own concern, governed
  by its hot-file rule and worker placement (see [The engine](06-the-engine.md)). The one-mission rule
  is about missions, not about the workers inside one.

This rule is why a campaign is a chain and never a fan-out on a single repo. The DAG can branch (pick
one of several next nodes), but it never runs two nodes simultaneously against the same working tree.

## Where conditional gates live

When a node finishes, the program coordinator does not guess what comes next. It reads the previous
node's `fleet-outcome` block and evaluates the outgoing edges in order. The first edge whose `if`
expression is true wins. If none match, the campaign is DONE (or BLOCKED, if the node's status was
`blocked`).

The inputs to an edge expression come entirely from the previous node's `fleet-outcome`:

```
fleet-outcome block (from the readiness doc)
        │
        ├── status                (done | partial | blocked)   ──┐
        ├── metrics.<key>         (p0_open, drift_open, ...)     ├──▶ edge `if` expression
        └── deferred_missions[]   (ids deferred this run)       ──┘
```

The expression grammar the evaluator actually supports (in `scripts/lib/fleet_outcome.py`):

```
always                               always true; the unconditional edge
p0_open == 0                         equality on a metric or top-level field
p0_open != 0                         inequality
p0_open > 0                          ordering: > < >= <= (numeric coercion)
code_bug_findings > 0                same, any metric key the mission emits
status == blocked                    top-level status field
deferred_missions contains bug-batch true if any deferral id matches
```

Two behaviors worth knowing, both deliberate:

- Edges are evaluated in declared order, first match wins. Put your specific conditions before your
  `if: always` fallback, or the fallback shadows them.
- An edge whose expression references a metric the previous mission never emitted (or is otherwise
  malformed) is not a crash. It is skipped, and evaluation falls through to the next edge. The rule is
  "unknown or unsupported expression, skip the edge, do not guess." A campaign-author typo does not
  silently match the wrong branch; it just does not take that edge.

Worked example. Imagine an audit-first campaign where you only want to run dependency work if the
audit actually deferred it:

```yaml
edges:
  audit:
    - { to: deps, if: deferred_missions contains dependency-update }
    - { to: tests, if: always }
  deps:
    - { to: tests, if: always }
  tests: []
```

After the `audit` node finishes, the coordinator reads its `fleet-outcome`. If `deferred_missions`
contains an entry with `id: dependency-update`, the first edge matches and the campaign routes to
`deps`. If not, the first edge is false, and the `if: always` fallback routes to `tests`. The
decision is mechanical and reproducible: same `fleet-outcome` in, same next node out, every time.

This is the whole reason a mission's readiness doc must start with a valid `fleet-outcome` block. The
block is the gate's only input. A node that finishes without one strands the campaign: the
coordinator has nothing to branch on, logs the gap, and cannot pick a next node. The three branchable
surfaces (`status`, `metrics.*`, `deferred_missions`) are exactly the fields documented in
[fleet-outcome schema](17-fleet-outcome-schema.md). Read that chapter when you are ready to write an
edge against a specific metric.

> Do not branch on `run` telemetry fields (`duration_min`, `coordinator_turns`, `worker_retries`).
> Those are recorded for dogfood comparisons, not for routing. The branchable fields are `status`,
> anything under `metrics`, `deferred_missions`, and a handful of explicitly branchable discipline
> assertions (`unverified_assumptions`, `cost_estimate`, `root_cause_audited`, `archive_enabled`).
> The schema chapter marks which is which.
## Real-world use cases

### Example — repo-health preset (2 nodes)

External pack `repo-health-campaign.yaml`: doc-sync then test-coverage. Shipped preset dry-run:

```bash
./scripts/run-campaign.sh grok --preset repo-health --dry-run
```

### Invocation — ship-with-proof (3 nodes)

`ship-with-proof-campaign.yaml`: audit → test-coverage → doc-sync. Evidence pack closed REL-001..003
on gemoji with 26 runs, 57 assertions.

### Real run on quality-gate preset

`validate-headless.sh` exercises `quality-gate` alongside `repo-health` and `ship-with-proof` —
all three presets must dry-run exit 0 before merge.

---

That is the whole distinction. A mission is one job that leaves behind a validated `fleet-outcome`
block. A campaign is a DAG of those jobs, gated mechanically on that block, one mission at a time per
repo. The three shipped presets (`repo-health`, `ship-with-proof`, `quality-gate`) cover the common
shapes; the next two how-to chapters get specific. [Mission catalog](09-mission-catalog.md) details
every shipped mission. [Campaigns](10-campaigns.md) teaches you to author your own campaign YAML,
gates and conditional branches included.

← [Mental model](04-mental-model.md) · [Guide Index](README.md) · [The engine](06-the-engine.md) →
