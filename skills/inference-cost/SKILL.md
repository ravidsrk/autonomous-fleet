---
name: inference-cost
description: >-
  [Tier 2 - measurement-first cost optimization - full review gate] Reduce AI inference
  spend while holding output quality constant. Use when a repo has high LLM/API spend,
  needs cost controls, or wants model routing, prompt caching, batch/flex-tier pricing,
  provider abstraction, or token-hygiene cleanup. First gate is a baseline cost+quality
  harness; ship only sanctioned levers and block output-quality regressions. Hard-refuse
  subscription-token-as-backend/token-pool-proxy hacks; use billed provider API keys from
  env only. Runs via autonomous-fleet-core. Trigger on: "reduce inference cost", "optimize
  LLM spend", "lower token usage", "route cheaper models".
license: MIT
compatibility: Requires git, gh CLI, and billed provider API keys in the target repository env
metadata:
  author: "Ravindra Kumar <ravidsrk@gmail.com>"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
---

<!-- Corpus: prompts.md L2987 — Stage-9 prompt 18 "Inference-Cost Optimization (sanctioned levers only)". -->


# Mission: inference-cost

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` - read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| Provider SDK/docs skill | The repo already has one installed for the active provider | Use official provider docs and source-log the price/eval facts |

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (baseline, implement, integrator) | Provider SDK/docs skill if present | Repo harness conventions + official provider docs |
| @codex (review) | - | Mission review gate only |

## Deferred missions

Record in `docs/inference-cost-readiness.md` under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Cost issue is caused by missing product behavior or stubs | `take-product-to-completion` |
| Optimization exposes correctness bugs | `bug-batch` |
| Provider migration is a large architectural axis | `targeted-migration` |
| Missing regression/eval coverage blocks safe measurement | `test-coverage` |

**Empirical note:** Inference-cost optimization has no direct merge-success category and can quietly
damage product quality. Treat it as Tier 2: baseline first, frozen samples, full review gate, and
no shipment unless quality is held constant.

## GOAL

Reduce billed inference cost while preserving output quality for each optimized call class. The
deliverable is a before/after savings table with quality held constant, backed by a repeatable
baseline cost+quality harness. Optimize only with sanctioned levers: model routing, prompt
caching, batch/flex-tier pricing, a provider-abstraction layer, and token hygiene. Do not use
account, subscription, or credential-sharing hacks.

## HARD REFUSAL

Refuse any request, plan, code path, or workaround that turns a consumer subscription token into a
backend credential, builds a token-pool proxy, shares accounts, bypasses metering, or otherwise
avoids billed API usage through ToS-violating access. Use only provider-issued, billed API keys
from environment variables or the target repo's approved secret manager. If valid billed keys are
missing, record the blocker and stop the live-call portion of the mission.

## ROLE PIPELINE

- @claude establishes the baseline harness, selects sanctioned levers, and produces the readiness table.
- @codex implements the scoped optimization changes.
- A fresh build-blind @claude REVIEWS each PR: harness is real, costs are measured from the same
  sample, quality thresholds did not regress, and no forbidden credential/subscription hack exists.
- @claude is the INTEGRATOR: opens PR, merges (conflict-aware), cleans worktree.

## LEDGER

`docs/inference-cost-progress.md`. Per-task flags: `BASELINE=<t/f> PLANNED=<t/f> CODED=<t/f>
QUALITY_OK=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f> MERGED=<t/f>`. Plus a CALL-CLASS INDEX: each
inference call class, owner/module, baseline model/provider, baseline cost metric, quality sample,
candidate lever, `OPEN | SHIPPED via PR#n | REJECTED (quality/cost reason) | DEFERRED (reason)`.

## TASK STRUCTURE

- **T-BASELINE [@claude] - MEASUREMENT-FIRST GATE** - inventory inference call classes and build
  or extend a harness that runs a frozen, representative sample for each class. Capture prompt and
  completion tokens, provider/model, cacheability, latency when relevant, unit pricing source and
  date, total cost per sample, and a quality score or rubric result. Output
  `docs/inference-cost-baseline.md`. Do not plan savings from estimates alone.
- **T-PLAN [@claude] - SANCTIONED LEVERS ONLY** - for each call class, propose only these levers:
  model routing, prompt caching, batch/flex-tier pricing for async work, a provider-abstraction
  layer that preserves semantics, and token hygiene. Define acceptance thresholds: expected cost
  delta, max latency impact, and the exact quality gate. Freeze the CALL-CLASS INDEX.
- **T-OPTIMIZE... [per call class or lever, loop]** - @codex implements one coherent optimization per PR; a fresh build-blind @claude reviews each PR before @claude merges.
  Run the baseline harness and candidate harness against the same frozen sample. If a cheaper
  model, shorter prompt, cache behavior, batch mode, or provider route degrades any required sample
  or violates the rubric, reject it for that call class and do not ship it. Keep only changes with
  measured savings and `QUALITY_OK=t`.
- **T-FINAL [@claude]** - run the full suite and the cost+quality harness. Output
  `docs/inference-cost-readiness.md` with **`fleet-outcome` YAML** (`cost_regressed`,
  `quality_regressed`, `levers_open`), the before/after savings table, quality results, rejected
  levers with reasons, provider price sources, and all PRs. Ship as the final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/inference-cost-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission inference-cost DONE: docs/inference-cost-progress.md all task flags true,
docs/inference-cost-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE

Every shipped optimization has measured before/after savings with quality held constant, every
CALL-CLASS INDEX item is `SHIPPED`, `REJECTED`, or explicitly `DEFERRED`, suite and harness green,
`cost_regressed=false`, `quality_regressed=false`, `levers_open=0`, and
`docs/inference-cost-readiness.md` exists. Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)

- MEASUREMENT-FIRST is mandatory. Baseline cost and quality harness results are the first gate.
- SANCTIONED LEVERS ONLY: model routing, prompt caching, batch/flex-tier pricing, provider
  abstraction, and token hygiene.
- OUTPUT-QUALITY REGRESSION is blocking. A cheaper model or route that degrades a sample is not
  shipped for that call class.
- The final deliverable must include a before/after savings table with quality held constant.
- Use billed API keys from env or the approved secret manager only. Hard-refuse subscription-token
  backends, token-pool proxies, shared accounts, and metering bypasses.
- Token hygiene means removing waste while preserving required context and behavior. Do not trim
  prompts by deleting product-critical instructions or safety constraints.
- Any ambiguity -> preserve output quality and correctness over savings; record unshipped levers
  with measured evidence.
