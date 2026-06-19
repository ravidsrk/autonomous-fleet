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

## Prior runs

See git history for doc-sync trial on `fleet/doc-sync-base` (pre fleet-outcome).