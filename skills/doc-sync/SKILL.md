---
name: doc-sync
description: >-
  [Tier 1 · highest autonomous success ~0.92 merge · safe to run unattended] Bring a repo's
  documentation back into alignment with its actual code: README, docs/,
  AGENTS.md/CLAUDE.md, API references, setup/usage instructions, code comments that have
  drifted, and inline examples that no longer run. Use when docs are stale, after a refactor
  or dependency change, when onboarding docs are wrong, or for a periodic
  documentation-truth pass. This is a documentation mission ONLY — it does not change
  application behaviour or logic; it makes the docs match the code as it actually is. Runs
  fully autonomously via the autonomous-fleet-core engine. Trigger on: "sync the docs", "our
  README is out of date", "docs don't match the code", "update documentation", "fix
  onboarding/setup instructions", "documentation audit".
license: MIT
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "1"
  fleet-component: "mission"
---


# Mission: doc-sync

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — tool-agnostic coordinator engine
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, or `autonomous-fleet-adapter-grok`

Follow the core and your adapter in full, then apply the mission parameters below.

**Empirical note:** documentation is the single highest-success autonomous task category
(~0.92 merge rate across 33k real agent PRs). This mission is safe to run unattended.

## GOAL
Make the repository's documentation TRUE to its current code. Find every place docs and code
disagree and fix the DOCS (never bend the code to match stale docs). Scope includes: README,
everything under docs/, AGENTS.md / CLAUDE.md / CONTRIBUTING, API/reference docs, setup &
install & usage instructions, configuration docs, and code-level doc comments + inline examples
that have drifted or no longer run. Out of scope: any change to application behaviour, logic,
APIs, or tests' meaning. If a doc reveals an actual code bug, do NOT fix the code — record it in
DECISIONS.md as a finding for a separate mission.

## ROLE PIPELINE
- @claude AUDITS (finds drift) and WRITES the doc fixes.
- @codex REVIEWS each PR (fresh, build-blind): confirms the doc now matches the code, examples
  actually run, links resolve, nothing factually wrong remains.
- @claude is the INTEGRATOR: opens the PR, merges (conflict-aware), cleans the worktree.

## LEDGER
`docs/doc-sync-progress.md`. Per-task flags: `WRITTEN=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f>
MERGED=<t/f>`. Plus a DRIFT INDEX: every doc-vs-code discrepancy found in T-AUDIT, each `OPEN |
CLOSED via PR#n`.

## TASK STRUCTURE
- **T-AUDIT [@claude]** — read the code and the docs together; produce a complete DRIFT INDEX:
  every discrepancy with the doc location and the code truth it should reflect, grouped by doc
  area (README / setup / API / AGENTS.md / comments / examples). Also flag broken links, dead
  example commands, and instructions that no longer work. Output `docs/doc-sync-audit.md`.
  Independent — this is the only discovery task; freeze it, then fix.
- **T-FIX… [per doc area, loop]** — each doc area is one PR. @claude rewrites that area to match
  the code (run any example/command to verify it actually works) → @codex reviews the PR (doc
  matches code, examples run, links resolve) → @claude merges. Parallelize across non-overlapping
  doc files; serialize edits to the same file. Update the DRIFT INDEX as items close.
- **T-FINAL [@claude]** — verify every DRIFT-INDEX item is CLOSED, all example commands run,
  all internal links resolve, no stale instruction remains. Output `docs/doc-sync-readiness.md`
  (drift index all-closed + what was corrected + any code-bug findings deferred to other
  missions). Ship as the final PR.

## DONE
Every DRIFT-INDEX item `CLOSED`, every task `WRITTEN=t PR_OPEN=t REVIEWED=t MERGED=t`,
`docs/doc-sync-readiness.md` exists, all examples run and links resolve. Then send the FINAL
report.

## DECISION DEFAULTS (mission-specific; on top of the engine's)
- Fix the DOCS to match the code, never the code to match the docs. Code is ground truth.
- A doc that reveals a real code bug → record as a finding in DECISIONS.md, do NOT fix code here.
- Verify every example/command/snippet actually runs before claiming it correct.
- Preserve the docs' existing voice and structure; correct content, don't restyle gratuitously.
- Prefer many small per-area PRs (high merge success) over one sweeping docs PR.
- Any ambiguity → the wording that most accurately reflects what the code actually does.
