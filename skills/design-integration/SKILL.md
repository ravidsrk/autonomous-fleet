---
name: design-integration
description: >-
  [Tier 2 · moderate autonomy · full review gate] Adopt a fresh design across an existing
  product to full parity — VISUAL and FEATURE-WISE. Import the design (Claude Design
  export/URL or the claude_design MCP connector), reskin every existing screen to it, and
  where the design implies a feature the product lacks, design-and-build it; nothing the old
  product did is lost. Use for a whole-app redesign adoption, not a single page (that's
  landing-page-convergence). Reuses the existing backend; rewires the UI to the new design
  and fills gaps to full depth. Runs via the autonomous-fleet-core engine. Trigger on:
  "adopt this design across the product", "integrate the new design end to end", "make the
  app match this design fully", "redesign the whole app to this".
license: MIT
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
---


# Mission: design-integration

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, or `autonomous-fleet-adapter-grok`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `claude_design` MCP | DESIGN SOURCE uses MCP connector | User must `/design-login` — HARD EXTERNAL DEPENDENCY |
| `gstack-design-review` | Post-build visual QA on key screens | Rely on @codex review gate only |

## Deferred missions

Record in `docs/parity-readiness.md` under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Scope is one landing page only | `landing-page-convergence` |
| Backend rewrite needed (not UI rewire) | `legacy-rebuild` |
| Bugs found during parity work | `bug-batch` |

**Empirical note:** UI/feature work spans ~0.80-0.81 merge — full review gate required, reviewing
both visual fidelity AND feature parity. The control artifact is the PARITY MAP: anything not
mapped there is a feature that silently disappears.

## DESIGN SOURCE (the user supplies one)
A Claude Design export/URL, OR the claude_design MCP connector
(https://api.anthropic.com/v1/design/mcp). If using the MCP connector and it isn't authorized:
this is a HARD EXTERNAL DEPENDENCY — tell the user to run /design-login (grants
user:design:read/write), then wait; that is the one allowed pause (an agent can't self-grant the
scope). Otherwise a worker fetches/imports the design and READS ITS README first.

## GOAL
Make the product match the design BOTH ways: (1) every existing screen/flow reskinned/rebuilt to
the new design — the old product's functionality is the FLOOR, nothing dropped; (2) every relevant
aspect of the design implemented; (3) where the design implies a feature the product lacks,
design-and-build it in the design's language to full depth. End state: the product looks and
behaves as the design, zero feature regressions, every flow working. No partial reskins, no
half-migrated screens reachable.

## ROLE PIPELINE
- @claude IMPORTS the design + PROBES the existing product + builds the PARITY MAP + thin per-area
  specs.
- @grok CODES each area to full depth (visual match + feature).
- @codex REVIEWS each PR (fresh, build-blind): design-faithful AND no lost functionality, all
  states, real tests, no placeholders/half-migrated screens.
- @claude SHIPS: opens PR, conflict-aware merge, worktree cleanup.

## LEDGER
`docs/parity-progress.md`. Per-task flags: `PLANNED=<t/f> BUILT=<t/f> REVIEWED=<t/f>
SHIPPED=<t/f>`. Plus a PARITY MATRIX: every item classified REDESIGN | GAP-FILL | NEW, each `OPEN
| DONE via PR#n`.

## TASK STRUCTURE
- **T-A1 DESIGN EXTRACTION [@claude]** — import the design (per DESIGN SOURCE; README first);
  extract the full system (tokens, components, layouts, states, responsive) + every screen.
  Output docs/design-extract.md.
- **T-A2 PRODUCT PROBE [@claude, parallel]** — inventory the existing product end to end (every
  screen, route, flow, feature, state) + relevant backend/API contracts. The no-loss FLOOR.
  Output docs/product-probe.md.
- **T-MAP PARITY MAP [@claude, Opus-class, gated on A1+A2] — control point.** Cross-map design vs
  product. Classify every item: REDESIGN (product has it; rebuild to design), GAP-FILL (product
  has it, design doesn't cover it; design-and-build to full depth), NEW (design introduces it;
  build it). NOTHING in the product left unmapped. Define build order, shared FOUNDATION
  (design-system) work, per-item acceptance (visual + feature + tests), placement hints. Output
  docs/parity-spec.md. FROZEN. Write each item to the PARITY MATRIX.
- **T-FOUNDATION [relay]** — implement the design SYSTEM (tokens/theme/typography/spacing/shared
  components) wired in, with tests. Gates the screens.
- **T-ITEMS… [per matrix item, loop]** — @claude thin-plans → @grok builds to full parity (visual
  + feature, all states, responsive, tests) → @codex reviews (fidelity + no lost functionality +
  tests) → @claude ships. Parallelize non-overlapping screens; serialize overlapping.
- **T-FINAL [@claude]** — build green, lint clean, full suite green. Every matrix item DONE; the
  product matches the design everywhere; every product-probe capability still works (zero
  regressions); no half-migrated screens/placeholders/console errors. Output
  docs/parity-readiness.md (matrix complete, test summary, residual risks, all PRs). Ship as the
  final PR.

## DONE
Every PARITY-MATRIX item `DONE`, every task `PLANNED=t BUILT=t REVIEWED=t SHIPPED=t`, product
matches design visually + feature-wise with zero regressions, docs/parity-readiness.md exists.
Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)
- The design is the visual/UX TARGET; the product's functionality is the FLOOR. Reach both — full
  fidelity AND zero feature loss.
- Where the design doesn't cover an existing feature: design-and-build it in the design's language
  to full depth (GAP-FILL). Never drop a feature because the design is silent on it.
- Reuse the existing backend/logic/data/API contracts; rewire the UI to the design — not an engine
  rewrite.
- The design export's README and exact token/spacing values are authoritative; match precisely.
- Real content/assets; no placeholders on shipping screens. Mobile-first/responsive + a11y basics.
- Tests real; reject coverage-padding. Any ambiguity → the most faithful, complete,
  regression-free parity while converging.
