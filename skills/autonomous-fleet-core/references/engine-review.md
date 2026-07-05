# Engine review and shipping pipeline

Load when opening, reviewing, fixing, shipping, or cleaning up a task PR, including build-blind review and merge spot-checks.

<!-- moved from engine.md by the instruction-budget split; preserve doctrine semantics. -->

═══════════════════════════════════════════════════════════
PR-PER-TASK PIPELINE — commits preserved, NEVER squash, conflict-aware, checkout cleaned.
═══════════════════════════════════════════════════════════
The mission defines the role at each step (builder / reviewer / integrator) and any extra gates.
Default pipeline: BUILD → open PR → REVIEW → FIX → SHIP.
- TASK ROW (ledger): record ID, branch, PR#, REVIEWED_SHA, WT (worktree path or environment id),
  placement, and flags BUILT PR_OPEN REVIEWED MERGED WT_CLEAN. Set WT_CLEAN=false when PLACE
  creates an independent checkout or environment. Do not mark a task terminal until MERGED=true and
  WT_CLEAN=true. For dependent placement in the active checkout, record WT=<active> and set
  WT_CLEAN=true only after verifying no disposable checkout exists.
- BUILD (builder) on branch <prefix>/<slug> off BASE (PLACE per rules): set git user.name/email to
  MAINTAINER before commit #1; commit in SMALL, FREQUENT, logical increments; apply the
  AUTHORSHIP_MODE trailer policy (default `attributed`: agent Co-Authored-By trailer on every
  agent-produced commit; `maintainer-only` repos omit trailers); run secret-hygiene check before every
  commit/push. Implement the mission's unit; ADD a test wherever the mission calls for one. Run
  build + lint + affected/new tests green. Set the BUILT flag. PUSH. WORKER_DONE carrying the work
  identifiers + files modified + a short summary.
- OPEN PR (integrator): OPEN_PR against BASE with a title and body (what/why · acceptance
  checklist · any follow-up). PUBLIC info only — IDs + file:line, never secrets. Record PR#. Set
  PR_OPEN.
- REVIEW (reviewer — FRESH, BUILD-BLIND, never saw the build conversation): read the PR diff,
  grade ONLY against the unit's acceptance criteria. Read + verdict only, no edits. CROSS-VENDOR:
  when more than one worker vendor is available, the reviewer SHOULD be a DIFFERENT vendor than the
  builder (a Codex build reviewed by Claude, etc.) so a vendor's blind spot is not its own grader;
  hand the reviewer the diff + the acceptance contract as TEXT ONLY, never the build worktree or the
  builder's session. SCOPE of the "structural" claim: build-blindness is a MECHANICAL guarantee only
  in the cross-vendor / separate-process / Orca case, where the builder and reviewer are distinct
  processes (often distinct vendors) that never shared a session — there is no build conversation for
  the reviewer to see. On a SINGLE-SESSION / single-vendor adapter it is NOT a mechanical guarantee:
  the reviewer is a fresh same-vendor subagent with fresh context (instructed isolation + write
  isolation), not a process that mechanically cannot have seen the build. `run-sandboxed.sh --role
  reviewer` is a WRITE gate (candidate tree read-only, `.fleet/runs/<run_id>/` writable), NOT context
  isolation — it stops the reviewer editing, it does not blind it to a shared session. Single-vendor
  host: say so in DECISIONS.md and use a fresh same-vendor reviewer with fresh context. Actively try
  to FAIL it: real (not coverage-padding) tests, no lost behaviour, no secret leak, adheres to
  repo conventions, scoped/localized. Approve or request-changes with findings. WORKER_DONE
  PASS/FAIL. Set REVIEWED on pass. On FAIL → builder fixes on the SAME branch (dependent placement;
  more commits; re-push), re-review. Max 3 rounds, then BLOCKED. The 3-round cap is the
  coordinator's runtime rule; it is AUDITED AFTER THE FACT (not enforced at runtime) by
  `python3 <SUBSTRATE>/verify_round_budget.py` (run by validate-all in a clone), which FAILs a task that ran more than 3 failed
  review rounds then MERGED without a terminal GOAL_BLOCKED. The audit is only as complete as the
  emitted trace: a round the coordinator never recorded is invisible to it, so the script catches
  recorded over-runs, it does not stop one mid-flight.
  SHA-PIN (from AO code-review-manager.ts): record the exact reviewed SHA (`git rev-parse HEAD` on
  the branch) in the task row alongside REVIEWED. A PASS is bound to THAT SHA, not the branch name.
  If a newer SHA lands on the branch before SHIP (a fix-round push, a rebase, any commit), the prior
  PASS is OUTDATED: clear REVIEWED and force a re-review of the new SHA. Never ship a PASS that was
  graded against a SHA the branch has since moved past.
  ENFORCED (not prose-only): the reviewer writes `.fleet/runs/<run_id>/sha-pin.json`
  {reviewed_sha, branch, verdict} at PASS; `python3 <SUBSTRATE>/verify_sha_pin.py` (run by validate-all in a clone)
  re-resolves the branch HEAD and FAILs when reviewed_sha has diverged, so a stale PASS cannot
  ship even if the coordinator forgets. When HEAD moves, supersede the old record (superseded: true)
  and emit a fresh sha-pin for the new SHA — at most one active approve per branch. A merged task
  whose branch was deleted is N/A, not a fail.

