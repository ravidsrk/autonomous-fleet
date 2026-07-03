# fleet-outcome block (machine-readable mission results)

Every mission **T-FINAL** readiness doc MUST begin with this YAML frontmatter. Campaign /
program coordinators parse it for `if` edges — do not rely on prose alone.

## Common fields (all missions)

```yaml
---
fleet-outcome:
  mission: <skill-name>           # required
  status: done                    # done | partial | blocked
  repo: <REPO_ROOT>               # absolute path
  base_branch: <BASE>             # integration branch used
  prs_merged: <n>                 # count merged this run
  deferred_missions:              # same rows as Recommended next missions
    - id: bug-batch
      reason: "..."
      blocker: null
  run:                            # optional — operational telemetry
    duration_min: <n>
    coordinator_turns: <n>
    worker_retries: <n>
  unverified_assumptions: 0       # optional — research-discipline gate (non-negative int)
  sources_logged: <n>             # optional — research-notes.md line count
  cost_estimate: <n>              # optional — running spend estimate (non-negative number)
  root_cause_audited: <bool>      # optional — ROOT_CAUSE_DEPTH discipline assertion
  archive_enabled: <bool>         # optional — ARCHIVE_ENABLED discipline assertion
  run_id: <YYYYMMDDTHHMMSSZ-mission-6hex>  # optional — run-archive pointer
---
```

`run` is optional. Record when the host exposes timing/retries; use for dogfood comparisons and
tier validation. Do not branch campaign edges on `run` fields.

`unverified_assumptions` / `sources_logged` are the research-discipline gate (see engine.md
RESEARCH DISCIPLINE). Optional and cross-cutting: when present each must be a non-negative int.
T-FINAL records `unverified_assumptions: 0` once every external fact the build relied on has a
logged source in `docs/research-notes.md`; a campaign edge MAY branch on `unverified_assumptions
== 0`. Unlike `run` fields, these are branchable.

`cost_estimate` is the running spend estimate for the run (see engine.md MODEL & COST ROUTING).
Optional; when present it must be a non-negative number (may be fractional). T-FINAL records it as
telemetry; a campaign edge MAY branch on it (e.g. `cost_estimate > <budget>`). A coordinator with no
cost signal omits it.

`root_cause_audited` is the ROOT_CAUSE_DEPTH discipline assertion (see engine.md ROOT_CAUSE_DEPTH).
Optional and cross-cutting: when present it must be a bool. T-FINAL of a review mission records
`root_cause_audited: true` once every `category: root_cause_depth` finding closed in this mission
had its `cascade_impact` paths re-EVIDed; `false` when any cascade path was deferred to a follow-up
mission (which then MUST appear in `deferred_missions`). Missions that filed no root-cause-depth
findings OMIT the field entirely — this keeps non-applicable readiness docs from carrying
discipline assertions they don't substantiate. Branchable; a campaign edge MAY branch on
`root_cause_audited == true`.

`archive_enabled` is the ARCHIVE_ENABLED discipline assertion (see engine.md ARCHIVE_ENABLED and
references/run-archive.md). Optional and cross-cutting: when present it must be a bool. T-FINAL of
a mission that emitted any first-class artifact (findings JSON, verifier summary, blind-fix file,
etc.) records `archive_enabled: true` ONLY AFTER `<SUBSTRATE>/validate_run_archive.py
.fleet/runs/<run_id>/` exits 0. The validator enforces schema shape, on-disk integrity (sha256 +
size), AND the cross-cutting mtime-ordering invariants from Layers 1-3 (blind_fix < findings,
verify_summary > findings, readiness with the latest mtime). Unlike `root_cause_audited`,
`archive_enabled` is HARD-GATED in the validator: a fleet-outcome with `status: done` AND
`archive_enabled: false` is rejected (the audit trail IS the discipline; you cannot ship done with
a broken archive). Missions that emitted no first-class artifacts OMIT the field. Branchable; a
campaign edge MAY branch on `archive_enabled == true`.

