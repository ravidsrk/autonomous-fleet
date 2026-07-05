# Mission catalog

Empirical tiers from arXiv 2601.15195 (MSR 2026 AIDev dataset, 33,596 agent-authored PRs;
cross-agent merge rates). Start Tier 1 unattended; review frozen artifacts for Tier 2–3.

## Shipped missions (real-run evidence required)

A mission stays in `skills/` only when it has BOTH `docs/<mission>-progress.md` and
`docs/<mission>-readiness.md` from a real run AND at least one external-repo run-archive.
Demoted on 2026-06-23 (Commit D): everything else now lives under
[`docs/exploratory/missions/`](../../../docs/exploratory/missions/) and is not active
in this surface.

### Tier 1 — safe unattended (~62–84% cross-agent merge)

| Skill | Use when |
|-------|----------|
| `doc-sync` | Docs drifted from code; README/setup/API docs wrong |
| `test-coverage` | Undertested modules; lock behaviour before refactor |

### Tier 2 — full review gate (~64–79% cross-agent merge)

| Skill | Use when |
|-------|----------|
| `adversarial-review-and-fix` | Code-grounded audit → frozen findings → fix loop |

## Exploratory missions (NOT active until promoted)

Documented but lacking the progress + readiness + external archive triple. See
[`docs/exploratory/missions/README.md`](../../../docs/exploratory/missions/README.md)
for the promotion criteria.

| Tier | Skill | Where it lives now |
|------|-------|--------------------|
| 1 | `dependency-update` | `docs/exploratory/missions/dependency-update/` |
| 1 | `cleanup` | `docs/exploratory/missions/cleanup/` |
| 2 | `bug-batch` | `docs/exploratory/missions/bug-batch/` |
| 2 | `targeted-migration` | `docs/exploratory/missions/targeted-migration/` |
| 2 | `design-integration` | `docs/exploratory/missions/design-integration/` |
| 2 | `inference-cost` | `docs/exploratory/missions/inference-cost/` |
| 3 | `take-product-to-completion` | `docs/exploratory/missions/take-product-to-completion/` |
| — | `agents-layer` | `docs/exploratory/missions/agents-layer/` |
| — | `contract-first-build` | `docs/exploratory/missions/contract-first-build/` |
| — | `scaffold-align` | `docs/exploratory/missions/scaffold-align/` |
| 2 | `browser-qa-fix` | `docs/exploratory/missions/browser-qa-fix/` |
| 2 | `incident-investigate` | `docs/exploratory/missions/incident-investigate/` |

**gstack-derived (2026-06-27):** `browser-qa-fix` and
`incident-investigate` remain active exploratory mappings from gstack specialist
flows into fleet frozen-ledger missions. Four additional gstack-derived designs
are parked under `docs/exploratory/missions/archive/`. Research:
[`docs/gstack-missions-research.md`](../../../docs/gstack-missions-research.md).

The three `—`-tier missions were demoted earlier (2026-06-22) and still carry
placeholder `@builder`/`@reviewer` role handles; they must adopt canonical
`@codex`/`@claude` staffing before promotion back to `skills/`.

These SKILLs do not load via the umbrella. To run one, promote it first (see the
exploratory README) or invoke it manually as a one-off operator action with the
understanding that it has no field hours.

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
`skills/fleet-program/references/campaigns.md` (if-outcome). Headless presets also
under `scripts/campaigns/` — only `repo-health`, `ship-with-proof`, and
`quality-gate` remain populated; the others (`secure-ship`, `align-then-ship`,
`handoff-to-product`, `gstack-quality`) reference demoted or parked missions and
are archived in-place pending promotion.

The earlier `handoff-to-product` campaign depended on three missions
(`scaffold-align`, `contract-first-build`, `agents-layer`) that lacked real-run
evidence and moved to `docs/exploratory/missions/` on 2026-06-22. The campaign
YAML is archived (`scripts/campaigns/handoff-to-product.yaml`); restore it on
first real run that promotes those missions back to `skills/`. See
`docs/exploratory/missions/README.md`.

Third-party skills (gstack, agent-skills, mattpocock): attach via Optional/Worker slots only —
see `skills/autonomous-fleet-core/references/community-skills.md` and
`docs/research-community-skills.md`.

## Composition reminder

Single mission = `autonomous-fleet-core` + **one adapter** + **one mission**. Each mission has
`## Required skills`, `## Optional skills`, `## Worker skills`, and `## Deferred missions`.
Multi-mission = `fleet-program` + core + adapter. See `skills/autonomous-fleet-core/references/composition.md`
and `fleet-outcome.md`.
