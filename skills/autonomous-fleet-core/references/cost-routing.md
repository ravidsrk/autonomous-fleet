# Cost Routing

<!-- demoted from engine.md (issue #84) -->
═══════════════════════════════════════════════════════════
MODEL & COST ROUTING — match the model tier to the role; track spend; gate on a budget.
═══════════════════════════════════════════════════════════
Running every worker at flat max effort is the difference between an affordable unattended fleet and
an unaffordable one. DISPATCH carries an optional per-task `model` / `effort`; the coordinator routes
by role, not uniformly, and records a running cost estimate so a mission can stop before it overruns.

- DISPATCH(task, handle) MAY carry `model`/`effort`. When the adapter's host supports per-call model
  or effort selection, the coordinator sets it per the ROLE TIER below; when it does not, it records
  the intended tier in the ledger and uses the host's single available setting. This is a hint, not
  a hard primitive — an adapter without model selection ignores it.
- ROLE TIER (default; a mission may override in DECISION DEFAULTS):
  - STRONG (highest reasoning): the coordinator itself, the REVIEWER, and any planning/decomposition
    or freeze step (T-AUDIT). Judgment-heavy, low-volume, high-leverage — never cheap out here. The
    freeze emits the task DAG the PLAN/DAG VALIDATION GATE checks before the first SPAWN_WORKER.
  - MID: bulk BUILDERS on Tier 1/2 missions and well-scoped task units.
  - CHEAP (fastest/cheapest): mechanical or high-volume steps — build-failure triage, lint/format
    fixes, log scans, status summarization, the dashboard render.
  Record the tier chosen per role in DECISIONS.md (alongside the launch flags).
- BUDGET: a mission MAY set a `BUDGET` decision-default (a soft spend ceiling for the run). The
  coordinator keeps a running `cost_estimate` in the ledger. `cost_estimate` is a DECLARED ESTIMATE
  aggregation, NOT a measured spend: it is the sum of the per-task estimates the adapter exposes, or
  a coarse token-based estimate when it does not — never a reconciled provider bill. As
  `cost_estimate` approaches BUDGET: downgrade non-critical workers a tier, then defer remaining
  optional work via `fleet-outcome.deferred_missions`, then GOAL_BLOCKED with a clear note. NEVER
  silently exceed a stated BUDGET; surface it like any hard gate.
- T-FINAL records `cost_estimate: <n>` in the readiness `fleet-outcome` (a non-negative number,
  parallel to `unverified_assumptions`). It is reportable telemetry — an ESTIMATE, not a billed
  figure — and a campaign edge MAY branch on it; a coordinator with no cost signal omits it (it is
  optional).
