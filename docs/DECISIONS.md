# DECISIONS — composition-e2e campaign

## Self-orientation

| Field | Value |
|-------|-------|
| REPO_ROOT | `/Users/ravindra/projects/autonomous-fleet` (canonical local clone of `ravidsrk/autonomous-fleet`) |
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
- Verified: `validate-all.sh` 20/20 skills, pytest 25 pass
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

## Review-fix run (2026-06-20) — frozen end-to-end review

Second adversarial fix run. Closes the frozen `docs/autonomous-fleet-review.md` findings
(H1, H2, H3, M1, M2, M3, L1–L6). Review is frozen; this run only closes findings, no re-scope.

| Field | Value |
|-------|-------|
| REVIEW_DOC | `docs/autonomous-fleet-review.md` (materialized this session — the "Autonomous-Fleet — End-to-End Review") |
| BASE | `ravidsrk/review-fix` off `main`@354c90a |
| REPO_ROOT | `/Users/ravindra/orca/workspaces/autonomous-fleet/research-mission` (worktree; `main` is checked out at `/Users/ravindra/projects/autonomous-fleet`) |
| MAINTAINER | Ravindra Kumar `<ravidsrk@gmail.com>` (sole author, no agent/tool trailers) |
| Roles | Coder = Agent-tool subagent; Reviewer = `codex exec` read-only; Integrator = @claude coordinator |

Decisions:

- **Orchestration mechanics:** literal Orca `@grok`/`@codex` agent-dispatch substituted with
  Agent-tool subagent coders + `codex exec` reviewers for reliability and verifiability. Identical
  role separation is preserved (coder ≠ reviewer ≠ integrator; nobody reviews their own work).
  Rationale matches the prior run's GEM-001 finding: `grok -p` headless fails `Auth` even with
  `XAI_API_KEY`, so headless grok dispatch is not dependable here. DECISION-DEFAULTS bless the
  option that closes findings faithfully while keeping the baseline green and history clean.
- **skill-creator install blocked:** `npx skills add … skill-creator` was denied by the sandbox
  classifier (untrusted external code). Consequence: skills validation can't run locally. Baselines
  use `VALIDATE_SKILLS_OPTIONAL=1 ./scripts/validate-all.sh` (the opt-out flag H2 introduces);
  full agentskills.io skill validation is deferred to CI (which installs skill-creator).
- **6 fix tasks over disjoint file sets**, parallel-safe, merged in a fixed order for a clean
  baseline re-check after each. H→M→L priority; HIGH (H1/H2/H3) leads.
- **Sandbox floor (the H3 discipline applied to this run):** workspace-write on REPO_ROOT only;
  no `--yolo`; no publish/deploy/host-env action; the H3 rail ships as code/docs, never activated
  against a live target. No gitleaks in repo → manual secret self-check on every diff before commit.
- **Merge policy:** planned `gh pr merge --merge --delete-branch`; DEVIATED to local
  `git merge --no-ff` into BASE because the harness classifier denied the outward `git push` / `gh
  pr create` / `gh pr merge` actions. Local merge commits preserve history, never squash, and fully
  close the findings; the directive sanctions this as the no-outward-actions fallback. `BASE → main`,
  pushing `ravidsrk/review-fix` to GitHub as real PRs, and any `npx skills` re-publish are
  human-owned and out of scope.
- **Independent review:** each of the 6 fix branches was reviewed by a FRESH read-only reviewer
  subagent (distinct instance from its coder) that re-ran the finding's proving commands and checked
  test quality (non-tautology) before integration. All 6: VERDICT PASS.