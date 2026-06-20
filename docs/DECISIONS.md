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

## Adversarial FIX run (2026-06-20)

Orca multi-agent FIX run. Review is frozen; this run only closes findings.

| Field | Value |
|-------|-------|
| REVIEW_DOC | `docs/adversarial-audit-2026-06-20.md` (resolved: `__REVIEW_DOC__` placeholder was unsubstituted and the default `docs/adversarial-review.md` is absent; this audit, written this session and the only frozen review in the tree, is the source of truth) |
| BASE | `ravidsrk/adversarial-fresh` off `main`@1460f47 |
| REPO_ROOT | `/Users/ravindra/orca/workspaces/autonomous-fleet/new-research` (repoId d19bcfee) |
| MAINTAINER | Ravindra Kumar `<ravidsrk@gmail.com>` |
| Roles | @grok codes (interactive Orca terminal), @codex reviews (`codex --full-auto`), @claude integrates |
| Worker effort | MAX / highest tier |

Decisions:

- Grok dispatch: interactive Orca terminal only. `grok -p` headless fails `Auth(AuthorizationRequired)` even with `XAI_API_KEY` set (the GEM-001 issue); interactive grok VERIFIED working with tool use (read README.md, returned first line, 11s). So the @grok coder runs in interactive Orca terminals via `dispatch --inject`, never `grok -p`.
- 5 fix tasks over disjoint file sets, all Wave 1, parallel; P0 (RCE-01) leads. REVIEW_DOC gave no explicit wave/hot-file map, so derived: group by the file(s) each finding touches. PIN-17 split into inline pinning in the two driver scripts (drivers task) and a shared `requirements.txt` (validators task) to keep file sets disjoint.
- No gitleaks config in repo; workers self-check diffs for secrets before push. No money/keys/prod surface, so SAFETY RAILS satisfied trivially; acceptance = local pytest + shell harness on fixtures.
- Merge policy: `gh pr merge --merge` into BASE (no squash), branch deleted, worktree retired. BASE->main promotion is a human meta-PR (out of scope).