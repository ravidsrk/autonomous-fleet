---
name: doc-sync
description: >-
  [Tier 1 · highest cross-agent merge-success category (documentation) · safe to run unattended] Bring a repo's
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
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.2"
  tier: "1"
  fleet-component: "mission"
---

<!-- Corpus: prompts.md L2953-2964 (Stage 8 distillation, Tier 1 grouping at L2961 names doc-sync as run-unattended); see docs/doc-sync-readiness.md for the dogfood run. -->


# Mission: doc-sync

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

Activate only when the trigger applies. Do not load unrelated catalog skills.

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `skill-creator` | Editing or validating skills in the autonomous-fleet repo itself | Run `./scripts/validate-skills.sh` (framework clone only) |

## Worker skills

Inject per role on DISPATCH (workers load these; coordinator does not):

| Role | Skills | If unavailable |
|------|--------|----------------|
| @codex (write doc fixes) | — | Repo README + manifests only |
| @claude (audit, fresh review, integrator) | — | Repo README + manifests only |

## Deferred missions

Record in `docs/doc-sync-readiness.md` under **Recommended next missions** and in DECISIONS.md.
Do not start another mission in the same run.

| Finding type | Route to |
|--------------|----------|
| Code bug (doc reveals wrong behaviour) | `bug-batch` |
| Undertested area flagged during audit | `test-coverage` |
| Broken setup/deps (not doc wording) | `dependency-update` |

**Empirical note:** Documentation, CI, and build-update tasks show the highest merge-success
rate among AI-agent PRs (arXiv 2601.15195 — Ehsani et al., MSR 2026, AIDev dataset of ~33k PRs).
This mission is safe to run unattended.

## GOAL
Make the repository's documentation TRUE to its current code. Find every place docs and code
disagree and fix the DOCS (never bend the code to match stale docs). Scope includes: README,
everything under docs/, AGENTS.md / CLAUDE.md / CONTRIBUTING, API/reference docs, setup &
install & usage instructions, configuration docs, and code-level doc comments + inline examples
that have drifted or no longer run. Out of scope: any change to application behaviour, logic,
APIs, or tests' meaning. If a doc reveals an actual code bug, do NOT fix the code — record it in
DECISIONS.md as a finding for a separate mission.

## ROLE PIPELINE
- @claude AUDITS (finds drift) — the frozen DRIFT INDEX.
- @codex WRITES the doc fixes.
- A fresh build-blind @claude REVIEWS each PR: confirms the doc now matches the code, examples
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
- **T-FIX… [per doc area, loop]** — each doc area is one PR. @codex rewrites that area to match
  the code (run any example/command to verify it actually works) → fresh build-blind @claude reviews the PR (doc
  matches code, examples run, links resolve) → @claude merges. Parallelize across non-overlapping
  doc files; serialize edits to the same file. Update the DRIFT INDEX as items close.

  **PR sizing (issue #100 — the seam that decides spam vs blob):**
  - A "doc area" is one of: one top-level doc file (README, CONTRIBUTING, a
    single `docs/<file>.md`), one `docs/` subdirectory, one docs-site content
    section (e.g. one `docs-site/src/content/docs/<chapter>.md` — but if the
    site copy is GENERATED from `docs/`, fix the source and re-run the sync;
    never hand-edit the generated copy), or one code module's
    comments/docstrings. Group the frozen DRIFT INDEX rows by that unit.
  - Target diff ≤ ~400 changed lines per PR. An area whose rows exceed that:
    split by file. An area whose fix is < ~10 lines: MERGE it with another
    area touching the same file tree rather than opening a one-liner PR.
  - Never split one file across two PRs; never let one PR touch two areas
    whose rows could merge-conflict.
  - Worked example: DRIFT INDEX rows D-001..D-003 all in CONTRIBUTING.md →
    ONE PR "docs(CONTRIBUTING): …". Rows D-004..D-007 spread across four
    code files' comments → ONE PR "docs(comments): …" (all < 400 lines,
    disjoint files, one conceptual unit: comment truth). This is exactly the
    split the first external run used (gemoji#8/#9).

  **DRIFT INDEX row schema (frozen at T-AUDIT; the reviewer verifies against
  THESE columns):**

  | ID | Doc file:line | Doc says | Code truth | Fix area | State |
  |----|---------------|----------|------------------------|----------|-------|
  | D-001 | `CONTRIBUTING.md:11` | "Ruby 1.9+" | CI tests 2.7/3.0/3.1 (cite code file:line)  | contributing | OPEN → CLOSED via PR#n |
- **T-FINAL [@claude]** — verify every DRIFT-INDEX item is CLOSED, all example commands run,
  all internal links resolve, no stale instruction remains. Output `docs/doc-sync-readiness.md`
  starting with **`fleet-outcome` YAML** (`drift_open`, `code_bug_findings` in metrics; see
  `autonomous-fleet-core/references/fleet-outcome.md`), then drift summary + **Recommended next
  missions**. Ship as the final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/doc-sync-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission doc-sync DONE: docs/doc-sync-progress.md all task flags true,
docs/doc-sync-readiness.md with fleet-outcome.status done and mission metrics satisfied,
the readiness fleet-outcome validates (python3 <SUBSTRATE>/validate_fleet_outcome.py per the engine's SUBSTRATE RESOLUTION; skip recorded in the readiness doc when SUBSTRATE=none), all PRs merged into BASE.
```


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