═══════════════════════════════════════════════════════════
DONE CONDITION: regression-catching test.
═══════════════════════════════════════════════════════════
A feature/fix task cannot set REVIEWED and cannot be done unless it includes a regression-catching
test that would FAIL if the repaired behavior broke again. The build-blind reviewer explicitly
asserts that test is present, behavior-exercising, and not coverage padding before returning PASS.

- SHIP (integrator, CONFLICT-AWARE): on REVIEWED, BEFORE merging confirm the branch HEAD still
  equals the SHA-pinned REVIEWED SHA; if it moved, the PASS is outdated — force re-review, do not
  ship stale. Then check conflicts vs BASE. IF
  CONFLICTS: rebase the branch onto updated BASE, resolve preserving BOTH the change intent and
  what landed on BASE since fork, keep commits authored by MAINTAINER with the AUTHORSHIP_MODE trailer policy applied; re-run
  lint + affected tests green; if the resolution materially changed logic, dispatch a quick
  reviewer re-review of the rebased diff; force-push. Only when conflict-free + green: MERGE_PR
  with a merge commit (ALL commits preserved, NEVER squash), delete the PR branch. Pull BASE,
  verify MERGED + branch-deleted FIRST, then update the ledger (MERGED). CLEANUP the merged
  checkout only after guard clauses pass: NEVER remove the active worktree; NEVER remove a worktree
  whose branch is unmerged; NEVER remove a worktree with uncommitted changes. The adapter resolves
  remove/archive version-tolerantly: try X, fall back to Y. Set WT_CLEAN=true, then
  SYNC_TASK_STATE(completed). WORKER_DONE.
- You only SEQUENCE and wait. Each task = one branch = one PR = one merge-commit = branch deleted =
  checkout cleaned = task completed.

═══════════════════════════════════════════════════════════
CLUSTER-INHERITANCE CLOSE: one PR closes the foundation + its dependents.
═══════════════════════════════════════════════════════════
When a single root cause produces multiple findings (e.g. one shared bug surfaces as five
separately-IDed issues), the FOUNDATION cluster fix closes the dependent findings IN THE SAME PR.
The ledger CLOSE-INDEX records every dependent ID as `CLOSED via PR#n` pointing at the foundation
PR. Workers must explicitly enumerate `CLOSES=[ids]` in the PR body so the reviewer and the verifier
can confirm coverage — and each dependent ID is only marked closed when ITS OWN EVID repro (per the
FROZEN-ARTIFACT CLOSE TEST) and acceptance gate pass against the foundation PR. Cite directives.md
"Frontguard 16-cluster root-cause map" (FOUNDATION clusters bias first; dependents inherit) and the
FOUNDATION/INDEPENDENT + `touches:` overlap hint pattern.

═══════════════════════════════════════════════════════════
FIRST-MERGE SPOT-CHECK: block later waves on fail.
═══════════════════════════════════════════════════════════
After the first task merges into BASE, run a one-time spot-check before launching or merging later
waves. Assert the produced merge preserved the branch commit count, every preserved commit is authored
by MAINTAINER, trailer usage matches the recorded AUTHORSHIP_MODE (attributed: agent trailers
present on agent commits; maintainer-only: none), the PR branch is deleted, and the
secret-scan ran for the merge path. Record FIRST_MERGE_SPOT_CHECK=PASS or FAIL in DECISIONS.md. On
FAIL, block later waves and repair the merge pipeline before any further SHIP step.

═══════════════════════════════════════════════════════════
T_FINAL WORKTREE-ORPHAN SWEEP: no merged task leaves a checkout.
═══════════════════════════════════════════════════════════
At T_FINAL, inspect every recorded WT and the host worktree or environment list. For each task with
MERGED=true and WT_CLEAN=false, run CLEANUP only after the same guard clauses pass: not active,
branch merged and deleted, no uncommitted changes. For any orphan worktree or environment matching
BRANCH_PREFIX with no ledger row, archive or remove it only if external SCM proves merged and
branch-deleted; otherwise record it in DECISIONS.md and keep it. Use adapter version-tolerant
remove/archive syntax: try X, fall back to Y. The readiness doc is blocked while any merged task
remains WT_CLEAN=false.

═══════════════════════════════════════════════════════════
TRUST BOUNDARIES — trigger-loaded in `references/engine-autonomy.md`.
═══════════════════════════════════════════════════════════
Load `references/engine-autonomy.md` before processing repo/issue/worker content or safety-sensitive tasks.
