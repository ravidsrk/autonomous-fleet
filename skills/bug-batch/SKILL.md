---
name: bug-batch
description: >-
  [Tier 2 · moderate autonomy ~0.82 merge · full review gate · reproduce-first required]
  Close a batch of bugs — from a list, an issue tracker, or a described set — one PR per
  bug, each gated by a FAILING TEST written first that reproduces the bug, then a fix that
  turns it green. Use for a backlog of bugs, a tracker label, or a known cluster of defects.
  Bug-fixes are among the categories agents are WEAKEST at (they need exact, not
  approximate, changes), so this mission forces exactness: prove the bug with a red test
  before fixing. Does not add features. Runs via the autonomous-fleet-core engine. Trigger
  on: "fix these bugs", "work through the bug backlog", "close the bugs labelled X", "fix
  this list of issues", "batch bug fixing".
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
---

<!-- Corpus: prompts.md L2962 (Stage 8 Tier 2 grouping — "bug-batch (reproduce-first gate)"). -->


# Mission: bug-batch

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| — | — | — |

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @codex (repro test, fix) | — | Repo test conventions |
| @claude (review, integrator) | — | Mission review gate only |

## Deferred missions

Record in `docs/bug-batch-readiness.md` under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Fix reveals missing feature (not a bug) | `take-product-to-completion` or user-scoped mission |
| Root cause is architectural | `adversarial-review-and-fix` |
| Area lacks regression tests | `test-coverage` |

**Empirical note:** bug-fix tasks merge at ~0.82 and are among the two WEAKEST categories,
because success depends on EXACT (not approximate) code changes and on correctly localizing the
defect. The reproduce-first gate below is the specific countermeasure: a failing test that pins
the bug forces an exact fix and proves it landed. This gate is MANDATORY — it is the reason this
mission works.

## GOAL
Close every bug in the batch with a verified fix. The batch source is whatever the user supplies:
a list in the prompt, an issue tracker query/label, or a described cluster. For EACH bug:
reproduce it with a failing test, fix the root cause, prove the test now passes, and ensure no
regression elsewhere. One PR per bug. No feature work — if a "bug" is actually a feature request,
record it and skip.

## ROLE PIPELINE
- @claude triages the batch into a frozen BUG INDEX.
- @codex (per bug) writes the reproducing test + the fix.
- A fresh build-blind @claude REVIEWS each PR: the test genuinely reproduces the bug (fails
  WITHOUT the fix), the fix addresses root cause (not a symptom mask), no regression, scoped.
- @claude is the INTEGRATOR: opens PR, merges (conflict-aware), cleans worktree.

## LEDGER
`docs/bug-batch-progress.md`. Per-task flags: `REPRO=<t/f> FIXED=<t/f> PR_OPEN=<t/f>
REVIEWED=<t/f> MERGED=<t/f>`. Plus a BUG INDEX: each bug ID/description, `OPEN | FIXED via PR#n |
SKIPPED (reason)`.

## TASK STRUCTURE
- **T-TRIAGE [@claude]** — assemble the batch into a BUG INDEX (if the source is a tracker, pull
  the matching issues; cite IDs). For each: a one-line repro hypothesis and the suspected area.
  Separate real bugs from feature-requests-mislabelled-as-bugs (skip the latter, record why).
  Output `docs/bug-batch-triage.md`. Freeze the batch, then fix.
- **T-FIX… [per bug, loop — REPRODUCE-FIRST GATE]** — each bug is one PR, in strict order:
  1. **REPRODUCE**: write a test that FAILS because of the bug (red). Confirm it red. Set REPRO.
     If the bug can't be reproduced, mark the bug NEEDS-INFO in the index and move on — do NOT
     guess-fix an unreproduced bug.
  2. **FIX**: fix the root cause so the test goes green; run the full suite (no regression). Set
     FIXED.
  3. A fresh build-blind @claude reviews the PR — independently confirms the test fails without the
     fix and passes with it, the fix is root-cause not symptom, no regression → @claude merges.
  Parallelize bugs in non-overlapping files; serialize same-file (hot-file rule). Update the BUG
  INDEX.
- **T-FINAL [@claude]** — full suite green incl. every new reproducing test; walk the BUG INDEX,
  every bug `FIXED` or `SKIPPED/NEEDS-INFO` with reason. Output `docs/bug-batch-readiness.md`
  with **`fleet-outcome` YAML** (`bugs_open`, `bugs_skipped`), bug
  index resolution, the reproducing test per fix, skips/needs-info, all PRs). Ship as the final
  PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/bug-batch-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission bug-batch DONE: docs/bug-batch-progress.md all task flags true,
docs/bug-batch-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Every BUG-INDEX item `FIXED` (with its reproducing test) or explicitly `SKIPPED`/`NEEDS-INFO`,
every fixed task terminal, suite green, `docs/bug-batch-readiness.md` exists. Then send the FINAL
report.

## DECISION DEFAULTS (mission-specific)
- REPRODUCE-FIRST IS MANDATORY. No fix without a test that first fails because of the bug. An
  unreproduced bug is marked NEEDS-INFO, never guess-fixed.
- Fix ROOT CAUSE, not the symptom. A change that hides the symptom but leaves the cause is
  rejected.
- A "bug" that is actually a feature request → SKIP, record why; don't build features here.
- The reproducing test stays in the suite as a permanent regression guard.
- One PR per bug — never batch multiple bugs into one PR (keeps localization and review clean).
- Any ambiguity → reproduce it precisely first; let the failing test define exactly what "fixed"
  means.
