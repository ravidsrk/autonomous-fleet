---
name: landing-page-convergence
description: >-
  [Tier 2 · moderate autonomy · full review gate] Force a production landing page that has
  DIVERGED from an approved design into full fidelity with that design - section by section,
  with a named divergence checklist as the forcing function so it converges instead of
  drifting. Use when a live page no longer matches its design export and needs to be brought
  back into line (a single page/site, not a whole app - that's design-integration). Extracts
  the design system, diffs production against it, and closes each divergence as its own PR.
  Runs via the autonomous-fleet-core engine. Trigger on: "make the landing page match the
  design", "the production page diverged from the design", "bring the landing page into
  parity", "fix the landing page to match the mockup".
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
---


# Mission: landing-page-convergence

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` - read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `qa-only` | Production/staging URL; report-only before final section PR | Screenshot + @codex review only |
| `browse` | Coordinator spot-checks live page between sections | Screenshot + manual diff |

Community catalog: `autonomous-fleet-core` → `references/community-skills.md`.

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude / @grok (build sections) | `frontend-design`, `frontend-ui-engineering` | Design extract values exactly |
| @grok (section QA) | `qa` when URL available and fix-verify loop requested | Fidelity gate per section |
| @codex (review) | - | Mission fidelity gate |

## Deferred missions

Record in final readiness doc under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Whole app must match design | `design-integration` |
| Copy/positioning strategy undefined | `take-product-to-completion` (boundary pass) |

**Empirical note:** No matching task category in arXiv 2601.15195 - full review gate. The thing that
makes it converge rather than drift is a NAMED DIVERGENCE CHECKLIST that is part of the
termination condition: the run isn't done until every listed divergence is closed, and each PR
declares which divergence it closes.

## DESIGN SOURCE (the user supplies one)
A Claude Design export/URL or design file. A worker fetches/opens it and READS ITS README first,
then extracts the EXACT design system. This export's values are authoritative - match precisely,
don't approximate.

## DIVERGENCE CHECKLIST (the forcing function)
If the user names specific divergences, transcribe them as D1..Dn - these are the floor. T2 (the
production diff) confirms/details each AND surfaces any additional divergences (add as new
D-items). Each D-item is a FIX the build must close and the reviewer must verify against the
design export. The run terminates only when every D-item is CLOSED.

## GOAL
Bring the production landing page to full fidelity with the design export - same composition, type
scale, spacing rhythm, sections, component treatment. The design is the TARGET; production
changes. Converge, do not reinterpret or "improve on" the design. Keep existing copy and working
links/CTAs unless the design's section structure requires content the page lacks (then build it to
match the design).

## ROLE PIPELINE
- @claude EXTRACTS the design + DIFFS production + rebuilds each section.
- @codex REVIEWS each PR (fresh, build-blind): matches the design export
  (tokens/spacing/type/layout), the claimed D-item is actually closed, responsive, no
  placeholders.
- @claude is the INTEGRATOR: opens PR, conflict-aware merge, worktree cleanup.

## LEDGER
`docs/landing-progress.md`. Per-task flags: `BUILT=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f>
MERGED=<t/f>`. Plus the DIVERGENCE CHECKLIST D1..Dn, each `OPEN | CLOSED via PR#n`.

## VISUAL BASELINE (before/after gate)
T2 records the exact baseline capture commands/queries that produced the before-state
screenshots in `docs/landing-diff.md` and `docs/landing-progress.md`: command line or browser
query, URL/route, viewport/device, auth/seed state, screenshot path, and covered section/D-item.
T-FINAL replays those commands/queries like-for-like after all PRs merge, captures after-state
screenshots to parallel paths, and writes an explicit before/after comparison in
`docs/landing-readiness.md`. Passing requires strict visual improvement toward the design for each
covered D-item. Screenshot existence alone is not evidence. If a baseline cannot be replayed, the
covered D-item stays `OPEN` until a replayable baseline exists and passes.

## TASK STRUCTURE
- **T1 DESIGN EXTRACTION [@claude]** - fetch/open the design export (README first); extract the
  EXACT system (tokens color/type/spacing/radii, component styles, type scale + weights, spacing
  rhythm, section-by-section layout). Output docs/design-extract.md + place assets.
- **T2 PRODUCTION DIFF [@claude, gated on T1]** - diff the current production page section by
  section against docs/design-extract.md; confirm and detail each known D-item with the exact
  production files responsible; surface any additional divergences (add as D-items). Output
  docs/landing-diff.md. Record VISUAL BASELINE capture commands/queries and write the full
  checklist to the ledger.
- **T-CONVERGE… [per section/D-item, loop]** - each is one PR. @claude rebuilds that section to
  MATCH the design exactly (correct tokens, spacing, type, layout, component treatment), closing
  its D-item(s), responsive, real content → @codex reviews (fidelity + D-item closed + responsive)
  → @claude merges. Do global-craft items (tokens/type scale/spacing rhythm/eyebrow labels) FIRST
  as a foundation pass so per-section fixes inherit them. Parallelize non-overlapping sections;
  serialize same-file. Update D-item close-status.
- **T-FINAL [@claude]** - build green, lint clean. Walk the page across mobile/tablet/desktop;
  EVERY D-item CLOSED; matches docs/design-extract.md in tokens/spacing/type/layout/section
  structure; fully responsive; no placeholders/dead links/console errors. Replay VISUAL BASELINE
  commands/queries and include the strict before/after comparison. Output `docs/landing-readiness.md`
  with **`fleet-outcome` YAML** (`divergences_open`), D-item summary, **Recommended next
  missions**, all PRs. Ship as the final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/landing-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission landing-page-convergence DONE: docs/landing-progress.md all task flags true,
docs/landing-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Every D-item `CLOSED`, every task `BUILT=t PR_OPEN=t REVIEWED=t MERGED=t`, page matches the design
export, replayed VISUAL BASELINE confirms strict improvement, docs/landing-readiness.md exists.
Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)
- The design export is the TARGET; production changes to match. Converge, don't reinterpret or
  "improve."
- The export's exact token/spacing/type values are authoritative; match precisely, don't
  approximate.
- Keep existing copy and working links/CTAs UNLESS the design's structure requires content the
  page lacks (then build it to match the design).
- Close global-craft items (tokens, type scale, spacing rhythm, eyebrow labels) early so
  per-section fixes inherit them.
- Real content/assets; no placeholders on the shipping page. Mobile-first/responsive + a11y.
- Any ambiguity → the closest fidelity to the design export while converging.