`run_id` is the run-archive pointer (see references/run-archive.md). Optional and cross-cutting:
when present it must match `YYYYMMDDTHHMMSSZ-<mission>-<6-hex>`, mirroring
`scripts.lib.fleet_run.RUN_ID_PATTERN`. Allows post-hoc tools (INFLATION POST-MORTEM, dashboards)
to jump straight to the archive without re-deriving the run_id from filesystem scans. Set when
`archive_enabled` is set.

Then markdown body: human summary, indexes, **Recommended next missions** table (duplicate of
`deferred_missions` for readers).

### degraded_mode (optional, closed enum)

`degraded_mode: no_scm_auth` — set by the engine PRECONDITIONS when `gh` was
unauthenticated and the run detoured to local merge-commits. The PR/review
pipeline never ran, so this mode is **incompatible with `status: done`**
(validator-enforced; report `partial`). Unknown mode strings are rejected —
the enum is closed so a typo cannot slip past the done-gate.

## Mission-specific metrics

Add under `fleet-outcome.metrics`. Shipped missions are validated by the
`MISSION_METRICS` table in `<SUBSTRATE>/lib/fleet_outcome.py`; exploratory
missions retain their `fleet-outcome` shape (the schema validator still
knows them) so a promotion run can land without schema churn.

| Mission | Readiness doc | Metrics |
|---------|---------------|---------|
| `doc-sync` (shipped) | `docs/doc-sync-readiness.md` | `drift_open: 0`, `code_bug_findings: <n>` |
| `test-coverage` (shipped) | `docs/test-coverage-readiness.md` | `gaps_open: 0`, `coverage_regressed: false` |
| `adversarial-review-and-fix` (shipped) | `docs/arch-build-readiness.md` | `p0_open: 0`, `p1_open: <n>`, `findings_open: 0`, `ops_queue_count: <n>` |
| `dependency-update` (exploratory) | `docs/dependency-update-readiness.md` | `advisories_open: 0`, `majors_deferred: <n>` |
| `cleanup` (exploratory) | `docs/cleanup-readiness.md` | `cleanup_items_open: 0` |
| `bug-batch` (exploratory) | `docs/bug-batch-readiness.md` | `bugs_open: 0`, `bugs_skipped: <n>` |
| `targeted-migration` (exploratory) | `docs/migration-readiness.md` | `migration_items_open: 0`, `old_axis_removed: true` |
| `design-integration` (exploratory) | `docs/parity-readiness.md` | `parity_items_open: 0`, `regressions: 0` |
| `landing-page-convergence` (exploratory) | `docs/landing-readiness.md` | `divergences_open: 0` |
| `legacy-rebuild` (exploratory) | `docs/rebuild-readiness.md` | `units_open: 0`, `floor_preserved: true`, `e2e_verified: true` |
| `take-product-to-completion` (exploratory) | `docs/completion-readiness.md` | `in_items_open: 0`, `roadmap_count: <n>`, `stubs_remaining: 0`, `e2e_verified: true` |
| `inference-cost` (exploratory) | `docs/inference-cost-readiness.md` | `cost_regressed: false`, `quality_regressed: false`, `levers_open: 0` |

## Metric definitions (shipped missions — operational, not vibes)

A campaign edge that branches on a metric is only as real as the metric's
definition (issue #99). Two coordinators counting the same repo must converge.

**doc-sync**
- `drift_open` — the number of DRIFT INDEX rows in `docs/doc-sync-audit.md`
  whose state is not `CLOSED via PR#n`. Counted FROM THE FROZEN AUDIT: rows are
  transcribed verbatim at T-AUDIT freeze; no invented, dropped, or renumbered
  rows. Zero means every frozen row is closed — not "no drift exists anywhere".
- `code_bug_findings` — the number of DECISIONS.md entries recorded during this
  run where a doc revealed wrong CODE behaviour (deferred to `bug-batch`, never
  fixed here). Informational; not done-gated.

**test-coverage**
- `gaps_open` — the number of rows in the frozen T-MAP gap list (the ledger's
  coverage-gap index: one row per file/function the freeze declared
  under-tested) not yet closed by a merged PR whose tests exercise that gap.
  Frozen at T-MAP; zero = every frozen row closed.
- `coverage_regressed` — boolean: the mission's final coverage measurement (the
  same tool/flags recorded in DECISIONS.md at T-MAP) is strictly lower than the
  T-MAP baseline for any file the run touched. Baseline and final numbers are
  recorded in the readiness doc.

