---
name: take-product-to-completion
description: >-
  [Tier 3 · high blast radius · expect rework · run deliberately, review the scope artifact]
  Take a STALLED product to a full-fledged, complete, shippable state — adversarial review
  of what exists, research the market, freeze a COHERENT PRODUCT BOUNDARY, then build
  everything inside it to full depth (no stubs, no half-built screens) and rebuild the
  landing page. Use when a product has been started but never finished, when "done" keeps
  expanding so nothing ships, or when you need a side project driven to a credible v1. NOT
  for a thin MVP — the user wants real depth — but the boundary is frozen once so the run
  converges instead of expanding forever. Highest-risk mission: feature/cross-module work
  has no category in arXiv 2601.15195, so expect rework; the scope artifact (the
  IN/ROADMAP/FIX boundary) is the thing to eyeball. Runs via the autonomous-fleet-core
  engine. Trigger on: "take this product to the finish line", "finish this stalled project",
  "make this shippable end to end", "complete the whole product".
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "3"
  fleet-component: "mission"
status: exploratory
---

> **Status: exploratory.** This mission is documented but has not yet been run end-to-end on an external repo with an archived run-archive. It is preserved for future promotion (see `docs/exploratory/missions/README.md` § Promotion criteria). Do not invoke this skill in a production fleet until it has been promoted.


<!-- Corpus: prompts.md L2963 (Stage 8 Tier 3 grouping) + Stages 4-5 (prompts 9-12 at L788-L1488: ship-v1, product-completion, handoff triad, autonomy enforcement) + Stage-9 prompt 24 "Aula Completion-for-Real" at prompts.md L3011-L3013 (final-form role topology). -->


# Mission: take-product-to-completion

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. ROADMAP items defer to future runs or `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `office-hours` | Boundary (T3) is ambiguous and user wants product framing | Use T1+T2 research only |

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (plan, T1 review, T3 boundary) | — | Mission gates T1–T3 |
| @codex (build areas, landing) | `frontend-design` | Completion boundary + per-area specs |
| @claude (fresh build-blind reviewer) | — | Mission review gate only |
| @claude (integrator / ship) | — | Mission ship gate only |

Stage-9 final form (Aula prompt 24, prompts.md L3013): @grok retired. @codex builds; a fresh
build-blind @claude reviews each fix PR (different terminal session than the planner/integrator
@claude); @claude integrates. The cross-vendor reviewer rule still holds — the reviewer must not
have seen the build conversation, and is handed the diff + acceptance contract as TEXT ONLY.

## Deferred missions

ROADMAP list in boundary doc + **Recommended next missions** in `docs/completion-readiness.md`.

| Finding type | Route to |
|--------------|----------|
| ROADMAP feature (explicit future scope) | User picks mission on next run |
| Deep security hardening beyond FIX list | `adversarial-review-and-fix` |
| Legacy stack blocks completion | `legacy-rebuild` |

**Empirical note:** this is the highest-blast-radius mission. Feature and cross-module work has
no direct category in arXiv 2601.15195 — Ehsani et al., MSR 2026, AIDev dataset of ~33k PRs (where
documentation, CI, and build-update tasks show the highest merge-success rate among AI-agent PRs),
and broad autonomous runs thrash when they fail. The single control that matters is the FROZEN
BOUNDARY in T3 — review that artifact. Everything downstream inherits it.

## CORE TENSION (read first)
"Finish the whole product" is unbounded and is exactly why it never ships. The fix is NOT a thin
MVP — build to real depth, zero stubs — but define a COHERENT PRODUCT BOUNDARY ONCE, then
complete everything inside it and STOP, rather than letting the boundary expand. Inside the
boundary: nothing thin, nothing stubbed, everything works end to end and is polished. Outside:
an honest post-v1 roadmap, deferred deliberately, not pretended away.

## GOAL
Turn the stalled product into a complete, professional, shippable product: every IN-scope
feature fully implemented to real depth, the critical path (signup → core value) working end to
end, the landing page rebuilt to the positioning, zero feature regressions, real content
everywhere. "A customer would pay for this and call it finished" — not "it demos."

## ROLE PIPELINE
Stage-9 final form (Aula prompt 24, prompts.md L3013):
- @claude PROBES + PLANS (adversarial review, research, the frozen boundary, per-area specs).
- @codex CODES each area to full depth.
- A FRESH BUILD-BLIND @claude REVIEWS each PR (different terminal session than the planner;
  cross-vendor reviewer rule; handed diff + acceptance contract as TEXT ONLY): genuinely complete
  + full-depth, real tests, no stubs/placeholders, nothing IN thinned, nothing out-of-boundary
  added, no regressions.
- @claude SHIPS: opens PR, merges (conflict-aware), cleans worktree.

## LEDGER
`docs/completion-progress.md`. Per-task flags: `PLANNED=<t/f> BUILT=<t/f> REVIEWED=<t/f>
SHIPPED=<t/f>`. Plus the frozen SCOPE INDEX (every IN + FIX item, each `OPEN | DONE via PR#n`)
and a ROADMAP list (deferred, never built this run).

## TASK STRUCTURE
- **T1 ADVERSARIAL REVIEW [@claude]** — hostile audit of the current product: every route,
  screen, flow, feature with honest status (works/half-built/broken/stub/dead); trace the
  critical path and find exactly where it breaks; dead ends, placeholder UI, missing flows,
  auth/billing/onboarding gaps. Output `docs/completion-review.md`. (Parallel with T2.)
