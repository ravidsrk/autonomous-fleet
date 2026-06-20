# Mission catalog

Empirical tiers from arXiv 2601.15195 (MSR 2026 AIDev dataset, 33,596 agent-authored PRs;
cross-agent merge rates). Start Tier 1 unattended; review frozen artifacts for Tier 2–3.

## Tier 1 — safe unattended (~62–84% cross-agent merge)

| Skill | Use when |
|-------|----------|
| `doc-sync` | Docs drifted from code; README/setup/API docs wrong |
| `test-coverage` | Undertested modules; lock behaviour before refactor |
| `dependency-update` | Stale deps; security advisories; routine bumps |
| `cleanup` | Dead code, duplication, smells — not a full rebuild |

## Tier 2 — full review gate (~64–79% cross-agent merge; no direct category for UI/migration)

| Skill | Use when |
|-------|----------|
| `bug-batch` | Bug list/backlog — **reproduce-first** (failing test before fix) |
| `adversarial-review-and-fix` | Code-grounded audit → frozen findings → fix loop |
| `targeted-migration` | One-axis migration (framework, library, ORM, API) |
| `design-integration` | Whole-app design adoption (may need `/design-login` for MCP) |
| `landing-page-convergence` | Single page fidelity vs design export |

## Tier 3 — high blast radius (no direct category in the study; expect rework)

| Skill | Use when |
|-------|----------|
| `legacy-rebuild` | Modernize legacy app; preserve behaviour floor |
| `take-product-to-completion` | Stalled product → shippable; frozen IN/ROADMAP/FIX boundary |

## Adapters

| Skill | Runtime |
|-------|---------|
| `autonomous-fleet-adapter-orca` | Orca orchestration (reference adapter) |
| `autonomous-fleet-adapter-claude-code` | Claude Code (subagents + ledger) |
| `autonomous-fleet-adapter-grok` | Grok Build (subagents + ledger + `update_goal`) |
| `autonomous-fleet-adapter-codex` | OpenAI Codex (`/goal` + subagents) |
| `autonomous-fleet-adapter-template` | Authoring guide for new runtimes |

## Setup

| Skill | Use when |
|-------|----------|
| `setup-autonomous-fleet` | First fleet run on a repo — adapter, branch prefix, default bundle |

## Programs

| Skill | Use when |
|-------|----------|
| `fleet-program` | Mission chains and conditional campaign DAGs on one repo |

Presets: `skills/fleet-program/references/programs.md` (linear),
`skills/fleet-program/references/campaigns.md` (if-outcome). Headless presets also under
`scripts/campaigns/` (`repo-health`, `ship-with-proof`, `align-then-ship`, `quality-gate`).
One mission at a time per repo; `fleet-outcome` YAML on every readiness doc.

Third-party skills (gstack, agent-skills, mattpocock): attach via Optional/Worker slots only —
see `skills/autonomous-fleet-core/references/community-skills.md` and
`docs/research-community-skills.md`.

## Composition reminder

Single mission = `autonomous-fleet-core` + **one adapter** + **one mission**. Each mission has
`## Required skills`, `## Optional skills`, `## Worker skills`, and `## Deferred missions`.
Multi-mission = `fleet-program` + core + adapter. See `skills/autonomous-fleet-core/references/composition.md`
and `fleet-outcome.md`.