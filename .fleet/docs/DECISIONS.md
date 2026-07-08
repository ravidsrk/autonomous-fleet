# DECISIONS — adversarial-review-and-fix c6c486

## Self-orientation

| Field | Value |
|-------|-------|
| repo | `ravidsrk/autonomous-fleet` |
| REPO_ROOT | `/workspace` |
| MAINTAINER | Cursor Agent `<cursoragent@cursor.com>` |
| BRANCH_PREFIX | `cursor/` |
| BASE | `cursor/adversarial-review-base-256a` off `main`@e9e541b |
| Adapter | `autonomous-fleet-adapter-grok` (same-vendor-instructed review) |
| LEDGER_DIR | `.fleet/docs/` (docs-site Starlight probe) |
| RUN_ID | `20260708T184204Z-adversarial-review-and-fix-c6c486` |
| RUN_SHORT | `c6c486` |
| SUBSTRATE | `/workspace/scripts` |
| AUTHORSHIP_MODE | `attributed` |
| reviewer_mode | `same-vendor-instructed` |

## ASSUMPTIONS

1. Scope = entire autonomous-fleet app (skills, scripts, substrate, CI, action, docs-site tooling).
2. Fresh-run: ignore prior review docs; write `docs/adversarial-review-fresh.md`.
3. Out of scope: BASE→main promotion, production deploy, secret rotation, load/prod verification.
4. SCM: `gh` authenticated as `cursor`; PRs merge into BASE with `--merge` (never squash).
5. Lane B findings open as draft `do-not-merge` PRs; never auto-merge.

## Skeptic decisions

- SEC-006 DO_NOT_FIX (version-tolerant auth probe).
- SEC-005/009/004/010/ARCH-004/ARCH-005 → Lane B (ask / human-gate or draft-both).
- OPS-001 narrowed: fatal only on real-run archive emit; dry-run cleanup stays non-fatal.
- Wave 1 Lane A: SEC-001, SEC-002, SEC-003, ARCH-001, ARCH-002, BUG-001 (FOUNDATION first).
