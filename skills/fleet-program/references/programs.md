# Preset fleet programs (linear)

For **conditional DAGs** (`if` edges on `fleet-outcome`), use [campaigns.md](campaigns.md).
Linear presets below map to campaigns with `always` edges — paste into program ledger **Campaign
spec** or run as MODE linear.

## repo-health

**When:** "clean up this repo", "make the codebase healthy", "docs and tests are stale", first
pass on an unfamiliar repo.

| # | Mission | Why |
|---|---------|-----|
| 1 | `doc-sync` | Highest merge rate; surfaces real state in docs |
| 2 | `test-coverage` | Lock behaviour before churn; uses doc-sync deferrals as gap hints |
| 3 | `cleanup` | Behaviour-preserving tidy after truth + tests exist *(exploratory)* |

## docs-and-tests

**When:** Documentation and coverage only — no code cleanup.

| # | Mission |
|---|---------|
| 1 | `doc-sync` |
| 2 | `test-coverage` |

## secure-ship

**When:** Pre-production hardening, security pass before release.

| # | Mission | Why |
|---|---------|-----|
| 1 | `adversarial-review-and-fix` | Frozen findings before churn |
| 2 | `dependency-update` | Advisories and stale deps after fixes *(exploratory)* |
| 3 | `doc-sync` | Docs match post-fix code |

The audit GATES the campaign (not `if: always`): it advances to deps only when clean
(`findings_open == 0`); a non-clean audit `status: blocked` halts the run. A deferred major bump
re-audits the changed surface before docs. See `campaigns.md` for the edge wiring.

## migrate-safe

**When:** Major upgrade or one-axis migration with safety net.

| # | Mission | Why |
|---|---------|-----|
| 1 | `test-coverage` | Characterization tests on migration surface |
| 2 | `targeted-migration` | The migration itself *(exploratory)* |
| 3 | `doc-sync` | Update setup/migration docs |

## fix-then-prove

**When:** Known bug backlog with weak tests.

| # | Mission |
|---|---------|
| 1 | `bug-batch` *(exploratory)* |
| 2 | `test-coverage` |

## ship-with-proof

**When:** Harden a branch before merge or PR — audit, prove with tests, sync docs. Optional
gstack post-gates (`ship`, `qa`) after the chain. Campaign YAML:
`scripts/campaigns/ship-with-proof.yaml`. See [campaigns.md](campaigns.md).

| # | Mission |
|---|---------|
| 1 | `adversarial-review-and-fix` |
| 2 | `test-coverage` |
| 3 | `doc-sync` |

## align-then-ship

**When:** Stalled product → shippable (Tier 3 — explicit user request). Pre-gate: `grill-with-docs`
or `office-hours`. Campaign: `scripts/campaigns/align-then-ship.yaml`.

| # | Mission |
|---|---------|
| 1 | `take-product-to-completion` *(exploratory)* |

## quality-gate

**When:** Production-readiness check without full doc-sync pass. Optional report-only QA after chain.
Campaign: `scripts/campaigns/quality-gate.yaml`.

| # | Mission |
|---|---------|
| 1 | `adversarial-review-and-fix` |
| 2 | `test-coverage` |

Community skill hooks: [community-skills.md](../../autonomous-fleet-core/references/community-skills.md).

## Custom chains

User-specified order wins. Rules:

- Max one active mission.
- Carry **Recommended next missions** from each readiness doc into the next mission's discovery
  task (T-AUDIT, T-MAP, T-SCAN, etc.).
- Do not insert the archived full-rebuild design (`legacy-rebuild`) or `take-product-to-completion`
  unless the user explicitly asks (Tier 3 blast radius).