**adversarial-review-and-fix**
- `p0_open` — CLOSE-INDEX rows of severity P0 whose state is not lane-terminal
  (Lane A `MERGED=true`, Lane B `HUMAN_GATED=true`, Lane 0
  `CODE_CLOSED=true, OPS_QUEUED=true`). Severities come from the frozen
  findings JSON, never re-graded after freeze.
- `p1_open` — same lane-terminal rule for severity-P1 CLOSE-INDEX rows; same
  frozen-severity discipline.
- `findings_open` — CLOSE-INDEX rows of ANY severity not lane-terminal
  (superset of the two above).
- `ops_queue_count` — `HUMAN_ACTION_REQUIRED:<id>` rows the run appended to the
  ops queue (`docs/arch-ops-actions.md` or the mission's equivalent).
  Informational; not done-gated.

Exploratory missions define their metrics in their own SKILL.md the same way
before promotion; a metric without an operational definition does not gate.

## Schema-verified review findings (optional, cross-cutting)

Review missions that emit findings to the JSON shape in
`skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json` MAY add
four extra metrics that surface the verifier's audit. These are cross-cutting:
any mission whose reviewer phase produces structured findings can record them.

| Metric | Meaning |
|--------|---------|
| `verified_findings` | Findings whose `evidence.quoted_line` was located in the cited `evidence.file_path` (whitespace-tolerant grep). |
| `unverified_findings` | Findings whose quote was NOT found — likely reviewer hallucination. Operators MUST inspect these before the fix loop consumes them. |
| `auto_applicable_findings` | Verified findings with `fix_strategy: auto` AND `confidence >= 80`. Builder MAY apply the recommended `fix_alternative` without human gating. |
| `human_gated_findings` | Verified findings with `fix_strategy: ask`. Human approval required before fix. |

All four must be non-negative integers when present. They populate from
`<SUBSTRATE>/verify_findings.py --summary-out summary.json` so coordinators wire
the verifier into the readiness doc without re-parsing JSON. Lineage:
GodModeSkill quoted-line self-consistency + xreview confidence/fix_strategy
gating, both ingested in the 2026-06-22 competitor audit. A campaign edge
MAY branch on `unverified_findings == 0` to refuse to advance the fix loop
on a hallucinated finding set.

## Example (adversarial-review-and-fix)

```yaml
---
fleet-outcome:
  mission: adversarial-review-and-fix
  status: done
  repo: /Users/me/my-app
  base_branch: fleet/secure-ship-base
  prs_merged: 14
  metrics:
    p0_open: 0
    p1_open: 2
    findings_open: 0
    ops_queue_count: 1
    # Optional schema-verified review findings audit (see above)
    verified_findings: 11
    unverified_findings: 0
    auto_applicable_findings: 3
    human_gated_findings: 8
  deferred_missions:
    - id: dependency-update
      reason: advisory on lodash transitive
      blocker: null
---
```

## Campaign condition expressions

`fleet-program` evaluates `if` on the **last completed node's** `fleet-outcome.metrics` and
top-level fields. Supported forms:

| Expression | Meaning |
|------------|---------|
| `always` | Unconditional edge |
| `p0_open > 0` | Metric comparison |
| `p0_open == 0` | |
| `code_bug_findings > 0` | |
| `unverified_findings == 0` | Schema-verified review gate (see above) |
| `status == blocked` | Top-level status |
| `deferred_missions contains bug-batch` | Non-empty deferral to mission id |

Use numeric metrics for branching; avoid parsing free text.
