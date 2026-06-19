# composition-e2e — runtime goal dogfood

Dogfood of **runtime goal binding** (R-09) on the existing `composition-e2e` campaign artifacts.

## What was added

| Artifact | Change |
|----------|--------|
| `docs/fleet-program-progress.md` | `## Runtime goal` section with campaign DONE condition |
| `skills/autonomous-fleet-core/references/runtime-goals.md` | Adapter binding spec |
| `skills/autonomous-fleet-core/references/engine.md` | Primitives 9–12 + AUTONOMY ENFORCEMENT |
| `skills/fleet-program/SKILL.md` | Runtime goal binding flow |
| `skills/autonomous-fleet-adapter-{grok,claude-code,codex,orca}` | SET_GOAL / GOAL_COMPLETE mapping |
| `scripts/validate-goal-condition.sh` | Lint goal conditions reference `docs/` |
| `scripts/run-mission-headless.sh` | Headless wrapper with `/goal` in prompt |

## Campaign goal (Grok)

At campaign start, coordinator runs:

```
/goal Campaign composition-e2e DONE: docs/fleet-program-progress.md PHASE is DONE,
every node in Node status is DONE or SKIPPED,
each readiness doc has valid fleet-outcome YAML,
./scripts/validate-fleet-outcome.sh passes on each readiness doc.
```

Per-node swap at `docs` node:

```
/goal Mission doc-sync DONE: docs/doc-sync-progress.md all task flags true,
docs/doc-sync-readiness.md with fleet-outcome.status done and drift_open == 0,
all PRs merged into BASE.
```

## Validation chain

```bash
./scripts/validate-goal-condition.sh --ledger docs/fleet-program-progress.md
./scripts/validate-fleet-outcome.sh docs/doc-sync-readiness.md
./scripts/eval-campaign-edge.sh \
  --readiness docs/doc-sync-readiness.md \
  --campaign docs/composition-e2e-campaign.yaml \
  --current-node docs
```

## Headless replay (optional)

```bash
./scripts/run-mission-headless.sh grok fleet-program --max-turns 80
```

## Dual-truth check

| Check | File truth | Native goal |
|-------|------------|-------------|
| Campaign done | `PHASE: DONE` in ledger | `update_goal(completed: true)` only after file check |
| Node skip | `bugs` SKIPPED in Node status table | `UPDATE_GOAL` logged skip reason |
| Metrics | `fleet-outcome` YAML in readiness | Condition references same paths |

Native goal prevents early turn exit; ledger prevents false completion.