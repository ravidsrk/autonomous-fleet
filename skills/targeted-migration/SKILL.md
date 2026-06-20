---
name: targeted-migration
description: >-
  [Tier 2 · moderate autonomy · full review gate] Migrate ONE axis of a codebase — a
  framework version, a library swap, a language/runtime bump, a database/ORM change, an
  API-version move — while preserving everything else and keeping the suite green. Use for a
  single deliberate migration that's too big for dependency-update but is NOT a full
  rebuild: React class→hooks, a major framework major-version, swapping one library for
  another, a DB engine/ORM change, a REST→GraphQL of one surface. Changes one axis;
  preserves architecture and behaviour on every other axis. Runs via the
  autonomous-fleet-core engine. Trigger on: "migrate to X", "swap library A for B", "upgrade
  framework to v-next", "move from REST to GraphQL", "migrate the database/ORM".
license: MIT
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
---


# Mission: targeted-migration

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code``, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program` (see `migrate-safe` preset).

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| — | — | — |

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @grok (migrate) | Stack skill matching repo if installed (`nextjs`, `wrangler`, etc.) | Target framework docs + migration guide |

## Deferred missions

Record in `docs/migration-readiness.md` under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Full rebuild required (multi-axis) | `legacy-rebuild` |
| Pre-migration test gap | `test-coverage` (often prior program step) |
| Migration docs / setup instructions | `doc-sync` |

**Empirical note:** No matching task category in arXiv 2601.15195 — full review gate required. The
discipline that makes it converge: change ONE axis, hold everything else constant, and migrate
incrementally behind a green suite rather than big-bang.

## GOAL
Migrate the single named axis end to end — every usage moved to the new framework/library/runtime/
DB/API — while behaviour and all other architecture stay identical and the suite stays green. NOT
a rebuild: only the target axis changes; the rest of the system is preserved exactly. Incremental
and shippable per PR; at every merge the app builds and tests pass.

## ROLE PIPELINE
- @claude plans the migration (inventory all usages, sequence, compatibility strategy) and codes
  each increment.
- @codex REVIEWS each PR (fresh, build-blind): correctly migrated to the new axis, behaviour
  identical, nothing else changed, suite green, no half-migrated state left reachable.
- @claude is the INTEGRATOR: opens PR, merges (conflict-aware), cleans worktree.

## LEDGER
`docs/migration-progress.md`. Per-task flags: `MIGRATED=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f>
MERGED=<t/f>`. Plus a MIGRATION INDEX: every usage-site/module to move, `OPEN | DONE via PR#n`,
and the compatibility/cutover strategy.

## TASK STRUCTURE
- **T-PLAN [@claude, Opus-class]** — inventory EVERY usage of the old axis; define the target and
  the migration strategy (can old and new coexist during migration via an adapter/shim, or is it
  a hard cutover?); sequence the modules; identify a characterization-test safety net for
  behaviour. Output `docs/migration-plan.md` with a MIGRATION INDEX. FROZEN — increments conform.
- **T-FOUNDATION [@claude, if needed]** — establish the new axis alongside the old (install, base
  config, any adapter/shim that lets modules migrate incrementally). Gates the per-module work.
- **T-MIGRATE… [per module/usage-group, loop]** — each is one PR. @claude migrates that slice to
  the new axis, preserves behaviour (characterization tests prove it), suite green → @codex
  reviews (correct migration, behaviour identical, nothing else touched) → @claude merges.
  Parallelize independent modules; serialize shared ones. Update the MIGRATION INDEX.
- **T-CLEANUP [@claude]** — once every usage is migrated, remove the old axis (dependency,
  adapter/shim, dead compatibility code). Confirm nothing references it.
- **T-FINAL [@claude]** — build green, full suite green, the old axis fully gone, no
  half-migrated state. Output `docs/migration-readiness.md` with **`fleet-outcome` YAML**
  (`migration_items_open`, `old_axis_removed`), migration index done, old axis
  removed, behaviour preserved, all PRs). Ship as the final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/migration-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission targeted-migration DONE: docs/migration-progress.md all task flags true,
docs/migration-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Every MIGRATION-INDEX item `DONE`, old axis removed, every task terminal, suite green,
`docs/migration-readiness.md` exists. Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)
- Change ONLY the target axis. Any change to other architecture or behaviour is out of scope —
  record it, don't do it here.
- Prefer an incremental coexistence strategy (adapter/shim, both versions during migration) over
  a risky big-bang cutover, when the axis allows it.
- Add characterization tests for behaviour BEFORE migrating a slice, so the test proves behaviour
  is preserved across the move.
- Remove the old axis only after ALL usages are migrated and verified; never leave a
  half-migrated reachable state at the end.
- Suite green at every merge; never merge a half-migrated red state.
- Any ambiguity → the migration path that preserves behaviour most provably while keeping the
  suite green throughout.
