---
name: autonomous-fleet
description: >-
  Entry point for the autonomous-fleet multi-agent engineering framework. Use whenever the
  user wants fully-autonomous coding runs, multi-agent orchestration, PR-per-task pipelines,
  or mentions autonomous-fleet — even if they have not named a specific mission yet. Routes
  to one mission or to fleet-program for sequential chains, loads
  autonomous-fleet-core plus a runtime adapter, and runs unattended on the current repo.
  Install from github.com/ravidsrk/autonomous-fleet. Trigger on: "use autonomous-fleet",
  "run autonomous fleet", "autonomous multi-agent run", "fleet mission", "which fleet
  mission should I use".
license: MIT
compatibility: Requires git and gh CLI in the target repository; install skills via npx skills
metadata:
  author: "ravidsrk"
  version: "1.0.1"
  fleet-component: "umbrella"
---

# autonomous-fleet

Meta-skill for the [autonomous-fleet](https://github.com/ravidsrk/autonomous-fleet) framework.
This skill does not replace the engine — it orients you, picks a mission, and tells you which
skills to load next.

## What this framework is

A **skill package** of installable skills (this one + core + adapters + 3 proven mission
skills + `fleet-program` + setup). Each single-mission run composes three layers:

| Layer | Skill(s) | Role |
|-------|----------|------|
| **Engine** | `autonomous-fleet-core` | Tool-agnostic coordinator method |
| **Adapter** | `autonomous-fleet-adapter-{orca,claude-code,grok,codex}` | Maps primitives to your runtime |
| **Mission** | `doc-sync`, `test-coverage`, `adversarial-review-and-fix` | Defines the job |

> Exploratory missions (not yet shipped end-to-end): see
> [`docs/exploratory/missions/`](../../docs/exploratory/missions/). These are
> documented but lack a real-run progress + readiness + external archive
> triple and so are not active in the shipped surface.

## Install (if skills are not already loaded)

**First time on a repo:** run `/setup-autonomous-fleet` after install (adapter, prefix, default bundle).

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-orca \
  --skill fleet-program \
  --skill doc-sync \
  -y
```

On Orca, also load Orca's companion skills (`orchestration`, `orca-cli`) for full-handoff vs
supervised routing — see `autonomous-fleet-adapter-orca` → `references/orca-platform.md`.
For Grok, Claude Code, or Codex hosts, swap `-orca` for `-grok`, `-claude-code`, or `-codex`.
Install all: `npx skills add https://github.com/ravidsrk/autonomous-fleet --skill '*' -y`

## How to route a request

1. Read the user's intent against the mission catalog in [references/missions.md](references/missions.md).
2. If intent names **multiple missions**, conditional flows ("if audit finds P0…"), or "healthy
   repo" → activate **`fleet-program`** (campaign DAG — not several mission skills at once).
3. If intent maps clearly to **one** mission → activate that mission skill and follow it.
4. If intent is vague ("clean up this repo") → prefer `fleet-program` preset `repo-health`, or
   the closest single mission; Tier 1 for first unattended single-mission runs.
5. Always activate **`autonomous-fleet-core`** and **one adapter** alongside the mission or program.

Default adapter: `autonomous-fleet-adapter-orca` (reference runtime). On Grok Build without Orca,
use `autonomous-fleet-adapter-grok`.

## Quick routing

| User says | Mission |
|-----------|---------|
| sync docs, README stale, onboarding wrong | `doc-sync` |
| add tests, raise coverage | `test-coverage` |
| audit and fix, harden before prod | `adversarial-review-and-fix` |
| docs then tests, repo health, mission chain, if-outcome campaign | `fleet-program` |
| ship safely, harden before PR | `fleet-program` preset `ship-with-proof` |
| production ready, quality gate | `fleet-program` preset `quality-gate` |

Other intents that previously routed to a dedicated mission
(`bug-batch`, `cleanup`, `dependency-update`, `design-integration`,
`inference-cost`, `take-product-to-completion`, `targeted-migration`) are
exploratory at the moment — see `docs/exploratory/missions/`. Parked
mission designs live under `docs/exploratory/missions/archive/`. Until a
mission is promoted back to `skills/`, route those intents to
`adversarial-review-and-fix` (which can file the work as a deferred
mission in its outcome) or fall back to a manual operator pass. Re-route
directly once a mission is promoted.

**gstack-derived exploratory missions (2026-06-27)** — active designs are
documented in `docs/exploratory/missions/`, not active until promoted:

| User says | Exploratory mission |
|-----------|---------------------|
| browser QA, test the site and fix, dogfood staging | `browser-qa-fix` |
| incident RCA, root cause, regression test for outage | `incident-investigate` |

Research: [`docs/gstack-missions-research.md`](../../docs/gstack-missions-research.md).

Full tier notes and merge-rate guidance: [references/missions.md](references/missions.md).
Community skill bundles: `autonomous-fleet-core` → `references/community-skills.md`.

## Execution checklist

After routing, load and follow these skills in full (do not improvise the method):

1. `autonomous-fleet-core` — `references/engine.md` and `references/composition.md`
2. Your runtime adapter skill
3. The chosen mission skill **or** `fleet-program` for a chain (one mission active at a time)

The target repo is wherever the user is working (`git rev-parse --show-toplevel`). No
placeholders — discover maintainer, stack, and scope per the core engine.

## Safe defaults

- **First unattended run:** `doc-sync` or `test-coverage` (Tier 1, highest merge rates).
- **Never run** `autonomous-fleet-core` alone — it needs a mission + adapter.
- **Authoring a new runtime:** copy `autonomous-fleet-adapter-template`, not this skill.