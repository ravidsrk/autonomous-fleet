# arch-build-progress (adversarial-review-and-fix: REST of the codebase, 2026-06-21)

PHASE: DONE
MISSION: adversarial-review-and-fix   REPO: autonomous-fleet   BASE: ravidsrk/dogfood-adversarial-rest (off main@a3ceb81)
REVIEW_DOC: docs/arch-build-review-rest.md (frozen; 12 confirmed findings)
COORDINATOR: this Claude Code session

## TARGET
Everything PR #26 did not cover: CLIs + fleet_outcome older code, 8 shell scripts, engine.md + 4
references, 5 adapters, 17 missions, 6 campaigns.

## REVIEW (workflow: 6 finder partitions reproduce by execution / file:line+scenario -> 2 refuters each)
Two passes (transient rate-limit truncated the first; resume completed coverage). 16 raised, 12
confirmed (union of both passes). by partition: python-clis 4, adapters 4, shell 1, engine 1,
references 1, missions-campaigns 1.

## PLAN + FIX
12 fix units across 8 files. All fixed + verified by execution (pick_next_node fallback, validate
batch, run-campaign dry-run, codex/grok/container-use CLI cross-checks). 3 P1 (D1 blocked-halt, E-2
codex headless goal, F1-missions back-edges), 9 P2. See docs/arch-build-review-rest.md.

## TASK ROWS (all CODED=t REVIEWED=t MERGED=f, reviewed_sha=2b7ef3f)
F1-eval / F2 / F4 (fleet_outcome.py) · F3 (validate_fleet_outcome.py) · B2 / D1 / F1-miss
(run-campaign.sh) · C4 (engine.md) · E-1 (3 adapters) · E-2 (codex adapter + runtime-goals.md) ·
E1 (orca) · E2 (grok).

## DISCIPLINES
RESEARCH (reproduce, cross-check CLIs) · PLAN/DAG gate · COUPLING (hot files: fleet_outcome.py,
run-campaign.sh serialized their findings) · adversarial verify (2 refuters/finding) · SIGNAL
RECONCILIATION (re-measured: dry-run + suite green after each) · DASHBOARD. Honesty: rate-limit
truncation surfaced + resumed, recorded in the readiness.
