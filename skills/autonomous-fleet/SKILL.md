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
  version: "1.0.0"
  fleet-component: "umbrella"
---

# autonomous-fleet

Meta-skill for the [autonomous-fleet](https://github.com/ravidsrk/autonomous-fleet) framework.
This skill does not replace the engine — it orients you, picks a mission, and tells you which
skills to load next.

## What this framework is

A **skill package** of 20 installable skills (this one + core + adapters + missions + programs + setup).
Each single-mission run composes three layers:

| Layer | Skill(s) | Role |
|-------|----------|------|
| **Engine** | `autonomous-fleet-core` | Tool-agnostic coordinator method |
| **Adapter** | `autonomous-fleet-adapter-{orca,claude-code,grok,codex}` | Maps primitives to your runtime |
| **Mission** | `doc-sync`, `bug-batch`, … | Defines the job |

## Install (if skills are not already loaded)

**First time on a repo:** run `/setup-autonomous-fleet` after install (adapter, prefix, default bundle).

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-grok \
  --skill doc-sync \
  -y
```

Replace `autonomous-fleet-adapter-grok` with `autonomous-fleet-adapter-orca`,
`autonomous-fleet-adapter-claude-code`, or `autonomous-fleet-adapter-codex` for other runtimes. Install all:
`npx skills add https://github.com/ravidsrk/autonomous-fleet --skill '*' -y`

## How to route a request

1. Read the user's intent against the mission catalog in [references/missions.md](references/missions.md).
2. If intent names **multiple missions**, conditional flows ("if audit finds P0…"), or "healthy
   repo" → activate **`fleet-program`** (campaign DAG — not several mission skills at once).
3. If intent maps clearly to **one** mission → activate that mission skill and follow it.
4. If intent is vague ("clean up this repo") → prefer `fleet-program` preset `repo-health`, or
   the closest single mission; Tier 1 for first unattended single-mission runs.
5. Always activate **`autonomous-fleet-core`** and **one adapter** alongside the mission or program.

Default adapter on Grok Build: `autonomous-fleet-adapter-grok`.

## Quick routing

| User says | Mission |
|-----------|---------|
| sync docs, README stale, onboarding wrong | `doc-sync` |
| add tests, raise coverage | `test-coverage` |
| bump deps, security advisories | `dependency-update` |
| dead code, dedupe, tidy (not rewrite) | `cleanup` |
| fix bugs, bug backlog | `bug-batch` |
| audit and fix, harden before prod | `adversarial-review-and-fix` |
| migrate framework/library/ORM | `targeted-migration` |
| adopt design across whole app | `design-integration` |
| landing page match mockup | `landing-page-convergence` |
| rebuild legacy app | `legacy-rebuild` |
| finish stalled product | `take-product-to-completion` |
| docs then tests, repo health, mission chain, if-outcome campaign | `fleet-program` |
| ship safely, harden before PR | `fleet-program` preset `ship-with-proof` |
| finish stalled product, shippable end-to-end | `fleet-program` preset `align-then-ship` |
| production ready, quality gate | `fleet-program` preset `quality-gate` |

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