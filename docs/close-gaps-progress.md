# close-gaps progress (adversarial-review-and-fix dogfood vs the gap analysis)

PHASE: FIXING
MISSION: adversarial-review-and-fix (self, dogfood)   REPO: autonomous-fleet
BASE: ravidsrk/close-gaps (off ravidsrk/gap-analysis-doc = main + REVIEW_DOC)
REVIEW_DOC: docs/gap-analysis-genesis-prompts.md (FROZEN)   COORDINATOR: this Claude Code session
GREEN BASELINE: validate-all.sh PASS · pytest 188 passed (regression floor)
ROLES: builder = codex (codex exec — `--full-auto` is rejected by current codex; adapter fallback);
  fresh build-blind reviewer = the coordinator reviewing the diff only (cross-vendor to the codex
  build); integrator = coordinator. Builder and reviewer are never the same vendor on the same diff.

## HOT FILES (serialize: one in-flight task each)
engine.md · scripts/lib/fleet_outcome.py · skills/adversarial-review-and-fix/SKILL.md

## GAP CLOSE-INDEX (PARTIAL/MISSING + 4 verified-directly; CAPTURED 11 = DONE, do not touch)
WAVE 1 (P1)
- g-antiinflation-e2e   [P1 antiinflation] fleet_outcome.py + engine.md  | OPEN
- g-antiinflation-doctr [P1 antiinflation] engine.md invariant          | OPEN
- g-frozen-scope        [P1 frozenscope]   engine.md block              | OPEN
- g-wt-clean            [P1 cleanup]       engine.md + adapters         | OPEN
WAVE 2 (P2)
- g-three-lane          [P2 lanes] adversarial-review-and-fix/SKILL.md  | OPEN
- g-lane-b-draft        [P2 lanes] engine.md + adv-review               | OPEN
- g-lane-0-refuse       [P2 lanes] adv-review DECISION DEFAULTS         | OPEN
- g-rotate-before-scrub [P2 lanes] engine.md SECRET HYGIENE             | OPEN
- g-evid-flag           [P2 audit] adv-review per-fix EVID              | OPEN
- g-root-cause-cluster  [P2 audit] adv-review FOUNDATION/INDEP/touches  | OPEN
- g-regression-done     [P2 antiinflation] engine.md DONE-condition     | OPEN
- g-exercised-like-prod [P2 antiinflation] adv-review + engine default  | OPEN
- g-first-merge-check   [P2 audit] engine.md pipeline spot-check        | OPEN
- g-upgrade-maximal     [P2 missions] dependency-update/SKILL.md        | OPEN
- g-inference-cost      [P2 missions] NEW skills/inference-cost/SKILL.md + MISSION_METRICS | OPEN
WAVE 3 (P3)
- g-capability-boundary [P3 missions] take-product-to-completion/SKILL.md | OPEN
- g-reference-input     [P3 missions] engine.md SELF-ORIENTATION        | OPEN
- g-spike               [P3 missions] engine.md RESEARCH DISCIPLINE     | OPEN
- g-visual-baseline     [P3 missions] landing-page + design-integration | OPEN
- g-dup-block           [P3 cleanup] engine.md duplicate-block removal   | OPEN

## TASK ROWS
(none dispatched yet)

## DEFERRED (out-of-scope ideas noticed; frozen-scope rail — not built this run)
(none yet)
