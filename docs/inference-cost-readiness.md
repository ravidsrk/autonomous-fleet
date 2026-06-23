---
fleet-outcome:
  mission: inference-cost
  status: done
  repo: ravidsrk/autonomous-fleet
  base_branch: ravidsrk/inference-cost-dogfood
  prs_merged: 0
  metrics:
    cost_regressed: false
    quality_regressed: false
    levers_open: 3
  deferred_missions: []
  unverified_assumptions: 0
  sources_logged: 0
  cost_estimate: 0.4
  run:
    duration_min: 20
    note: inference-cost dogfood — mission-fit adapted; measurement-first gate delivered
---

# inference-cost readiness — autonomous-fleet (2026-06-23)

## Mission-fit adaptation (recorded per engine SELF-ORIENTATION step 4)

The literal mission (reduce a product's LLM/API spend) does NOT match this repo: autonomous-fleet has
no product inference layer — it shells out to the claude/codex/grok CLIs via adapters, and the
inference-cost mission itself is now demoted to docs/exploratory/missions/. Rather than fabricate a
target, the mission's INTENT was adapted to the framework's analog: its OWN operational spend, tracked
as the `cost_estimate` fleet-outcome metric and governed by the engine's MODEL & COST ROUTING block.

## Measurement-first gate (the deliverable)

The framework tracked `cost_estimate` across runs but had NO tool to aggregate it — the 'seat' metric
has scripts/analyze_seat.py, cost had nothing. Built the analog: scripts/analyze_cost.py +
scripts/lib/analyze_cost.py (per-run + aggregate, mirrors analyze_seat), 10 tests, 100% coverage, a
mutation entry pinning the aggregation. First real measurement of the framework's own spend:

```
runs: 8   missing_cost: 1   total_cost: 8.75
by_mission:
  adversarial-review-and-fix  6.90   (79%)
  test-coverage               1.55
  cleanup                     0.20
  doc-sync                    0.10
```

## What the measurement reveals (cost-routing audit)

- Spend concentrates almost entirely in adversarial-review-and-fix (79%): the multi-agent
  review-heavy mission (finder + verifier panels). That is exactly where MODEL & COST ROUTING's
  "bulk builders/reviewers cheaper" lever has the most leverage.
- 1 run carries no `cost_estimate` (a telemetry gap the harness now flags as `missing_cost`).
- Quality gate: the framework's mutation gate + coverage --fail-under=100 + e2e checks ARE the
  output-quality-regression guard the mission requires; cheaper routing that regressed them would be
  caught.
- The ToS subscription-token-as-backend hack stays hard-refused (inference-cost SKILL.md + the H3
  worker self-discipline); billed API keys from env only.

## Levers surfaced, NOT executed (levers_open: 3 — operator-addressable, not framework code)

The actual reductions live in the OPERATOR's dispatch choices, not framework code, so they are
surfaced for a human decision, not auto-applied:

1. Route the bulk review finders/verifiers in adversarial-review-and-fix to a cheaper tier (the
   coordinator + final verdict stay strong); the measurement shows this is 79% of spend.
2. Close the telemetry gap: the 1 run missing `cost_estimate` (make T-FINAL always record it).
3. Enable prompt caching / batch-or-flex-tier pricing at the adapter CLI layer.

## Why status: done

This is the full extent inference-cost can achieve ON this repo: the framework has no inference code
to optimize, so the measurement-first gate + the routing audit + the surfaced operator levers IS the
deliverable. Applying levers 1-3 is an operator action (dispatch/model choice), out of framework
scope. cost_regressed:false and quality_regressed:false — this run added a measurement tool, changed
no cost or behaviour.

## Verification

- analyze_cost: 10 tests, 100% coverage, mutation `analyze-cost-total-sum-off` caught (breaking the
  sum fails 3 tests). validate-all + the full mutation gate green.
