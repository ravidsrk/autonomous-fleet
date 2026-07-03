---
name: cleanup
description: >-
  [Tier 1 · merge-friendly chore-category work · lower-risk when scoped] Targeted
  code-health pass — remove dead code, kill duplication, fix a named anti-pattern, tidy
  structure — WITHOUT re-architecting. The light counterpart to legacy-rebuild: improves the
  code as it is, preserves all behaviour, no big structural change. Use for "clean up this
  mess", tech-debt paydown, removing cruft after a feature, or eliminating a specific smell.
  Behaviour-preserving by definition; every change covered by existing or added tests
  proving nothing broke. Runs fully autonomously via the autonomous-fleet-core engine.
  Trigger on: "clean up the code", "remove dead code", "reduce duplication", "tidy this up",
  "pay down tech debt", "fix this anti-pattern" (when a full rebuild is NOT wanted).
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "1"
  fleet-component: "mission"
status: exploratory
---

> **Status: exploratory.** This mission is documented but has not yet been run end-to-end on an external repo with an archived run-archive. It is preserved for future promotion (see `docs/exploratory/missions/README.md` § Promotion criteria). Do not invoke this skill in a production fleet until it has been promoted.


<!-- Corpus: prompts.md L2961 (Stage 8 Tier 1 grouping) + Stage-9 worktree-cleanup gate (prompts.md L2979 prose + prompt 21 at L2999) — cleanup-as-flag, not cleanup-as-prose. -->


# Mission: cleanup

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| Repo dead-code tooling | T-SCAN needs knip/ts-prune/etc. | Use grep, coverage, and linter output only |

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @codex (clean) | — | Repo linters + characterization tests |
| @claude (scan, fresh review, integrator) | — | Repo linters + characterization tests |

## Deferred missions

Record in `<LEDGER_DIR>/cleanup-readiness.md` under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Re-architecture / framework swap needed | `legacy-rebuild` |
| Bug exposed by deletion risk | `bug-batch` |
| Untested risky area | `test-coverage` first |

**Empirical note:** chore/refactor-light sits among the higher-merging cross-agent task
categories (chore ~84% in arXiv 2601.15195, Ehsani et al., MSR 2026) — lower-risk when scoped and
behaviour-preserving. There is no published category-level merge rate for this mission as scoped,
and per-task merge rates vary by agent, so treat the tier ordering as qualitative. The risk is
scope creep into a rewrite; this mission explicitly does NOT re-architect (that's legacy-rebuild).

## GOAL
Improve code health while preserving ALL behaviour: remove dead/unreachable code, eliminate
duplication (extract shared helpers), fix the specific anti-pattern(s) in scope, tidy structure
and naming, remove cruft. This is NOT a re-architecture — no framework changes, no new build
system, no sweeping structural redesign (if that's needed, this is the wrong mission — record it
and point to legacy-rebuild). Every change is behaviour-preserving and proven so by tests.

## ROLE PIPELINE
- @claude identifies cleanup targets (the frozen CLEANUP INDEX).
- @codex performs the changes.
- A fresh build-blind @claude REVIEWS each PR: behaviour-preserving (tests prove it), genuinely
  cleaner, scoped (no creeping rewrite), no functionality removed that was actually used.
- @claude is the INTEGRATOR: opens PR, merges (conflict-aware), cleans worktree.

## LEDGER
`<LEDGER_DIR>/cleanup-progress.md`. Per-task flags: `CLEANED=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f>
MERGED=<t/f>`. Plus a CLEANUP INDEX: each item (dead-code/duplication/anti-pattern/structure)
with location, `OPEN | DONE via PR#n`.

## TASK STRUCTURE
- **T-SCAN [@claude]** — scan for: dead/unreachable code (use the repo's tooling — knip,
  ts-prune, coverage, linters — where available), duplication, the named anti-pattern(s),
  structural/naming issues. Confirm what's truly unused (don't delete something reachable via
  reflection/dynamic import without checking). Output `docs/cleanup-scan.md` with a CLEANUP
  INDEX. Freeze, then clean.
- **T-CLEAN… [per item/area, loop]** — each coherent cleanup is one PR. @codex makes the
  behaviour-preserving change, ensures existing tests still pass (add a characterization test
  first if the area is untested and risky) → fresh build-blind @claude reviews (cleaner + behaviour intact + scoped)
  → @claude merges. Parallelize non-overlapping files; serialize same-file. Update the CLEANUP
  INDEX.
- **T-FINAL [@claude]** — build green, full suite green, no behaviour change, the targeted smells
  gone. Output `<LEDGER_DIR>/cleanup-readiness.md` with **`fleet-outcome` YAML** (`cleanup_items_open`),
  cleanup summary, **Recommended next missions**, all PRs. Ship as the final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `<LEDGER_DIR>/cleanup-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission cleanup DONE: <LEDGER_DIR>/cleanup-progress.md all task flags true,
<LEDGER_DIR>/cleanup-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Every CLEANUP-INDEX item `DONE`, every task terminal, suite green, behaviour preserved,
`<LEDGER_DIR>/cleanup-readiness.md` exists. Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)
- Behaviour-preserving ALWAYS. If a "cleanup" would change behaviour, it's not cleanup — stop and
  record it.
- Before deleting "dead" code, confirm it's truly unreachable (check dynamic/reflective/string
  references, public API surface, build entry points). When unsure, leave it and note it.
- Do NOT re-architect. No framework swap, no new build system, no structural redesign — that's
  legacy-rebuild. Record such needs and point there.
- For risky untested areas, add a characterization test capturing current behaviour BEFORE
  refactoring, so the test proves you preserved it.
- Prefer many small scoped PRs over one sweeping cleanup.
- Any ambiguity → the smaller, safer change that demonstrably preserves behaviour.
