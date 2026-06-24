<!-- title: fleet-outcome schema | description: The machine-readable YAML block every mission emits at T-FINAL, field by field, and the campaign edge expressions that branch on it. | sidebar_order: 17 -->

# fleet-outcome schema

**On this page:** [What it is](#what-it-is) · [Where it lives](#where-it-lives) ·
[Required fields](#required-fields) · [Mission metrics](#mission-metrics) ·
[Cross-cutting fields](#cross-cutting-fields) · [Review-findings metrics](#review-findings-metrics) ·
[The readiness tasks block](#the-readiness-tasks-block) ·
[Campaign edge expressions](#campaign-edge-expressions) · [Validating an outcome](#validating-an-outcome) ·
[Field reference table](#field-reference-table)

The `fleet-outcome` block is the one piece of a run meant to be read by a machine. Every other
artifact in a run-archive (see [Run-archive anatomy](15-run-archive.md)) is structured for a human or
a verifier; this block is structured for the next mission in a campaign. It is the contract a
coordinator reads to decide what to do next, so it is small, typed, and validated. If you are
validating that a run finished cleanly, this is the block you check. If you are writing a campaign and
need a conditional gate, this is the block your `if` expression evaluates against.

## What it is

A `fleet-outcome` is YAML frontmatter at the top of a mission's readiness doc. When a mission reaches
its final state, the coordinator emits the **T-FINAL** transition (see [The engine](06-the-engine.md)
for the primitive, and [Trace schema](16-trace-schema.md) for the trace event). Part of that step is
writing the readiness doc, and that doc begins with a `fleet-outcome:` mapping that answers four
questions in a form a script can act on:

```
  +---------------------------------------------------------------+
  |  fleet-outcome                                                 |
  +---------------------------------------------------------------+
  |  WHAT ran        ->  mission: doc-sync                         |
  |  HOW it ended    ->  status: done | partial | blocked         |
  |  WHERE it ran    ->  repo, base_branch                         |
  |  WHAT it moved   ->  prs_merged, metrics{...}                  |
  +---------------------------------------------------------------+
            |
            v
  read by fleet-program / a campaign coordinator to pick the next node
```

The schema is enforced by `scripts/lib/fleet_outcome.py`. The human-facing reference that mirrors it
lives at `skills/autonomous-fleet-core/references/fleet-outcome.md`. When the two disagree, the
Python is the source of truth: it is what the validator runs.

## Where it lives

The block is the leading YAML frontmatter of a readiness doc under `docs/`. The parser,
`parse_readiness`, requires a leading `---` fence and a `fleet-outcome:` key inside it:

```yaml
---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: /Users/me/my-app
  base_branch: fleet/doc-sync-base
  prs_merged: 3
  metrics:
    drift_open: 0
    code_bug_findings: 1
---
# doc-sync readiness

(human summary, indexes, Recommended next missions table...)
```

Two structural rules the parser enforces, both from `fleet_outcome.py`:

- The document must start with `---` (a leading BOM, whitespace, or blank lines are stripped first,
  but nothing else may precede the fence). No frontmatter means `parse_readiness` raises
  `missing YAML frontmatter`.
- The frontmatter must be a mapping that contains the `fleet-outcome` key, and `fleet-outcome` must
  itself be a mapping. A bare scalar or a list under that key raises
  `fleet-outcome must be a mapping`.

After the closing `---`, the markdown body is free-form: a human summary, indexes, and a
**Recommended next missions** table that duplicates `deferred_missions` for readers.

## Required fields

Five top-level fields are required on every outcome. They come from `REQUIRED_TOP` in
`fleet_outcome.py`:

```
  REQUIRED_TOP = { mission, status, repo, base_branch, prs_merged }
```

```
  Field         Type     Constraint
  -----------   ------   -----------------------------------------------------
  mission       string   must be a key in MISSION_METRICS (see below)
  status        enum     one of: done | partial | blocked
  repo          string   absolute path to the repo root
  base_branch   string   the integration branch the run merged into
  prs_merged    int      count merged this run; must be a real int, not a bool
```

A missing required field produces `missing required field '<key>'`, one per field. The three
validations worth calling out:

`status` is checked against `VALID_STATUSES = { done, partial, blocked }`. Anything else fails with
`invalid status ..., must be one of done, partial, blocked`. There is no fourth status. A run that
could not start is `blocked`; one that did some but not all of the work is `partial`; one that
finished its scope is `done`.

`prs_merged` is checked with `type(prs_merged) is not int`, a strict identity check, not an
`isinstance`. So a YAML boolean (an `int` subclass in Python) is rejected with
`prs_merged must be int, got bool`. Write a number, not `true`.

`mission` is checked against the `MISSION_METRICS` table. An unknown name fails with
`unknown mission ..., not in MISSION_METRICS`. You cannot invent a mission slug and have it validate;
it has to be one the framework ships or carries as exploratory.

## Mission metrics

If `mission` is a known mission, the outcome must carry a `metrics:` mapping, and that mapping must
contain every metric the mission requires. The required set per mission is the `MISSION_METRICS`
table in `fleet_outcome.py`. This is the exact table the validator enforces:

```
  Mission                         Required metrics
  -----------------------------   ------------------------------------------------
  doc-sync                        drift_open, code_bug_findings
  test-coverage                   gaps_open, coverage_regressed
  dependency-update               advisories_open, majors_deferred
  cleanup                         cleanup_items_open
  bug-batch                       bugs_open, bugs_skipped
  adversarial-review-and-fix      p0_open, p1_open, findings_open, ops_queue_count
  targeted-migration              migration_items_open, old_axis_removed
  design-integration              parity_items_open, regressions
  landing-page-convergence        divergences_open
  legacy-rebuild                  units_open, floor_preserved, e2e_verified
  take-product-to-completion      in_items_open, roadmap_count, stubs_remaining,
                                  e2e_verified
  inference-cost                  cost_regressed, quality_regressed, levers_open
```

> Three of these are shipped missions (`doc-sync`, `test-coverage`,
> `adversarial-review-and-fix`); the rest are exploratory. The validator knows all of them so a
> promotion run can land without schema churn. See the [Mission catalog](09-mission-catalog.md) for
> which are shipped today.

Two rules govern the metrics mapping. First: a required metric that is absent produces
`metrics missing '<key>' for <mission>`, one per missing key. So a `doc-sync` outcome with
`metrics: { drift_open: 0 }` fails because `code_bug_findings` is missing.

Second: every metric value must be numeric or boolean. The validator allows `bool`, `int`, and
`float`, and rejects anything else with `metric '<key>' must be numeric or bool, got <type>`. A
non-finite float (`inf`, `nan`) is rejected with `metric '<key>' must be finite`. Do not put free text
in a metric: campaign edges compare metrics numerically. Use numeric metrics for branching, avoid
parsing free text.

The end-to-end gate. Two missions, `take-product-to-completion` and `legacy-rebuild`, are in
`E2E_VERIFIED_MISSIONS`. For these, a `status: done` outcome whose `metrics.e2e_verified` is not
exactly `True` is rejected:

```
  cannot be done without end-to-end verification: a green test suite is not
  proof a product works; e2e_verified must be true (verify the real end-to-end
  result state, not exit codes)
```

This is deliberate. For a product-completion or rebuild mission, exit codes are not proof. The
outcome cannot claim `done` unless the run actually verified the real end-to-end result.

## Cross-cutting fields

Beyond the required core and the mission metrics, several optional top-level fields are
cross-cutting: any mission may set them, and each has its own validation. A mission with nothing to
assert omits them. Omitting an inapplicable field is the correct move, not setting it to a placeholder.

```yaml
run: # optional operational telemetry, NOT branchable
  duration_min: 12
  coordinator_turns: 40
  worker_retries: 1
unverified_assumptions: 0 # research-discipline gate, non-negative int
sources_logged: 18 # research-notes.md line count, non-negative int
cost_estimate: 1.42 # running spend estimate, non-negative number
root_cause_audited: true # ROOT_CAUSE_DEPTH discipline assertion, bool
archive_enabled: true # ARCHIVE_ENABLED discipline assertion, bool
run_id: 20260624T141500Z-doc-sync-a1b2c3 # run-archive pointer
deferred_missions: # same rows as Recommended next missions
  - id: bug-batch
    reason: "transitive advisory on lodash"
    blocker: null
```

`run` is optional operational telemetry: duration, coordinator turns, worker retries. Record it when
the host exposes timing and retry counts. It is for dogfood comparisons and tier validation. The
validator does not type-check the `run` sub-fields, and you must not branch a campaign edge on them.

`unverified_assumptions` and `sources_logged` are the research-discipline gate (see the engine
RESEARCH DISCIPLINE doctrine). When present, each must be a non-negative int; a negative value or a
non-int fails with `<key> must be a non-negative int`. T-FINAL records `unverified_assumptions: 0`
once every external fact the build relied on has a logged source in `docs/research-notes.md`. Unlike
`run` fields, this one is branchable: a campaign edge MAY gate on `unverified_assumptions == 0`.

`cost_estimate` is the running spend estimate for the run (see the engine MODEL & COST ROUTING
doctrine). When present it must be a non-negative finite number, and it may be fractional. A bool,
a non-number, a non-finite float, or a negative value fails with
`cost_estimate must be a non-negative finite number`. A coordinator with no cost signal omits it. It
is branchable, for example `cost_estimate > 5`.

`root_cause_audited` is the ROOT_CAUSE_DEPTH discipline assertion. When present it must be a bool. A
review mission records `true` once every `root_cause_depth` finding it closed had its
`cascade_impact` paths re-EVIDed, and `false` when any cascade path was deferred (which then MUST
appear in `deferred_missions`). Missions that filed no root-cause-depth findings OMIT the field. It is
branchable. Unlike `archive_enabled`, this field does NOT gate `status: done` from the validator: its
semantics depend on whether any such findings were filed, so that gating lives in the SKILL prose.

`archive_enabled` is the ARCHIVE_ENABLED discipline assertion (see
[Run-archive anatomy](15-run-archive.md)). When present it must be a bool. A mission that emitted any
first-class artifact (findings JSON, verifier summary, blind-fix file) records `archive_enabled:
true` only after `scripts/validate_run_archive.py .fleet/runs/<run_id>/` exits 0. That validator
checks schema shape, on-disk integrity (sha256 plus size), and the mtime-ordering invariants from
the substrate layers. Missions that emit no first-class artifacts (a pure doc update with no
findings or verifier outputs) OMIT the field.

This is the one cross-cutting field that is hard-gated against `status: done`. If you set
`archive_enabled: false` AND `status: done`, the validator rejects it:

```
  cannot be done with archive_enabled=false: the run-archive manifest is the
  audit trail (engine.md ARCHIVE_ENABLED); a status=done without a passing
  archive is not auditable. Set status=partial instead, or fix the manifest so
  archive_enabled=true.
```

The audit trail is the discipline. If you asserted the archive is not enabled, you are not done.

`run_id` is the run-archive pointer. When present it must match the run-id pattern, which mirrors
`scripts.lib.fleet_run.RUN_ID_PATTERN`:

```
  ^[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*[a-z0-9]-[0-9a-f]{6}$

  example: 20260624T141500Z-doc-sync-a1b2c3
           \__________/ \_____/ \____/
            timestamp    mission  6 hex
```

A non-matching value fails with `run_id must match YYYYMMDDTHHMMSSZ-<mission>-<6-hex>`. It lets
post-hoc tools (the inflation post-mortem, dashboards) jump straight to the archive without
re-deriving the id from a filesystem scan. Set it whenever you set `archive_enabled`.

`deferred_missions` is a list of next-mission rows: each is the same row that appears in the
**Recommended next missions** table in the body. If present it must be a list, else
`deferred_missions must be a list`. Each row carries an `id` (a mission slug), a `reason`, and a
`blocker` (or `null`). Campaign edges can test it with `deferred_missions contains <id>`.

## Review-findings metrics

Review missions that emit structured findings to the JSON shape in
`skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json` MAY add four extra metrics
under `metrics`. These are cross-cutting: any mission whose reviewer phase produces structured
findings can record them. They populate from `scripts/verify_findings.py --summary-out summary.json`
so a coordinator wires the verifier output straight into the readiness doc.

```
  Metric                      Meaning
  -------------------------   -------------------------------------------------
  verified_findings           findings whose quoted_line was located in the
                              cited file (whitespace-tolerant grep)
  unverified_findings         findings whose quote was NOT found: likely a
                              reviewer hallucination; inspect before the fix
                              loop consumes them
  auto_applicable_findings    verified findings with fix_strategy: auto AND
                              confidence >= 80; builder MAY auto-apply
  human_gated_findings        verified findings with fix_strategy: ask; human
                              approval required before fix
```

All four must be non-negative integers when present (they go through the same numeric-or-bool metric
check as any other metric). A campaign edge MAY branch on `unverified_findings == 0` to refuse to
advance a fix loop on a hallucinated finding set.

## The readiness tasks block

The markdown ledger (`docs/<mission>-progress.md`) is the source of narrative loop memory: per-task
flags, the frozen audit index, the CONTEXT HANDOFF block. The outcome's optional `tasks:` block is a
small machine-readable snapshot of that ledger that lets the validator catch a class of bug the prose
ledger cannot: a row whose flags say something that is physically impossible. It is the
ledger-contradiction guard.

When present, `tasks:` must be a list. Each row is a mapping of booleans for one unit. The validator
walks each row through `_validate_task_row_invariants` in `fleet_outcome.py` and rejects three
impossible combinations:

```
  Row flags                         Rejected with
  -------------------------------   -----------------------------------------------
  merged: true, built: not true     "task <id>: merged a task that never built"
  merged: true, wt_clean: not true  "task <id>: merged but worktree not clean"
  reviewed: true, pr_open: not true "task <id>: reviewed before PR opened"
```

Each is a hard invariant of the loop, not a heuristic. You cannot merge a unit that never built. You
cannot merge while the worktree is dirty (the conflict-aware merge and checkout-cleanup rules forbid
it). You cannot have reviewed a unit before its PR existed (the reviewer reads the PR). A row that
asserts any of these is a ledger that contradicts itself, and the validator says so by row `id` (or
`#<index>` if the row has no `id`).

```yaml
tasks: # optional machine-readable ledger snapshot, validated for self-consistency
  - id: T-BUILD-auth
    built: true
    pr_open: true
    reviewed: true
    merged: true
    wt_clean: true
```

The check is strict-identity on `True`: a row is only flagged when `merged`/`reviewed` is exactly
`True` and the partner flag is anything other than `True` (missing, `false`, `null`). A row with no
`merged: true` is never flagged, so a partial run with in-flight units validates cleanly. The block is
optional: a mission that does not emit a snapshot omits it entirely, and the prose ledger stays the
loop's authority. It exists to make "merged-but-never-built", "merged-but-not-clean", and
"reviewed-before-PR" un-claimable in a machine-readable outcome, not to duplicate the ledger.

## Campaign edge expressions

A `fleet-program` campaign is a DAG of missions. Each edge carries an optional `if` expression. The
coordinator evaluates it against the last completed node's `fleet-outcome` and takes the edge if it is
true. Evaluation is `eval_edge` in `fleet_outcome.py`. These are the only supported forms:

```
  Expression                              Meaning
  -------------------------------------   ----------------------------------------
  always                                  unconditional edge, always taken
  p0_open > 0                             metric comparison: >, <, >=, <=
  p0_open == 0                            metric equality: ==, !=
  status == blocked                       top-level field equality
  unverified_findings == 0                review-findings gate
  deferred_missions contains bug-batch    non-empty deferral to a mission id
```

How the comparison resolves, straight from the implementation:

The left operand is looked up by `_metric_value`: it checks `metrics` first, then falls back to a
top-level field of the same name. So `status == blocked` reads the top-level `status`, and
`p0_open > 0` reads `metrics.p0_open`. If the name exists in neither place, `eval_edge` raises
`metric '<name>' not found in outcome`.

The right operand is a single token, parsed by `_parse_right_operand`: `true` and `false` become
booleans, a bare integer becomes an int, a decimal becomes a float, anything else stays a string
(quotes are stripped). The token is anchored to end-of-string. A trailing extra token (a typo like
`status == blocked now`) does not match the comparison regex and falls through to
`unsupported expression`, so the edge is logged and skipped rather than silently mis-comparing.

Ordering operators (`>`, `<`, `>=`, `<=`) coerce both sides to float through `_coerce_for_ordering`.
A bool coerces to 0 or 1. A value that cannot become a finite float raises
`cannot compare metric values numerically`. Equality operators (`==`, `!=`) compare the values
as-is, no coercion.

```
            eval_edge("p0_open == 0", outcome)
                          |
                          v
     +--------------------------------------------------+
     | look up "p0_open" -> metrics.p0_open, else top   |
     | parse right operand "0" -> int 0                 |
     | == is equality -> compare as-is                  |
     +--------------------------------------------------+
                          |
                  True  <-+->  False  (edge taken / not taken)
```

`pick_next_node` walks a node's edges in order and returns the first matched edge's `to`. An edge
whose expression references a missing metric raises inside `eval_edge`, and `pick_next_node` treats a
raising edge as not-taken (it catches `ValueError` and continues) so a malformed edge cannot strand a
later `if: always` fallback. But a matched edge whose `to` is missing or empty is a misconfigured
campaign, so `pick_next_node` raises `matched edge on node ... has no valid 'to'` rather than
returning `None`. When no edge matches, it returns `None`, which the coordinator reads as the run
being done at this node.

## Validating an outcome

Two CLI entrypoints exercise this schema, both thin wrappers over the same library. Validate every
readiness doc, or specific ones:

```bash
# validate all docs/*-readiness.md
python3 scripts/validate_fleet_outcome.py

# validate specific files
python3 scripts/validate_fleet_outcome.py docs/doc-sync-readiness.md
```

With no file arguments it globs `docs/*-readiness.md`. It prints `OK <name> mission=<m>` per passing
doc, `FAIL <error>` per validation error, returns 0 when all pass and 1 when any fail. Malformed YAML
in one doc fails that doc alone; it does not abort the batch. This validator runs as part of
`scripts/validate-all.sh` (see [CLI reference](18-cli-reference.md)).

Evaluate a single edge expression, or pick the next campaign node, against one readiness doc:

```bash
# evaluate one expression: exit 0 if true, 1 if false
python3 scripts/eval-campaign-edge.py \
  --readiness docs/doc-sync-readiness.md \
  --expr 'code_bug_findings > 0'

# resolve the next node from a campaign YAML
python3 scripts/eval-campaign-edge.py \
  --readiness docs/doc-sync-readiness.md \
  --campaign scripts/campaigns/repo-health.yaml \
  --current-node doc-sync
```

The `--expr` form prints `{"expr": ..., "result": true|false}` and returns 0 when the expression is
true, 1 when false. The `--campaign` form prints `{"current": ..., "next": ...}` where `next` is the
resolved node id or `null` at a terminal node.

## Field reference table

The complete top-level schema, as enforced by `validate_outcome`. Required fields are marked; every
other field is optional and omitted when not applicable.

```
  Field                    Type      Req   Branchable   Notes
  ----------------------   -------   ---   ----------   -----------------------------
  mission                  string    yes   no           must be in MISSION_METRICS
  status                   enum      yes   yes          done | partial | blocked
  repo                     string    yes   no           absolute path
  base_branch              string    yes   no           integration branch
  prs_merged               int       yes   no           strict int, not bool
  metrics                  mapping   *     yes          required if mission known;
                                                        each value numeric or bool
  run                      mapping   no    no           timing/retry telemetry
  unverified_assumptions   int>=0    no    yes          research-discipline gate
  sources_logged           int>=0    no    yes          research-notes.md line count
  cost_estimate            number    no    yes          non-negative finite; fractional ok
  root_cause_audited       bool      no    yes          NOT a status=done gate
  archive_enabled          bool      no    yes          hard-gates status=done
  run_id                   string    no    no           RUN_ID_PATTERN
  deferred_missions        list      no    via contains rows of {id, reason, blocker}
  tasks                    list      no    no           ledger snapshot; rows checked
                                                        for self-consistency
```

For the trace event that carries this outcome at T-FINAL, see [Trace schema](16-trace-schema.md). For
the on-disk artifacts the outcome's `archive_enabled` and `run_id` point at, see
[Run-archive anatomy](15-run-archive.md). For how a campaign chains nodes on these edges, see
[Missions vs campaigns](05-missions-vs-campaigns.md).

---

← [Trace schema (v1)](16-trace-schema.md) · [Guide Index](README.md) ·
[CLI reference](18-cli-reference.md) →
