# close-gaps progress (adversarial-review-and-fix dogfood vs the gap analysis)

PHASE: FIXING
MISSION: adversarial-review-and-fix (self, dogfood)   REPO: autonomous-fleet
BASE: ravidsrk/close-gaps (off ravidsrk/gap-analysis-doc = main + REVIEW_DOC)
REVIEW_DOC: docs/gap-analysis-genesis-prompts.md (FROZEN)   COORDINATOR: this Claude Code session
GREEN BASELINE: validate-all.sh PASS · pytest 188 -> 205 passed (WAVE1+2; +e2e, engine-discipline, advreview-lanes, inference-cost tests)
ROLES: builder = codex (codex exec — `--full-auto` is rejected by current codex; adapter fallback);
  fresh build-blind reviewer = the coordinator reviewing the diff only (cross-vendor to the codex
  build); integrator = coordinator. Builder and reviewer are never the same vendor on the same diff.

## HOT FILES (serialize: one in-flight task each)
engine.md · scripts/lib/fleet_outcome.py · skills/adversarial-review-and-fix/SKILL.md

## GAP CLOSE-INDEX (PARTIAL/MISSING + 4 verified-directly; CAPTURED 11 = DONE, do not touch)
WAVE 1 (P1)
- g-antiinflation-e2e   [P1 antiinflation] fleet_outcome.py             | CLOSED via merge 5eff10e (e2e gate; non-inert proven)
- g-antiinflation-doctr [P1 antiinflation] engine.md invariant          | CLOSED via merge 8c3f103
- g-frozen-scope        [P1 frozenscope]   engine.md block              | CLOSED via merge 8c3f103
- g-wt-clean            [P1 cleanup]       engine.md (tracked gate)     | CLOSED via merge 8c3f103 (adapter notes -> WAVE2)
WAVE 2 (P2)
- g-three-lane          [P2 lanes] adversarial-review-and-fix/SKILL.md  | CLOSED (WAVE2 -> BASE)
- g-lane-b-draft        [P2 lanes] engine.md + adv-review               | CLOSED (WAVE2 -> BASE)
- g-lane-0-refuse       [P2 lanes] adv-review DECISION DEFAULTS         | CLOSED (WAVE2 -> BASE)
- g-rotate-before-scrub [P2 lanes] engine.md SECRET HYGIENE             | CLOSED (WAVE2 -> BASE)
- g-evid-flag           [P2 audit] adv-review per-fix EVID              | CLOSED (WAVE2 -> BASE)
- g-root-cause-cluster  [P2 audit] adv-review FOUNDATION/INDEP/touches  | CLOSED (WAVE2 -> BASE)
- g-regression-done     [P2 antiinflation] engine.md DONE-condition     | CLOSED (WAVE2 -> BASE)
- g-exercised-like-prod [P2 antiinflation] adv-review + engine default  | CLOSED (WAVE2 -> BASE)
- g-first-merge-check   [P2 audit] engine.md pipeline spot-check        | CLOSED (WAVE2 -> BASE)
- g-upgrade-maximal     [P2 missions] dependency-update/SKILL.md        | CLOSED (WAVE2 -> BASE)
- g-inference-cost      [P2 missions] NEW skills/inference-cost/SKILL.md + MISSION_METRICS | CLOSED (WAVE2 -> BASE)
WAVE 3 (P3)
- g-capability-boundary [P3 missions] take-product-to-completion/SKILL.md | OPEN
- g-reference-input     [P3 missions] engine.md SELF-ORIENTATION        | OPEN
- g-spike               [P3 missions] engine.md RESEARCH DISCIPLINE     | OPEN
- g-visual-baseline     [P3 missions] landing-page + design-integration | OPEN
- g-dup-block           [P3 cleanup] engine.md duplicate-block removal   | OPEN

## TASK ROWS
TASK cg-e2e-verified | PRI=P1 | THEME=antiinflation | FILE=hot(fleet_outcome.py) | CLOSES=[g-antiinflation-e2e] | BUILT=t PR_OPEN=t REVIEWED=t MERGED=t ACCEPT=t WT_CLEAN=t | MERGE=5eff10e | WT=removed | WORKER=codex | NOTE=reviewed build-blind cross-vendor; neutering gate fails test_e2e_gate (non-inert)

FIRST-MERGE SPOT-CHECK (5eff10e): PASS — author=Ravindra Kumar, 1/1 commits preserved (--no-ff), no trailers, branch deleted. Later waves unblocked.

## DEFERRED (out-of-scope ideas noticed; frozen-scope rail — not built this run)
(none yet)

## TASK ROW (wave 1 cont.)
TASK cg-engine-p1b | PRI=P1 | THEME=antiinflation/frozenscope/cleanup | FILE=hot(engine.md) | CLOSES=[g-antiinflation-doctr,g-frozen-scope,g-wt-clean] | BUILT=t PR_OPEN=t REVIEWED=t MERGED=t ACCEPT=t WT_CLEAN=t | MERGE=8c3f103 | WT=removed | WORKER=codex | NOTE=FROZEN-SCOPE RAIL FIRED: codex's build re-implemented the e2e metric out-of-scope (stale base + spec mention); review DROPPED it, kept only engine.md + test_engine_disciplines.py. Structural test proven non-inert.

═══════════════════════════════════════════════════════════
CONTEXT HANDOFF — WAVE 1 (P1) DONE; a fresh coordinator resumes at WAVE 2.
═══════════════════════════════════════════════════════════
PHASE=FIXING. BASE=ravidsrk/close-gaps @ 8c3f103 (off ravidsrk/gap-analysis-doc = main + REVIEW_DOC).
Green line: validate-all PASS, pytest 195. Worktrees CLEAN (only sibling main + new-research). No
open branches/PRs. REVIEW_DOC=docs/gap-analysis-genesis-prompts.md (frozen). Ledger=this file.
DONE so far (CLOSED in BASE): the 4 P1 gaps — g-antiinflation-e2e (5eff10e: e2e_verified gate +
test_e2e_gate.py, proven non-inert), g-antiinflation-doctr + g-frozen-scope + g-wt-clean (8c3f103:
engine.md banners + test_engine_disciplines.py). First-merge spot-check PASS.
NEXT = WAVE 2 (P2), then WAVE 3 (P3) — both still OPEN in the close-index above. Resume the same
pipeline: codex builds in a worktree off BASE (per the hot-file map) -> cross-vendor build-blind
review (NEUTER-THE-MECHANISM check: a new test must FAIL if the mechanism is removed; reject
tautologies + scope creep, as caught above) -> --no-ff merge into BASE -> WT_CLEAN -> ledger.
HOT-FILE SERIALIZATION (one in-flight each): engine.md (g-lane-b-draft, g-rotate-before-scrub,
g-regression-done, g-reference-input, g-spike, g-dup-block); adversarial-review-and-fix/SKILL.md
(g-three-lane, g-lane-0-refuse, g-evid-flag, g-root-cause-cluster, g-exercised-like-prod); the rest
are independent files (dependency-update, take-product-to-completion, landing-page/design-integration,
NEW skills/inference-cost). g-first-merge-check is ALREADY PRACTISED (recorded above) — close it by
adding the spot-check rail to engine.md's pipeline in the engine.md WAVE-2 batch.
T_FINAL (after all waves): RUN THE RAILS (feed fleet_outcome a done completion missing e2e -> rejected;
planted-bad input -> validators FAIL; worktree sweep -> no orphans), write docs/close-gaps-readiness.md,
mark human-owned follow-ups (BASE->main, npx skills republish) NOT done.
