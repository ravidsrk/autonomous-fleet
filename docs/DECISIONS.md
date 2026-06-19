# DECISIONS — doc-sync run

## Self-orientation

| Field | Value |
|-------|-------|
| REPO_ROOT | `/Users/ravindra/projects/autonomous-fleet` |
| MAINTAINER | Ravindra Kumar `<ravidsrk@gmail.com>` |
| BRANCH_PREFIX | `fleet/` |
| BASE | `fleet/doc-sync-base` |
| Adapter | `autonomous-fleet-adapter-grok` |
| Test scope | This repository (dogfood doc-sync on autonomous-fleet itself) |

## Defaults

- Single PR for README/setup drift (one doc area) — sufficient for trial run.
- Remote `npx skills add` examples intentionally omit `-p` (user-global install); local clone uses `./scripts/install-skills.sh` which passes `-p`.