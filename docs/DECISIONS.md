# DECISIONS — composition-e2e campaign

## Self-orientation

| Field | Value |
|-------|-------|
| REPO_ROOT | `/Users/ravindra/projects/autonomous-fleet` |
| MAINTAINER | Ravindra Kumar `<ravidsrk@gmail.com>` |
| BRANCH_PREFIX | `fleet/` |
| BASE | `fleet/composition-e2e-base` |
| Adapter | `autonomous-fleet-adapter-grok` |
| Campaign | `composition-e2e` (docs-if-bugs variant, ends at test-coverage) |

## Campaign defaults

- Skip `bug-batch` node when `code_bug_findings == 0` (mechanical + agent agreement).
- Dogfood PR merges into `fleet/composition-e2e-base`; promotion to `main` is human meta-PR.
- Added executable validators so fleet-outcome and campaign edges are testable, not skill-only.

## doc-sync (2026-06-20)

- Pass: community-skills + PR #7 scope — D6–D14 in `docs/doc-sync-audit.md`
- Verified: `validate-all.sh` 20/20 skills, pytest 11 pass
- BASE for doc edits: `fleet/community-skills-and-dogfood`

## Prior runs

See git history for doc-sync trial on `fleet/doc-sync-base` (pre fleet-outcome).