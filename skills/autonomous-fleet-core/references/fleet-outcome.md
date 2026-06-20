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
---
```

`run` is optional. Record when the host exposes timing/retries; use for dogfood comparisons and
tier validation. Do not branch campaign edges on `run` fields.

`unverified_assumptions` / `sources_logged` are the research-discipline gate (see engine.md
RESEARCH DISCIPLINE). Optional and cross-cutting: when present each must be a non-negative int.
T-FINAL records `unverified_assumptions: 0` once every external fact the build relied on has a
logged source in `docs/research-notes.md`; a campaign edge MAY branch on `unverified_assumptions
== 0`. Unlike `run` fields, these are branchable.

Then markdown body: human summary, indexes, **Recommended next missions** table (duplicate of
`deferred_missions` for readers).

## Mission-specific metrics

Add under `fleet-outcome.metrics`:

| Mission | Readiness doc | Metrics |
|---------|---------------|---------|
| `doc-sync` | `docs/doc-sync-readiness.md` | `drift_open: 0`, `code_bug_findings: <n>` |
| `test-coverage` | `docs/test-coverage-readiness.md` | `gaps_open: 0`, `coverage_regressed: false` |
| `dependency-update` | `docs/dependency-update-readiness.md` | `advisories_open: 0`, `majors_deferred: <n>` |
| `cleanup` | `docs/cleanup-readiness.md` | `cleanup_items_open: 0` |
| `bug-batch` | `docs/bug-batch-readiness.md` | `bugs_open: 0`, `bugs_skipped: <n>` |
| `adversarial-review-and-fix` | `docs/arch-build-readiness.md` | `p0_open: 0`, `p1_open: <n>`, `findings_open: 0`, `ops_queue_count: <n>` |
| `targeted-migration` | `docs/migration-readiness.md` | `migration_items_open: 0`, `old_axis_removed: true` |
| `design-integration` | `docs/parity-readiness.md` | `parity_items_open: 0`, `regressions: 0` |
| `landing-page-convergence` | `docs/landing-readiness.md` | `divergences_open: 0` |
| `legacy-rebuild` | `docs/rebuild-readiness.md` | `units_open: 0`, `floor_preserved: true` |
| `take-product-to-completion` | `docs/completion-readiness.md` | `in_items_open: 0`, `roadmap_count: <n>`, `stubs_remaining: 0` |
| `scaffold-align` | `docs/scaffold-align-readiness.md` | `align_items_open: 0`, `check_green: true`, `seam_frozen: true`, `scaffold_ok: true` |
| `contract-first-build` | `docs/contract-build-readiness.md` | `in_items_open: 0`, `roadmap_count: <n>`, `stubs_remaining: 0`, `ops_queue_count: <n>` |
| `agents-layer` | `docs/agents-layer-readiness.md` | `migration_items_open: 0`, `seam_unwired_open: 0`, `old_axis_removed: true`, `evals_passing: true`, `deploy_pending_ops: true` |

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
| `status == blocked` | Top-level status |
| `deferred_missions contains bug-batch` | Non-empty deferral to mission id |

Use numeric metrics for branching; avoid parsing free text.