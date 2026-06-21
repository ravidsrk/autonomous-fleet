# doc-sync progress (dogfood of the new disciplines, 2026-06-21)

PHASE: FIXING
MISSION: doc-sync   REPO: autonomous-fleet   BASE: ravidsrk/dogfood-doc-sync (off main@1e14409)
COORDINATOR: this Claude Code session

Dogfood goal: run a real doc-sync mission with the engine disciplines shipped this week active, and
show each one producing a real artifact.

## SELF-ORIENTATION
- REPO_ROOT resolved; product = autonomous-fleet (orchestration framework); MAINTAINER = Ravindra
  Kumar. Test cmd = pytest; lint = validate-all.sh.
- MISSION-FIT: doc-sync premise (docs drifted from code) CONFIRMED by grep, the README scripts/
  block and capability docs do not mention run-sandboxed.sh, coupling-graph.py, render-dashboard.py,
  the research/cost disciplines, container-use, or the new fleet-outcome fields.

## PLAN / DAG VALIDATION GATE (SPOQ, before any worker spawns)
Frozen work units:
- U1 README scripts/ Layout block: add run-sandboxed.sh, coupling-graph.py, render-dashboard.py.
- U2 README capabilities note: research discipline, cost routing, safety classifier, container-use
  placement, the cost_estimate/unverified_assumptions fleet-outcome fields.
U1 + U2 both touch README.md (one hot file) -> ONE task unit, no inter-task dependencies.
GATE: no cycles (trivial), dependencies resolvable (none), parallelism width = 1. PASS.

## COUPLING-AWARE PLACEMENT
One file (README.md). No coupling graph needed; single serialized unit. (scripts/coupling-graph.py
would cluster it trivially.)

## TASK ROW
TASK doc-sync-readme | FILE=README.md | PLACE=container-use(independent) | WORKER=codex(cross-vendor
to the claude coordinator+reviewer) | CODED=f REVIEWED=f MERGED=f | reviewed_sha=- | NOTE=edits made
inside a container-use environment, then checked out + reviewed + merged.

## DISCIPLINES EXERCISED (evidence appended as the run proceeds)
- RESEARCH: docs/research-notes.md (facts verified, unverified_assumptions: 0).
- COST ROUTING: builder=codex (mid tier), reviewer=claude/coordinator (strong). cost_estimate tracked.
- CONTAINER-USE PLACEMENT: worker runs in an isolated container + its own git branch.
- CROSS-VENDOR REVIEW + SHA-PIN: claude reviews codex's diff; reviewed SHA recorded; re-review if HEAD moves.
- SAFETY CLASSIFIER: the worker's git/gh commands pass scripts/run-sandboxed.sh --classify.
- SIGNAL RECONCILIATION: before MERGED, re-verify the external fact (gh pr / branch) overrides the ledger flag.
- DASHBOARD: scripts/render-dashboard.py renders this ledger into the four zones at close.
