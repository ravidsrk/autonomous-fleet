<!-- title: Campaigns | description: Chain autonomous-fleet missions behind verification gates: the three shipped presets, writing a custom campaign YAML, dry-run planning, and the headless-mode caveat. | sidebar_order: 10 -->

# Campaigns

A mission is one engineering job. A campaign is a sequence of missions wired together with
verification gates between them, so the next mission only runs once the previous one landed
clean. You point a campaign at one repo, it runs each node in turn, validates the outcome, and
decides where to go next by reading the `fleet-outcome` block the finished mission wrote.

If you have read [Missions vs campaigns](05-missions-vs-campaigns.md) you already know the shape.
This chapter is the operator's reference: the three presets that ship today, every flag on
`run-campaign.sh`, how to write your own campaign YAML, how the `if` gates evaluate, what
`--dry-run` shows you, and the honest state of headless mode. Pick the right mission first from
the [Mission catalog](09-mission-catalog.md); a campaign is only as good as the nodes inside it.

> One rule before anything else: a campaign runs one mission at a time on one repo. It is not a
> way to run missions in parallel. The gates between nodes are the whole point. If you want
> several repos worked at once, run separate coordinator sessions, one per repo.

**On this page:** [The three shipped presets](#the-three-shipped-presets) ·
[Anatomy of a campaign run](#anatomy-of-a-campaign-run) ·
[Custom campaign YAML](#custom-campaign-yaml) ·
[How gates evaluate](#how-gates-evaluate) ·
[Dry-run mode](#dry-run-mode) ·
[Headless mode and its caveat](#headless-mode-and-its-caveat) ·
[Reading the composition-e2e audit](#reading-the-composition-e2e-audit) ·
[The archived presets](#the-archived-presets)

---

## The three shipped presets

Three presets are active today. Each lives as a YAML file under `scripts/campaigns/` and references
only missions that have shipped (`doc-sync`, `test-coverage`, `adversarial-review-and-fix`). You run
one with `--preset <name>`:

```bash
./scripts/run-campaign.sh claude --preset repo-health      # doc-sync -> test-coverage
./scripts/run-campaign.sh claude --preset ship-with-proof  # review-fix -> test-coverage -> doc-sync
./scripts/run-campaign.sh claude --preset quality-gate     # review-fix -> test-coverage
```

The first argument is the runtime: `grok`, `claude`, or `codex`. Those three are the only values
the driver accepts; anything else exits with an error. The presets themselves are runtime-agnostic,
so the same preset runs under any of the three.

### repo-health

The recurring hygiene pass. Sync the docs to the code, then raise test coverage on whatever the
docs touched. Both edges are unconditional, so it is a plain two-node line.

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

```
  docs (doc-sync) ──always──> tests (test-coverage) ──> DONE
```

The `tidy` node (mission `cleanup`) is commented out in the file. `cleanup` is an exploratory
mission and is not active until it earns the three-artifact promotion gate, so the preset ships as a
two-node line. The commented block in `scripts/campaigns/repo-health.yaml` is the restore template
for when `cleanup` is promoted: it shows the `tidy` node and the `tests -> tidy` edge to add back.

> Use repo-health for the weekly or per-merge hygiene loop: a repo that drifted after a refactor,
> docs that no longer match the code, a module whose coverage slipped. It does not red-team your
> code and it does not ship anything. For that, use one of the other two.

### ship-with-proof

The harden-then-ship line. Red-team the surface and patch what it finds, raise coverage, then sync
the docs. Three nodes, all unconditional edges.

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

```
  audit (review-fix) ──always──> tests (coverage) ──always──> docs (doc-sync) ──> DONE
                                                                   │
                                                            post_gates: ship, qa
                                                            (run by hand, after DONE)
```

The `post_gates` list names two community skills, `ship` and `qa`. Read the next section carefully:
`post_gates` is documentation, not something the driver runs. The mechanical campaign driver
(`scripts/run-campaign.sh`) runs mission nodes only. The coordinator runs the gates by hand after
the campaign reaches DONE.

> Use ship-with-proof when the ask is "ship this branch safely", "harden it then open a PR", or
> "prove it before merge". It is the heaviest of the three because it leads with an adversarial
> audit and finishes with a docs pass, then hands off to `ship` / `qa`.

### quality-gate

A lighter acceptance check: audit, then coverage. No doc-sync node. Use it as a release gate
rather than a full hardening pass.

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

```
  audit (review-fix) ──always──> tests (test-coverage) ──> DONE
                                       │
                                post_gates: qa-only, health
```

> Use quality-gate when the ask is "is this production-ready?", "quality gate before release", or
> "acceptance check". It is ship-with-proof minus the docs node, with read-only post-gates
> (`qa-only`, `health`) instead of the write-capable `ship`.

### The three at a glance

```
preset           nodes (in order)                            edges        post_gates
---------------  ------------------------------------------  -----------  -------------
repo-health      doc-sync, test-coverage                     all always   none
ship-with-proof  review-fix, test-coverage, doc-sync         all always   ship, qa
quality-gate     review-fix, test-coverage                   all always   qa-only, health
```

All three presets today use only `if: always` edges, so none of them branches. The conditional
machinery is real and tested (see [How gates evaluate](#how-gates-evaluate)), but the shipped
presets are linear lines. The conditional examples in this chapter come from custom campaigns and
the fleet-program reference, not from a shipped preset.

---

## Anatomy of a campaign run

Before you write your own campaign, it helps to know what the driver actually does per node. The
loop in `scripts/run-campaign.sh` is mechanical and worth understanding, because every gate you
write plugs into it.

```
  ┌─ load campaign YAML, read `start` ──────────────────────────────┐
  │                                                                  │
  │  for each node, until no next node:                              │
  │    1. look up the node's mission                                 │
  │    2. validate the mission is in the registry                    │
  │    3. run it (or, with --dry-run, just print the plan)           │
  │    4. validate the readiness doc's fleet-outcome block           │
  │    5. if outcome status == blocked  ->  HALT (exit 2)            │
  │    6. else evaluate edges, pick the first matching `to`          │
  │    7. that node becomes current; loop                            │
  │                                                                  │
  └─ no next node  ->  "Campaign complete"                           │
```

Two safety rails sit on top of that loop:

- A per-node revisit budget. A node may be entered at most three times. Campaigns with deliberate
  back-edges (a `deps -> audit` re-audit loop, say) are allowed to revisit a node a few times to
  converge, but a fourth entry to the same node aborts with a non-converging-loop error.
- A global step cap. After 20 steps the run aborts with a step-limit error, so a misconfigured
  cycle can never run forever even if no single node trips the per-node budget.

When a node finishes, the driver validates that node's readiness doc with
`./scripts/validate-fleet-outcome.sh`, then reads the `status` field out of the `fleet-outcome`
block. A `status: blocked` is a valid outcome that passes validation, and it is a hard stop: the
campaign halts with exit code 2 and a message saying this is a human gate, not a completed
campaign. It does not fall through to "Campaign complete". `status: done` and `status: partial`
fall through to edge evaluation; `blocked` never does.

The full `fleet-outcome` schema (every field, every status, what each metric means) is its own
reference: [fleet-outcome schema](17-fleet-outcome-schema.md). The campaign driver reads four
things from it: `status` (for the blocked halt) and whatever metrics your edge expressions name.

---

## Custom campaign YAML

You are not limited to the three presets. Write your own campaign YAML and pass it with
`--campaign PATH` instead of `--preset NAME`:

```bash
./scripts/run-campaign.sh claude --campaign docs/composition-e2e-campaign.yaml
./scripts/run-campaign.sh grok   --campaign /tmp/my-campaign.yaml --repo /tmp/target-repo
```

> Adding a new file to `scripts/campaigns/` so it ships as a `--preset` is a contributor task, not
> a user one. It lives in CONTRIBUTING.md, because a shipped preset has to reference only shipped
> missions and pass the repo's edge linter. A custom `--campaign` file is yours to point at from
> anywhere on disk; it has the same schema but no promotion bar.

### The schema, annotated

Here is a complete, copy-pasteable custom campaign that exercises every field the driver reads. This
is the `composition-e2e` campaign that ships under `docs/composition-e2e-campaign.yaml`, annotated:

```yaml
campaign: composition-e2e # id; used for the default base-branch name and the ledger
repo: single # one REPO_ROOT for every node. `multi` is cross-repo (see below)
base: fleet/composition-e2e-base # base branch the run cuts work branches from; optional
start: docs # the first node id to enter

nodes: # every node maps an id to exactly one mission skill
  docs: { mission: doc-sync }
  bugs: { mission: bug-batch }
  tests: { mission: test-coverage }

edges: # per node, an ordered list of {to, if} edges
  docs:
    - { to: bugs, if: code_bug_findings > 0 } # conditional: only if doc-sync found code bugs
    - { to: tests, if: always } # fallback: otherwise straight to tests
  bugs:
    - { to: tests, if: always }
  tests: [] # empty list = terminal node; campaign reaches DONE here
```

```
  docs (doc-sync)
    ├─ code_bug_findings > 0 ──> bugs (bug-batch) ──always──> tests (test-coverage) ──> DONE
    └─ always ──────────────────────────────────> tests (test-coverage) ──> DONE
```

Field by field, what the driver requires and what it does with each:

```
field             required  meaning
----------------  --------  --------------------------------------------------------------
campaign          no*       campaign id; cosmetic to the driver, used for ledger + base name
repo              no        `single` (one repo for all nodes) or `multi` (cross-repo)
base              no        base branch missions cut work branches from; defaults per id
start             YES       the node id the driver enters first; missing `start` is an error
nodes             YES       map of node-id -> { mission: <skill> }; each node needs a mission
edges             no        map of node-id -> ordered list of { to, if }; missing = terminal
post_gates        no        documentation only; the driver does NOT run these (see below)
pre_gates         no        documentation only; the driver does NOT run these (see below)
```

The driver's pre-flight only enforces two things in YAML: the top-level mapping must contain
`start`, and every node under `nodes` must be a mapping with a `mission` key. A node missing its
`mission`, or a non-mapping campaign, is rejected before any mission runs. Beyond that, the mission
named in each node must exist in the mission registry, or the run aborts at that node with an
"unknown mission" error. So a typo in a mission name fails fast, at the node, not silently.

> `*` The `campaign:` key is not validated by the driver's YAML pre-flight, but every shipped file
> includes it and the fleet-program ledger reads it. Include it. The same goes for `repo` and
> `base`: harmless to omit from the driver's view, load-bearing for the ledger and for how branches
> are named. Match the shipped presets and set all three.

### pre_gates and post_gates are documentation

Both ship-with-proof and quality-gate carry a `post_gates` list. Do not expect the campaign driver
to run them. The mechanical driver runs mission nodes only. `pre_gates` and `post_gates` name
community skills (`ship`, `qa`, `qa-only`, `health`, `grill-with-docs`, `office-hours`) that a
coordinator runs by hand, before the first node or after the campaign reaches DONE. They are in the
YAML so the intended gates are recorded next to the campaign, not so the driver executes them. The
fleet-program reference spells out which gate runs where for each preset.

### Cross-repo is separate sessions, not parallel nodes

`repo: single` is the norm and what every shipped preset uses. There is a `multi` / `parallel_repos`
shape for running the same campaign against several different repositories, but it is not concurrent
missions on one repo. It means separate coordinator sessions, one program ledger per repo, no shared
base branch across them. The "one mission at a time per repo" rule is never relaxed.

---

## How gates evaluate

The `if` on each edge is a small expression evaluated against the finished node's `fleet-outcome`
block. The rules are deliberately narrow so a campaign never guesses.

Edge selection, per node:

1. Edges are evaluated in the order written.
2. The first edge whose `if` is true wins; its `to` becomes the next node.
3. If no edge matches (or the node has an empty edge list), the campaign reaches DONE at that node.
4. An edge whose expression references a metric that is not in the outcome, or is otherwise
   malformed, is skipped (treated as not-taken) rather than crashing the pick. A valid `if: always`
   fallback after it still fires. This is the do-not-guess contract: an unparseable edge is skipped,
   never assumed true.

So always put your unconditional `if: always` fallback last in the list, after the conditional
edges. The conditionals get first refusal; the fallback catches everything else.

### The three expression forms

The edge evaluator supports exactly three shapes. Anything else raises and the edge is skipped.

```
form                                   example                         meaning
-------------------------------------  ------------------------------  ----------------------------
always                                 if: always                      unconditional; always true
<metric> <op> <value>                  if: code_bug_findings > 0       compare a metric to a literal
deferred_missions contains <id>        if: deferred_missions contains cleanup   membership check
```

The comparison operators are `==`, `!=`, `>`, `<`, `>=`, `<=`. The left side is a metric name; it is
looked up first in the outcome's `metrics` map, then at the top level of the outcome. The right side
is a single literal token: an integer, a float, `true`/`false`, or a bare/quoted string. Booleans
compare as themselves for `==` / `!=` and coerce to 0/1 for the ordering operators.

One sharp edge worth knowing: the right operand is a single token anchored to the end of the
expression. A trailing word (a typo like `if: status == blocked now`) does not match the grammar, so
the edge is treated as unparseable and skipped, not silently compared against a multi-word string.
Keep expressions to one metric, one operator, one token.

### Which metrics you can name

The metric in an edge has to be one the finishing mission actually emits, or the lookup returns
nothing and the edge is skipped. Each mission emits a fixed metric set:

```
mission                       metrics available to an edge after that node
----------------------------  ----------------------------------------------------------
doc-sync                      drift_open, code_bug_findings
test-coverage                 gaps_open, coverage_regressed
adversarial-review-and-fix    p0_open, p1_open, findings_open, ops_queue_count
bug-batch                     bugs_open, bugs_skipped
```

So a `docs -> bugs` edge can branch on `code_bug_findings > 0` (doc-sync emits it), and an audit
node can branch on `findings_open == 0` or `ops_queue_count > 0` (adversarial-review-and-fix emits
those). An audit node cannot branch on `gaps_open`, because that metric belongs to test-coverage and
will not be present in the audit's outcome. The full metric vocabulary, including the exploratory
missions, lives in the [fleet-outcome schema](17-fleet-outcome-schema.md).

### A conditional example, end to end

The fleet-program reference documents an audit-gated `secure-ship` pattern that is a good model for a
custom campaign even though its current preset is archived (see below). The audit node gates the
whole campaign on a clean result, and a deferred major triggers a bounded re-audit:

```yaml
campaign: my-secure-ship
repo: single
start: audit
nodes:
  audit: { mission: adversarial-review-and-fix }
  deps: { mission: dependency-update }
  docs: { mission: doc-sync }
edges:
  audit:
    - { to: deps, if: findings_open == 0 } # clean audit -> proceed; non-clean blocks the run
  deps:
    - { to: audit, if: majors_deferred > 0 } # a deferred major -> re-audit the residual risk
    - { to: docs, if: always } # otherwise finish with docs
  docs: []
```

Two things make this work. First, the `audit` node has no `if: always` fallback, so an audit that
cannot close its findings (and writes `status: blocked`) does not flow anywhere; the driver's
blocked-halt stops the campaign before edge evaluation even runs. Second, the `deps -> audit`
back-edge revisits `audit` only when a major version bump was deferred, and the per-node revisit
budget of three keeps that loop bounded. This pattern depends on the `dependency-update` mission,
which is exploratory today, so you would run it as a `--campaign` file, not a `--preset`.

---

## Dry-run mode

Add `--dry-run` to print the plan without invoking any agent. It walks the campaign exactly the way
a real run would, but instead of running a mission it prints what it would run and the readiness doc
it would expect, then computes the next node assuming a benign success.

```bash
./scripts/run-campaign.sh grok --preset repo-health --dry-run
```

A dry run of repo-health prints something like:

```
== run-campaign ==
runtime:  grok
repo:     /path/to/autonomous-fleet
campaign: /path/to/autonomous-fleet/scripts/campaigns/repo-health.yaml
start:    docs
dry-run:  1

--- step 1: node=docs mission=doc-sync ---
  would run: run-mission-headless.sh grok doc-sync --repo /path/to/autonomous-fleet --max-turns 50
  expect:    /path/to/autonomous-fleet/docs/doc-sync-readiness.md with fleet-outcome.status done
  next:     tests

--- step 2: node=tests mission=test-coverage ---
  would run: run-mission-headless.sh grok test-coverage --repo /path/to/autonomous-fleet --max-turns 50
  expect:    .../docs/test-coverage-readiness.md with fleet-outcome.status done
  next:     <campaign done>

Campaign dry-run complete. Nodes visited: docs tests
```

How to read it: each step shows the node, the mission, the exact headless command it would invoke,
and the readiness doc it expects that mission to produce. The `next:` line is the node the driver
would pick. In a dry run the next-node computation assumes every mission succeeds with benign
metrics (every known metric set to 0), so conditional edges that need a non-zero metric will not
fire in dry-run. A `> 0` branch always shows the fallback path in a dry run. That is expected: the
dry run shows the success path through the DAG, not every branch. Use it to confirm the node order,
the mission per node, the expected readiness paths, and that the campaign terminates rather than
loops.

---

## Headless mode and its caveat

Everything above runs the campaign headless: `run-campaign.sh` drives each runtime's CLI
non-interactively, node by node, with no human in the loop. That is the mode the script exists for,
and the flags it exposes are the full set:

```
run-campaign.sh <grok|claude|codex> (--preset NAME | --campaign PATH) [options]

  --preset NAME                       built-in campaign at scripts/campaigns/<NAME>.yaml
  --campaign PATH                     a campaign YAML file anywhere on disk
  --repo PATH                         target git repo for the missions (default: this clone)
  --dry-run                           print the plan only; invoke no agents
  --max-turns N                       per-node turn budget (default 50; Grok/Codex only)
  --yolo                              auto-approve agent tool calls (Grok only; default off)
  --no-yolo                           deprecated alias for the default (no auto-approve)
  --yolo-untrusted-acknowledged       required with --yolo when --repo is outside this clone
```

A few specifics from the script:

- The runtime argument is positional and first. It must be `grok`, `claude`, or `codex`. Any other
  value exits with an error before anything else happens.
- `--repo` must be a git repository. The driver runs `git rev-parse` on it and aborts if it is not.
  Omit it and the campaign runs against this clone.
- `--max-turns` defaults to 50 and applies per node. The help text notes it is honored by Grok and
  Codex.
- `--yolo` auto-approves every agent tool call. The script prints a warning when it is on. Combined
  with an external `--repo`, that is a full remote-code-execution surface: the campaign and the
  campaign YAML are operator-supplied paths that can name arbitrary missions and repos, and yolo
  removes the approval prompt that would otherwise gate every shell command. The driver refuses
  `--yolo` against an external `--repo` unless you also pass `--yolo-untrusted-acknowledged` (or run
  the whole thing under `scripts/run-sandboxed.sh`). See [Safety and secrets](12-safety-and-secrets.md)
  for the threat model and the sandbox wrapper.

### The caveat: headless is not yet validated end to end

This is the honest part. The headless campaign path (`run-campaign.sh`) drives each runtime's CLI in
headless mode, which requires that CLI to be authenticated on the host (for example `grok login`),
and it is not yet fully validated end to end. The interactive path is the supported flow today: ask
your agent in chat, or use the `/goal` entry point, and drive the same missions in sequence through
the coordinator. The mechanical driver, its edge evaluator, and the gate semantics are all real and
tested in isolation; the gap is the full headless run against a live, authenticated CLI from start to
finish.

> If a headless run cannot authenticate, do not fight it. Drive the same missions interactively from
> your agent's chat or via `/goal`, one mission at a time, checking each readiness doc before
> starting the next. That is the same campaign, just with you reading the gate instead of the driver.
> The campaign YAML still documents the intended sequence and gates.

The headless auth requirement is also covered in [Installation](02-installation.md) (the per-runtime
CLI login step) and the caveat is restated in [Safety and secrets](12-safety-and-secrets.md). The
flag-by-flag CLI reference for `run-campaign.sh` and the other scripts is
[CLI reference](18-cli-reference.md).

---

## Reading the composition-e2e audit

`docs/composition-e2e-audit.md` is the record of an actual campaign run against autonomous-fleet
itself. Reading it tells you what a campaign exercises in practice, beyond the abstract DAG.

It is a drift index: a table of what a doc said versus what the code actually was, one row per
finding, each with a status. The `composition-e2e` campaign (the custom YAML annotated earlier) ran
`doc-sync` first, and the audit is the doc-sync node's output: five drift findings (D1 through D5),
all closed, each pinning a place where the README or a readiness doc had fallen out of sync with the
scripts and skills. The line that matters for the campaign's branching is "No code-bug findings
(`code_bug_findings: 0`)": that is exactly the metric the `docs -> bugs` edge tests. Because it was
0, the conditional `docs -> bugs` edge did not fire and the run took the `if: always` fallback
straight to `tests`. The audit is the receipt for that decision.

So when you write a conditional campaign and want to know what the gate metric will actually be on a
real repo, the composition-e2e audit is the worked example: it shows a real `fleet-outcome` metric
(`code_bug_findings: 0`) driving a real edge choice. The campaign's audit trail is how you verify
after the fact that the gate did what you intended.

---

## The archived presets

Three more YAML files sit in `scripts/campaigns/` but are archived, not active:

```
preset               status                                  blocked on
-------------------  --------------------------------------  ------------------------------------
secure-ship          archived-pending-exploratory-promotion  dependency-update (exploratory)
align-then-ship      archived-pending-exploratory-promotion  take-product-to-completion (exploratory)
handoff-to-product   archived-pending-exploratory-promotion  scaffold-align / contract-first-build / agents-layer
```

Each archived file is intentionally an empty stub: it carries only a `campaign:` id and a
`status: archived-pending-exploratory-promotion`, plus a header comment explaining why and how to
restore it. They are empty on purpose, so the autoplan and edge linter do not bind to missions that
do not exist as shipped skills. The missions they reference live under `docs/exploratory/missions/`
and have not earned the progress + readiness + external-archive triple required to ship.

> Do not try to run an archived preset. With no nodes, the driver has no `start` and rejects the
> file. The restore path is in each file's header comment: re-promote the exploratory mission per
> `docs/exploratory/missions/README.md`, then restore the campaign DAG from git history at the
> commit just before the demotion. That is a contributor task, covered in CONTRIBUTING.md and
> [Extending](13-extending.md), not something you do from the operator side.

When those missions promote, the presets come back with their original audit-gated DAGs. Until then,
the three active presets above are the full shipped set, and a custom `--campaign` file is how you
build anything more conditional than they offer.

---

← [Previous: Mission catalog](09-mission-catalog.md) ·
[Guide Index](README.md) ·
[Next: Strict mode](11-strict-mode.md) →