- **T2 MARKET RESEARCH [@claude]** — competitors, table-stakes features a credible full product
  in this category ships, current best-practice UX, what "complete and professional" looks like
  here today. Fetch live sources. Separate must-have-for-a-complete-product from genuine future
  scope. Output `docs/completion-research.md`. (Parallel with T1.)
- **T3 BOUNDARY + PLAN [@claude, Opus-class, gated on T1+T2] — MOST IMPORTANT, the control
  point.** Define the COHERENT BOUNDARY (informed by T2). Three lists: **IN** (every feature
  belonging in the full product — generous and complete, a real product not a skeleton, each
  built to full depth no stubs); **ROADMAP** (genuine future scope, deferred with reasoning —
  the boundary, NOT core things smuggled out to ship less); **FIX** (existing broken/half-built/
  stubbed things to repair). Test for the boundary: would a paying customer call this complete
  and professional — DONE, not "early"? Missing → reads half-baked → IN; only power-users-at-
  scale want it → ROADMAP. Then a positioning-led landing-page rebuild brief and a full app
  UI/UX plan covering every IN flow. Output `docs/completion-boundary.md`. FROZEN: build
  everything IN and FIX to full depth; the boundary does NOT expand mid-build (new ideas →
  ROADMAP in DECISIONS.md); nothing IN may be thinned. Write every IN/FIX item to the SCOPE
  INDEX. **CAPABILITY-BOUNDARY rail:** if a root blocker is a capability the fleet cannot
  conjure (missing AI engine, unavailable external API, credential the fleet must not handle),
  surface `CAPABILITY_BOUNDARY:<name>` as a named human decision in `DECISIONS.md`. Split
  the boundary into `BUILDABLE_NOW` vs `BLOCKED_ON_<boundary>`; build the buildable side fully,
  leave the blocked side named and unclaimed, and do not report DONE around it. This artifact is
  what the user should review.
- **T4 CRITICAL PATH [@codex build, fresh @claude review, gated on T3]** — make signup → core value work end to end;
  fix FIX-list items blocking the primary flow. Must work fully before cosmetic polish.
- **T5 LANDING PAGE [@codex build, fresh @claude review, gated on T3; parallel to T4 if non-overlapping]** — rebuild
  to the brief: positioning-led, conversion-oriented, fully responsive, real copy, no
  placeholders.
- **T6…Tn PER IN-AREA [loop, gated on T4]** — @codex builds each area to FULL DEPTH (complete,
  all loading/empty/error/edge states, polished, with tests) → fresh build-blind @claude reviews (complete +
  full-depth + tests real + nothing thinned/out-of-boundary + no regressions) → @claude ships.
  Parallelize non-overlapping areas; serialize overlapping ones.
- **T_POLISH [@claude]** — whole-product consistency pass: no broken links, no console errors,
  no reachable half-built screens, coherent visual language. New ideas → ROADMAP.
- **T_FINAL [@claude]** — build green, lint clean, full suite green. Walk the product as a new
  user end to end, zero dead ends; confirm every IN item fully implemented (zero stubs), every
  prior capability still works, ROADMAP is honest future scope.
  **RESULT-STATE TERMINATION GATE (engine: `engine.md` → RESULT-STATE TERMINATION GATE).** Green
  CI ≠ done. Walk the product as a new user end to end, then QUERY THE ACTUAL RESULT STATE —
  direct DB queries, API responses, on-chain state, audit rows — to confirm the action HAPPENED.
  Example from the Aula run (prompts.md L3013): approving an item in the UI must produce
  (a) approved-count incremented, (b) non-zero `api_cost` recorded, (c) audit row written. Exit
  codes don't prove this; querying the DB does. The `e2e_verified` readiness flag means the
  result-state query passed, not that the test suite was green. Output
  `docs/completion-readiness.md` with **`fleet-outcome` YAML** (`in_items_open`, `roadmap_count`,
  `stubs_remaining`), scope/roadmap summary, **Recommended next missions**, all PRs. Ship as the
  final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/completion-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission take-product-to-completion DONE: docs/completion-progress.md all task flags true,
docs/completion-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Every SCOPE-INDEX item `DONE`, every task `PLANNED=t BUILT=t REVIEWED=t SHIPPED=t`,
`docs/completion-readiness.md` exists, the product works end to end with zero stubs/dead ends.
Then send the FINAL report.

## DECISION DEFAULTS (mission-specific; on top of the engine's)
- When tempted to WIDEN the boundary mid-build: DON'T — record in ROADMAP. NOT license to thin
  what's IN. Every IN feature is built to full depth. "Don't expand the boundary," never "ship
  less of what's inside it."
- Research shows a feature is part of a credible full product here → IN, built completely. Only
  genuine future/advanced scope → ROADMAP.
- Reuse the existing backend/logic/data/API contracts; complete and wire them, don't rewrite.
- Prefer finishing an existing half-built flow over starting a new one — but finish it fully.
- Real content/assets everywhere; no lorem ipsum, no placeholders on shipping surfaces.
- Tests real and behaviour-exercising; reject coverage-padding. Bar = every feature/flow tested
  and green; coverage not regressed.
- Mobile-first / fully responsive and a11y basics across all screens.
- Capability boundary is not roadmap and not failure theater. If the product needs an AI engine,
  unavailable external API, human-held credential, or similar capability the fleet cannot conjure,
  name the human decision in `DECISIONS.md`, split buildable-now from
  `blocked-on-<boundary>`, and keep the final outcome blocked until the boundary is resolved.
- Any other ambiguity → the option that yields the most complete, professional product while
  still converging.
