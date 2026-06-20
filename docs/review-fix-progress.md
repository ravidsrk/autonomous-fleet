# Review-Fix Progress Ledger

Authoritative coordinator state for the frozen-review fix run. Reconstruct from THIS file, not
memory. REVIEW_DOC = `docs/autonomous-fleet-review.md` (frozen). BASE = `ravidsrk/review-fix` off
`main`@354c90a. MAINTAINER = ravidsrk <ravidsrk@gmail.com> (sole author, no trailers).

PHASE: FIXING

## Regression floor (re-check each merge)
- BASELINE @354c90a: validate-all.sh GREEN (skills step skipped — skill-creator not installed
  locally; CI installs it), pytest **25 passed**, 4 preset dry-runs exit 0.
- Post-H2 baseline command: `VALIDATE_SKILLS_OPTIONAL=1 ./scripts/validate-all.sh` (skill-creator
  install was blocked locally by the sandbox classifier; the new opt-out flag is the documented
  escape hatch; full skills validation deferred to CI).
- CURRENT: validate-all.sh GREEN, pytest **25** (rises as M3 adds tests), presets exit 0.

## CLOSE-INDEX
| ID | Sev | Status | PR |
|----|-----|--------|----|
| H1 | H | OPEN | — |
| H2 | H | OPEN | — |
| H3 | H | OPEN | — |
| M1 | M | OPEN | — |
| M2 | M | OPEN | — |
| M3 | M | OPEN | — |
| L1 | L | OPEN | — |
| L2 | L | OPEN | — |
| L3 | L | OPEN | — |
| L4 | L | OPEN | — |
| L5 | L | OPEN | — |
| L6 | L | OPEN | — |

## TASK ROWS
Flags: CODED PR_OPEN REVIEWED MERGED ACCEPT (t/f). FILE=indep means disjoint file set (parallel-safe).

| TASK | SEV | FILE | CLOSES | CODED | PR_OPEN | REVIEWED | MERGED | ACCEPT | PR# | WT | WORKER | NOTE |
|------|-----|------|--------|-------|---------|----------|--------|--------|-----|----|--------|------|
| fix-h1-license   | H | indep | H1            | f | f | f | f | f | — | — | — | LICENSE + regression test |
| fix-validators   | H | indep | H2,M1         | f | f | f | f | f | — | — | — | scripts/ validators + run-campaign + their tests |
| fix-engine-lib   | M | indep | M3            | f | f | f | f | f | — | — | — | fleet_outcome.py + test_fleet_campaign/injection/validate_cli |
| fix-safety       | H | indep | H3,L2         | f | f | f | f | f | — | — | — | engine.md + runtime-goals.md + headless + run-sandboxed.sh |
| fix-skills-meta  | L | indep | L1,L5,L6m     | f | f | f | f | f | — | — | — | 7 mission SKILL.md + codex adapter version |
| fix-docs         | M | indep | M2,L3,L4,L6r  | f | f | f | f | f | — | — | — | docs + community-skills + secure-ship.yaml + README |

Hot-file serialization (already enforced by the disjoint decomposition):
- LICENSE → fix-h1-license only.
- scripts/run-campaign.sh + validators + test_run_campaign.py → fix-validators only.
- scripts/lib/fleet_outcome.py + test_fleet_campaign/injection/validate_cli → fix-engine-lib only.
- engine.md + runtime-goals.md + run-mission-headless.sh → fix-safety only.
- mission SKILL.md ×7 + codex adapter SKILL.md → fix-skills-meta only.
- README/DECISIONS/readiness/community-skills/campaigns.yaml → fix-docs only.
- L6 wording appears in README (fix-docs) and mission descriptions (fix-skills-meta) — different
  files, coordinated wording, no conflict.

## Roles
- Coder = Agent-tool subagent (drives edits + tests + commit in an assigned worktree). [@grok role]
- Reviewer = `codex exec` read-only independent review of the diff. [@codex role]
- Integrator = this coordinator: push branch, `gh pr create --base ravidsrk/review-fix`, merge
  `--merge --delete-branch` (never squash), re-run baseline, update ledger. [@claude role]

## Merge order (disjoint, so conflict-free; sequence for baseline re-check)
fix-h1-license → fix-validators → fix-engine-lib → fix-safety → fix-skills-meta → fix-docs → T_FINAL.

## Log
- INGEST: REVIEW_DOC materialized, BASE created, baseline green confirmed (25 pytest). PHASE=FIXING.
