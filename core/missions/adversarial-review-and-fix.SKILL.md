---
name: adversarial-review-and-fix
description: >-
  [Tier 2 · moderate autonomy · full review gate · the proven two-phase workhorse] Run a rigorous
  CODE-GROUNDED adversarial architecture review of a repo, FREEZE it as the source of truth, then
  close every confirmed finding one at a time until done. Use for a security/architecture/
  reliability hardening pass, a pre-production audit-and-remediate, or "review the whole app and
  fix everything." Phase 0 reviews the actual source (not existing docs) and a skeptic narrows
  out false findings; Phase 1 fixes the confirmed set with full safety rails. Runs via the
  autonomous-fleet-core engine. Trigger on: "adversarial review and fix", "audit and
  remediate", "review the whole app and fix the issues", "harden this before production", "find
  and fix the architecture problems".
---

# Mission: adversarial-review-and-fix

Apply the **autonomous-fleet-core** engine on your active adapter (load the core; load your runtime adapter; follow all core machinery) with the
parameters below.

**Empirical note:** this mission's fixes span fix/refactor/security work (~0.80-0.82 merge) — the
full review gate is essential. The structural key is that Phase 0 produces a FROZEN, richly-shaped
review BEFORE any fixing begins, so Phase 1 executes against a finished spec rather than judging
and fixing in one loop. The skeptic pass prevents fixing phantom findings.

## CORE PRINCIPLE
The review is a frozen external artifact in the exact shape the fix-loop consumes. Phase 0's job
is not "find problems" — it's "produce a review document that is ranked, dependency-ordered, with
per-finding Fix + acceptance + which in-tree primitive to reuse, CODE vs CODE+OPS tagged, plus a
hot-file collision map and a validated-strengths do-not-touch list, with a skeptic-narrowed
confirmed/refuted split." Phase 1 then runs the engine's PR-per-task pipeline keyed off the
confirmed findings.

## FRESH-RUN NOTE
If prior review docs / in-flight review branches exist, they are OUT OF SCOPE: don't read, reuse,
or overwrite them; write fresh outputs (docs/adversarial-review-fresh.md); branch BASE off the
default branch at current HEAD; don't disturb sibling worktrees. The review is grounded in the
CODE, not in any existing doc.

## GOAL
Find and CLOSE the real architecture/reliability/security/data/coupling/cost/ops/version issues in
the repo. "CLOSED" = the Fix is implemented, a test exists where the Fix calls for one, and
acceptance is demonstrated on staging/testnet/fixtures. Converge to the confirmed Fixes; never
reinterpret beyond them; never fix a refuted non-issue.

## ROLE PIPELINE
- PHASE 0: @claude REVIEWER produces findings FROM THE CODE → @codex SKEPTIC narrows/refutes
  AGAINST THE CODE → freeze.
- PHASE 1: @grok CODES each fix; @codex is the FRESH BUILD-BLIND reviewer of each fix PR; @claude
  is the INTEGRATOR (opens PR, conflict-aware merge, worktree cleanup). @grok never reviews its
  own work; @codex never writes code; @claude never authors fixes.

## LEDGER
`docs/arch-build-progress.md`. PHASE marker (REVIEW | REVIEW_FROZEN | FIXING | VERIFY); a FINDING
CLOSE-INDEX (every confirmed ID by wave: `OPEN | CLOSED via PR#n | CODE_CLOSED via PR#n (OPS:
…)`); per-fix-task rows with flags `CODED PR_OPEN REVIEWED MERGED ACCEPT`; an OPS/VERIFY-AT-SCALE
list + recorded decisions.

## TASK STRUCTURE
- **P0-REVIEW [@claude, Opus-class]** — CODE-GROUNDED adversarial review (read the actual source;
  IGNORE any existing review docs). Cover reliability, concurrency, security, data model,
  cost/abuse, coupling, ops blind spots, version hygiene. Per finding: area-prefixed ID, severity
  P0-P3, problem with PUBLIC file:line evidence from the code, concrete FIX + which in-tree
  primitive to reuse, acceptance criteria, CODE vs CODE+OPS tag. Plus: dependency-ordered ranking
  (mark FOUNDATION), hot-file collision map, validated-strengths do-not-touch list. Output
  docs/adversarial-review-fresh.md.
- **P0-SKEPTIC [@codex, fresh, gated on P0-REVIEW]** — stress every finding AGAINST THE CODE
  (open each cited file:line; verify it's real, severity right, Fix sound, named primitive
  exists, won't break a strength). Produce CONFIRMED (with narrowed scope) and REFUTED/DO-NOT-FIX
  sets. Update the doc inline. Set PHASE=REVIEW_FROZEN. Confirmed = Phase 1 spec; refuted = never
  fixed.
- **BOOTSTRAP** — transcribe confirmed finding IDs into the ledger CLOSE-INDEX (waves from the
  ranking: P0s first, then FOUNDATION, then rest); task-create each in Orca. Set PHASE=FIXING.
- **FIX LOOP [Phase 1]** — P0s first, FOUNDATION early, parallel across non-colliding files, one
  in-flight task per hot file. Each fix runs the engine's PR-per-task pipeline (CODE→PR→REVIEW→
  FIX→SHIP conflict-aware). Reviewer independently re-demonstrates each finding's acceptance.
- **T-FINAL [@grok]** — build green, lint clean, full suite green incl. added tests; every
  confirmed finding CLOSED or CODE_CLOSED(+OPS recorded). Output docs/arch-build-readiness.md
  (each finding's status + closing PR, the OPS/VERIFY-AT-SCALE queue tagged with what it unblocks,
  recorded decisions, downstream human gates marked NOT done, all PRs). Ship as the final PR.

## DONE
Review frozen; every confirmed finding CLOSED or CODE_CLOSED(+OPS recorded); every fix task
terminal; docs/arch-build-readiness.md exists. Terminal state = engineering landed on BASE + OPS
queue surfaced — NOT deployed, NOT promoted to main. Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)
- The review is grounded in the CODE, not any existing doc. Phase 1 converges to CONFIRMED Fixes;
  never fixes a REFUTED non-issue.
- REUSE in-tree primitives over new infra wherever the review names one.
- KEEP validated strengths — close findings around them, never refactor them.
- Findings needing load/prod data the swarm can't see → ship code + plan, mark CODE_CLOSED +
  VERIFY_AT_SCALE; never block the loop.
- One in-flight task per hot file; the BASE→main promotion and any OPS apply are human-owned and
  out of scope.
- Any ambiguity → close the finding most faithfully to its Fix while keeping the loop
  terminating, the prod path safe, the strengths intact, history clean.
