# Gap analysis: genesis prompts vs autonomous-fleet

What the two source documents that birthed autonomous-fleet specify, mapped against what the
framework actually implements today. Sources: the maintainer's `orca-orchestration-prompts-FINAL.md`
(25 prompts across 9 stages + the Appendix throughline of 9 distilled ideas + the Stage-9 rails) and
`orchestration-directives-and-explanations.md` (3 production `/orchestration` directives + the shared
model). Produced 2026-06-21 by a 6-theme mapping workflow: each pattern was verified by reading the
source-doc section AND grepping the repo, then an adversary re-checked every CAPTURED/PARTIAL claim to
downgrade anything over-credited. Evidence is a repo `file:line` where the pattern is implemented, or
the source-doc line where it lives when the repo lacks it.

## Reconciliation (2026-06-29)

The gap rows below are the **original audit snapshot** from 2026-06-21. A dogfood
`adversarial-review-and-fix` run closed every PARTIAL/MISSING item against
`docs/close-gaps-readiness.md` (BASE `ravidsrk/close-gaps`). On current `main`, all 26 patterns are
**CAPTURED** in engine doctrine, missions, validators, and/or `tests/test_engine_disciplines.py`.

| Area | Original (2026-06-21) | Now |
|------|----------------------|-----|
| Stage 1–8 engine machinery | 11 CAPTURED | unchanged |
| Stage 9 rails (anti-inflation, lanes, WT_CLEAN, EVID, …) | 11 PARTIAL + 4 MISSING | **CAPTURED** — see `skills/autonomous-fleet-core/references/engine.md`, `skills/adversarial-review-and-fix/SKILL.md`, `scripts/verify_*.py` |
| Adapter WT_CLEAN guard echo | PARTIAL (engine only) | **CAPTURED** — all shipped adapters + `tests/test_adapter_namespacing_doc.py` |

**Still operator-owned (not a code gap):** external-repo run with `prs_merged > 0` and a citable
public benchmark — tracked in `docs/external-dogfood/README.md` and `docs/roadmap-gap-matrix.md`.

BOTTOM LINE (original 2026-06-21): 26 distinct patterns. 11 CAPTURED, 11 PARTIAL, 4 MISSING.
BOTTOM LINE (reconciled 2026-06-29): **26 CAPTURED** in repo artifacts; remaining work is proof on
external repos, not missing rails.

## CAPTURED (engine machinery is faithfully distilled)

| pattern | evidence |
|---------|----------|
| Self-orientation, no placeholders — resolve repo/product/maintainer fr | engine |
| File ledger = external brain; boolean exit gates; survives compaction  | engine |
| Worker placement dependent-vs-independent; 'fresh worker != new git wo | engine |
| One-PR-per-task, commits preserved, never-squash, conflict-aware, clea | engine |
| Autonomy is MECHANICAL not exhortative — poll task-list every turn, an | engine |
| Thin loop-holder coordinator that never plans/codes/reviews/merges its | autonomous-fleet-core/SKILL |
| Rolling check-wait windows; a timeout / {count:0} is a checkpoint, not | engine |
| 3-failure circuit-breaker -> reassign | engine |
| FINDING CLOSE-INDEX in the ledger | skills/adversarial-review-and-fix/SKILL |
| CODE_CLOSED + verify-at-scale for ops-blocked findings | CONFIRMED CAPTURED |
| DESIGN-ADOPTION via the claude_design MCP connector | CONFIRMED CAPTURED (re-checked, holds) |

## GAPS (PARTIAL + MISSING), prioritized

### [P1] [PARTIAL] The FROZEN ARTIFACT the whole run may not exceed — scope plan / code-grounded review bounding the run; the difference between converging and expanding forever

- Theme: Engine machinery & autonomy
- Evidence: Confirmed PARTIAL after independent grep. Source doc D1:3049 elevates this ABOVE the five ideas as the wrapping discipline. In the repo it exists only at MISSION level: take-product-to-completion/SKILL.md:10-11, :65 ('The single control that matters is the FROZEN BOUNDARY'), :110-113 ('FROZEN: the boundary does NOT expand mid-build ... nothing IN may be thinned'); adversarial-review-and-fix/SKILL.md:69 ('frozen external artifact'). Engine.md has only: a passing clause at line 109 ('If the mission's frozen artifact already decided, follow it') and the STRUCTURAL PLAN/DAG VALIDATION GATE at 242-256 over a 'frozen task DAG' — which validates DAG shape (no cycles, resolvable deps, parallelism width), NOT a discipline that caps the run's SCOPE. There is no engine-level block stating the frozen scope artifact bounds the whole run. DOWNGRADE-RESISTANT: the mapper's PARTIAL stands; I confirmed the engine gap is real, not just under-cited.
- Recommendation: Add a short engine-level discipline block in engine.md (near AUTONOMY ENFORCEMENT or after the PLAN/DAG GATE) titled e.g. 'FROZEN SCOPE BOUNDARY' stating the mission's frozen artifact caps the run's scope, new ideas route to ROADMAP/DECISIONS.md not into the build, and a reviewer fails any PR adding out-of-boundary work — so every mission inherits it instead of re-stating it.

### [P1] [PARTIAL] WT_CLEAN guard clauses

- Theme: Cleanup gate & completion integrity
- Evidence: CONFIRMED PARTIAL (mapper correct, not over-credited). Source: orca-orchestration-prompts-FINAL.md:3001 (six places: WT_CLEAN boolean in task row, version-tolerant orca worktree remove/archive with three guard clauses, WT recorded at spawn, ordered SHIP removal, termination gate treats merged-but-uncleaned as not-done, T_FINAL orphan sweep, handoff carries WT/WT_CLEAN); reinforced at :2979 and :3057. Repo: bare CLEANUP only — engine.md:20 'CLEANUP(worktree)' and engine.md:409 'CLEANUP the merged checkout'; adapters do unguarded `git worktree remove`/`container-use delete` (adapter-codex/SKILL.md:66, adapter-claude-code/SKILL.md:90,160, adapter-grok/SKILL.md:71,119, adapter-orca/SKILL.md:96 'remove/archive'). Verified by grep: NO `WT_CLEAN` token anywhere in skills/ or scripts/; NO active/unmerged/dirty guard; CONTEXT HANDOFF block (engine.md:224-239) lists flags/PR#/handles/placements but never WT/WT_CLEAN; TERMINATE gate (engine.md:142) keys on mission DONE + readiness doc, no merged-but-uncleaned check; no worktree T_FINAL orphan sweep (engine.md COMPENSATION at :164/:213 only closes orphan PRs, not worktrees).
- Recommendation: In skills/autonomous-fleet-core/references/engine.md add a WT_CLEAN task-row boolean to the PR-PER-TASK PIPELINE (~line 410) with three guard clauses (never remove active/unmerged/dirty worktree; verify MERGED + branch-deleted first), add WT/WT_CLEAN to the CONTEXT HANDOFF list (~228) and the TERMINATE gate (~142, merged-but-uncleaned = not done), and add a T_FINAL worktree-orphan sweep; have each adapter (orca/claude/grok/codex) note its version-tolerant remove-or-archive syntax with try/fallback.

### [P1] [PARTIAL] Real e2e/demo flow passing is the TERMINATION GATE

- Theme: Anti-inflation (green != working)
- Evidence: CONFIRMED PARTIAL (not downgraded). source: orca-orchestration-prompts-FINAL.md:3011,3061 ('the real pnpm demo:e2e passing end to end ... is the termination gate'). Repo: engine.md:142 TERMINATE = mission DONE condition met in the file AND final readiness doc exists — no e2e gate. Grep over engine.md, fleet-outcome.md, fleet_outcome.py, validate-fleet-outcome.sh, run-sandboxed.sh found ZERO e2e/demo termination machinery (only engine.md:224 unrelated 'not sufficient' about compaction). The only 'works/walk end to end' product check is take-product-to-completion/SKILL.md:125-130,146 T_FINAL, a prose @claude coordinator instruction, not a mechanical gate; fleet_outcome.py MISSION_METRICS (lines 15-45) has no e2e_passing/demo_passing field for any of the 17 missions.
- Recommendation: Add a mechanical e2e gate: a `demo_e2e_passing` (or `e2e_verified`) boolean to fleet_outcome.py MISSION_METRICS for completion/rebuild/build missions, asserted via querying real result state (not exit codes), and reference it in engine.md TERMINATE.

### [P1] [PARTIAL] Structural anti-inflation doctrine: green unit suite necessary but NOT sufficient; run must not believe its own green checkmarks

- Theme: Anti-inflation (green != working)
- Evidence: CONFIRMED PARTIAL (not downgraded). source: orca-orchestration-prompts-FINAL.md:3013,3061 ('a green unit suite is necessary but not sufficient'; 'an autonomous run will otherwise believe its own green checkmarks'). Repo has structural anti-inflation ONLY on the review axis: engine.md:380-387 build-blind cross-vendor reviewer actively tries to FAIL with 'real (not coverage-padding) tests'; engine.md:138 'A task advances only when its flags read true IN THE FILE — not when you believe'. Grep confirmed NO engine-level rule that a green suite is insufficient evidence of a working product; product-level 'works e2e' is prose only (T_FINAL). adversarial-review-and-fix/SKILL.md (the mission born from this exact Aula lesson) contains ZERO e2e/green-suite-insufficiency language.
- Recommendation: Add an engine.md invariant under AUTONOMY ENFORCEMENT: 'a green unit suite is necessary but not sufficient; never TERMINATE on green checkmarks alone — verify the real end-to-end result state.' Echo it into adversarial-review-and-fix/SKILL.md DECISION DEFAULTS.

### [P2] [MISSING] Three-lane split

- Theme: Surfacing lanes (refuse / draft-and-gate)
- Evidence: Source: orca-orchestration-prompts-FINAL.md:3007-3009 and Appendix idea #8 at :3059. Repo: grep for 'three[ -]?lane' / 'lane[ -]?0|a|b' / 'draft both' / 'both options' returns ZERO substantive hits across skills+scripts (only unrelated uses of 'surface' as a noun). adversarial-review-and-fix/SKILL.md has only CONFIRMED-fix + CODE_CLOSED/VERIFY_AT_SCALE + 'OPS apply is human-owned' (lines 144-152) — a binary fix/defer model, no lane taxonomy.
- Recommendation: Add a THREE-LANE REMEDIATION section to skills/adversarial-review-and-fix/SKILL.md classifying each frozen finding into Lane A (fully implement), Lane B (draft both versions, stop at decision gate), Lane 0 (refuse + surface as human action), so audit findings that are not code get the right outcome.

### [P2] [MISSING] Lane B — draft both versions and stop at a decision gate for editorial/brand-truth findings

- Theme: Surfacing lanes (refuse / draft-and-gate)
- Evidence: Source: orca-orchestration-prompts-FINAL.md:3008 ('drafts both versions and stops at a decision gate') and idea #8 at :3059. Repo: grep for 'editorial' / 'brand' / 'self-deal' / 'draft both' / 'both version' / 'prepare both' returns ZERO hits across skills+scripts. The only decision mechanism is engine.md:102-105 'STOP the wave, name the conflict in DECISIONS.md, pick the mission-intent default OR defer' — which RESOLVES with a default rather than drafting two options and halting for a human, the opposite of Lane B.
- Recommendation: Add a 'draft-both-and-gate' outcome to engine.md decision-gate handling (near line 104) and to adversarial-review-and-fix DECISION DEFAULTS: for editorial/disclosure/brand-truth findings, the fleet prepares both variants, records them in DECISIONS.md, and HALTS for a human rather than picking a default.

### [P2] [MISSING] Rotate-before-scrub hard human precondition

- Theme: Surfacing lanes (refuse / draft-and-gate)
- Evidence: Source: orca-orchestration-prompts-FINAL.md:3009 ('rotation is rotate-first/scrub-second, and the history-purge task is hard-gated on ROTATION_CONFIRMED=yes') and idea #8 at :3059. Repo: grep for ROTATION_CONFIRMED / rotate-first / 'rotate before' returns ZERO hits. SECRET HYGIENE (engine.md:480-487) covers gitleaks blocking on commit and never-commit-secrets, but has NO ordering gate making a history-purge / repo-scrub depend on confirmed human rotation first.
- Recommendation: Add to engine.md SECRET HYGIENE (after line 487) a hard precondition: any git-history purge / secret-scrub task is gated on a file-tracked ROTATION_CONFIRMED=yes boolean (human-set), since scrubbing before rotating gives false safety on already-compromised committed keys.

### [P2] [PARTIAL] VERIFY THE FIRST MERGE preserved all commits

- Theme: Cleanup gate & completion integrity
- Evidence: CONFIRMED PARTIAL (mapper correct, not over-credited). Source D2: orchestration-directives-and-explanations (1).md:1211 (also :390 'VERIFY THE FIRST PR MERGE preserved all commits...branch deleted, and that the secret-scan ran' and :790). Repo: engine.md SHIP preserves the merge at merge time — merge commit, ALL commits preserved / NEVER squash, commits authored by MAINTAINER with no trailers, delete branch (engine.md:404-409), and SIGNAL RECONCILIATION / EXTERNAL FACT re-verifies merge STATE before writing MERGED (engine.md:184-189). But verified by grep: NO check that the FIRST produced merge commit actually preserved commit-COUNT/authorship before proceeding to later tasks — no mission (adversarial-review-and-fix/SKILL.md, others) and no engine line does a first-merge spot-check (`git log --merges`/commit-count/author assertion). gitleaks exists per-commit (engine.md:480-482) but is NOT wired as a first-merge gate the way the source bundles it.
- Recommendation: In skills/autonomous-fleet-core/references/engine.md (PR-PER-TASK PIPELINE, after the SHIP step ~line 409) add a one-time FIRST-MERGE spot-check: after the first task merges, assert the produced merge commit preserved the branch's commit count, is authored by MAINTAINER with no trailers, the branch is deleted, and gitleaks ran — record PASS/FAIL in DECISIONS.md and block later waves on FAIL.

### [P2] [PARTIAL] Lane 0 — REFUSE-and-surface a credential rotation only a human can perform

- Theme: Surfacing lanes (refuse / draft-and-gate)
- Evidence: Source: orca-orchestration-prompts-FINAL.md:3009,3059. Repo: engine.md:467-469 ('rotates a live key') + INFRA-CHANGES-ARE-CODE OPS recording at engine.md:470-472 (docs/arch-ops-actions.md). CONFIRMED PARTIAL (not downgraded): the live rotation IS refused by the SAFETY RAILS and the request-as-untrusted-data rail (engine.md:442-444), but it is handled as a generic 'live action -> OPS deferral', not as a Lane-0 'refuse THIS finding and surface it as a named human action'. Grep for ROTATION_CONFIRMED / rotate-first / 'named human' / 'human action' returns ZERO hits across skills+scripts. Credential rotation is not modeled as a distinct finding outcome anywhere (fleet_outcome.py outcomes have no refuse/human-only state).
- Recommendation: In skills/adversarial-review-and-fix/SKILL.md DECISION DEFAULTS (after line 150), add an explicit REFUSE-and-surface lane: a human-only finding (credential rotation, console/IAM action) is recorded as a named human action in docs/arch-ops-actions.md with a HUMAN_ACTION_REQUIRED tag and excluded from the fix loop, not silently folded into generic OPS apply.

### [P2] [PARTIAL] No feature 'done' without a regression-catching test

- Theme: Anti-inflation (green != working)
- Evidence: CONFIRMED PARTIAL (not downgraded). source: orca-orchestration-prompts-FINAL.md:3013,3061 ('No feature is done without a regression-catching test'). Repo has this PER-MISSION as prose, verified at exact lines: test-coverage/SKILL.md:71 'tests assert real behaviour, would FAIL if the code broke'; bug-batch/SKILL.md:74 'test genuinely reproduces the bug (fails WITHOUT the fix)'; take-product-to-completion/SKILL.md:158 + legacy-rebuild/SKILL.md:145 + contract-first-build/SKILL.md:219 'Tests real and behaviour-exercising; reject coverage-padding'. Missing as a global engine done-condition; fleet_outcome.py MISSION_METRICS has no regression-test-present field (only test-coverage's coverage_regressed and design-integration's regressions, neither = 'each feature has a failing-if-broken test').
- Recommendation: Promote to an engine.md DONE-condition: a feature/fix task cannot set REVIEWED unless a regression-catching test (fails if the behaviour breaks) is present; have the build-blind reviewer assert it explicitly at engine.md:387.

### [P2] [PARTIAL] Anti-inflation enforced at the framework's OWN dogfood but not generalized to target products

- Theme: Anti-inflation (green != working)
- Evidence: CONFIRMED PARTIAL (not downgraded). Repo: docs/secure-ship-e2e.md:17-29 internalizes the exact lesson against the fleet's OWN scripts ('A fix that isn't exercised the way production runs it can be silently inert. Only an end-to-end run with a real blocked outcome revealed that the security gate, validated and CI-green, did nothing') and added test_blocked_node_halts_campaign (line 24). Confirmed this is a retro doc about the campaign DRIVER (run-campaign.sh, line 3), not a reusable mission/engine rail: grep found no e2e/silently-inert rail in any skills/*/SKILL.md or engine.md that fires on user repos.
- Recommendation: Lift the secure-ship-e2e.md lesson into a reusable rail: add a 'fixes must be exercised the way production runs them, not just CI-green' DECISION DEFAULT to adversarial-review-and-fix/SKILL.md and engine.md, so it fires on target repos, not just the fleet's own driver.

### [P2] [PARTIAL] Each finding's OWN evidence-reproduction as its acceptance gate

- Theme: Frozen-audit ingestion
- Evidence: CONFIRMED PARTIAL (downgrade upheld). Reviewer-side re-run is asserted in prose: SKILL.md:120 'Reviewer independently re-demonstrates each finding's acceptance' and engine.md:380-388 (FRESH BUILD-BLIND reviewer grades against acceptance criteria, actively tries to FAIL). BUT independently verified: (1) `grep -rn EVID skills/ scripts/` returns ZERO hits — the named EVID flag from D2:314-320 does NOT exist; the only ledger flag is the generic per-task `ACCEPT` (SKILL.md:98), not keyed to 'the finding's own Evidence reproduction stops reproducing'. (2) The builder-side gate from D2:362-364 ('VERIFY (still @claude, before opening the PR): re-run the EXACT reproduction from each finding's Evidence block') is absent from the engine BUILD step (engine.md:371-376 only says 'ADD a test... build+lint+tests green', never re-run the finding's own repro) and absent from the mission FIX-LOOP (SKILL.md:118-120). So the dual re-run is prose-asserted on the reviewer side only and not mechanized as a named per-finding gate on either side.
- Recommendation: In skills/adversarial-review-and-fix/SKILL.md add a per-fix-task EVID flag (e.g. flags `CODED PR_OPEN REVIEWED MERGED EVID`) defined as 'the finding's own Evidence reproduction re-run and no longer reproduces', and add to the FIX LOOP a builder-side 'before OPEN_PR, re-run the EXACT reproduction from each finding's Evidence block' step mirroring the reviewer's re-demonstration.

### [P2] [PARTIAL] ROOT-CAUSE CLUSTERING with FOUNDATION-vs-INDEPENDENT tags + touches:/collision file-map so fixing a cause once closes dependents

- Theme: Frozen-audit ingestion
- Evidence: CONFIRMED PARTIAL (downgrade upheld). FOUNDATION half exists: SKILL.md:107 review marks FOUNDATION + a 'hot-file collision map', SKILL.md:115,118 'P0s first, then FOUNDATION'; engine.md:262-282 has INDEPENDENT/DEPENDENT placement + COUPLING-AWARE PARTITIONING (CLUSTER tightly-coupled files, SERIALIZE hubs) + the hot-file/one-in-flight rule. BUT independently verified the source-doc contract is NOT met: `grep -ni 'cluster\|root.cause\|independent\|touches:\|inherit'` on the mission shows NO occurrence of root-cause CLUSTER grouping of findings, NO INDEPENDENT *tag on clusters*, NO per-cluster `touches:` file-list schema, and NO 'fix the shared root cause once and let dependents inherit' closure rule. D2:96-97,220-294,403-404,436 and D1:3055 require GROUPING the findings into root-cause clusters, tagging each cluster FOUNDATION-vs-INDEPENDENT, a per-cluster `touches:` map, and a dependents-inherit closure contract. The engine's COUPLING-AWARE PARTITIONING clusters *files* at decomposition for conflict-avoidance, which is a different mechanism from clustering *findings* by shared root cause so one fix closes many. Mission only tags individual findings FOUNDATION.
- Recommendation: In skills/adversarial-review-and-fix/SKILL.md P0-REVIEW/SKEPTIC output, require grouping confirmed findings into root-cause CLUSTERS, each tagged FOUNDATION|INDEPENDENT with a `touches:` file list and a CLOSES=[ids] set, and add a DECISION DEFAULT 'fixing a FOUNDATION cluster's root cause once closes its dependent findings (mark them CLOSED via that PR)'.

### [P2] [PARTIAL] Upgrade-Everything-to-Latest mission

- Theme: Specialized missions
- Evidence: CONFIRMED PARTIAL (re-checked, holds). skills/dependency-update/SKILL.md captures research-required at lines 115-116 ('read the changelog/migration guide and fix the code properly — never pin-around or suppress') and lockfile handling at lines 65,77,86. But the repo's batching rule is the OPPOSITE of one-major-per-PR: it GROUPS deps ('one PR per logical group' / 'Group related packages into one coherent PR' lines 6,67,86,117) — grep for 'one major|one-major|major per' across dependency-update and targeted-migration returned ZERO hits. No manifest+lockfile-as-universal-hot-file serialization rule exists (no 'hot file'/'codemod'/'bump and pray'/'draft pr'/'BLOCKED' hits in either mission). A hard major is DEFERRED-with-reasoning to targeted-migration (lines 54,118-119), NOT enforced as a one-major isolate parked as a 3-round-BLOCKED DRAFT PR. Confirmed targeted-migration is single-axis only ('Change ONLY the target axis', line 115) and does not carry this pattern either. Source: orca-orchestration-prompts-FINAL.md:3003-3005.
- Recommendation: Add a maximal-posture variant or DECISION DEFAULT to skills/dependency-update/SKILL.md: for major bumps, isolate one-major-per-PR (override grouping), require changelog-research + official codemod before code (reviewer FAILs 'bump and pray'), treat manifest+lockfile as the universal hot file (serialize manifest-mutating tasks, parallelize independent ecosystems), and park a 3-round-BLOCKED major as a DRAFT PR with a concrete reason rather than only deferring to targeted-migration.

### [P3] [MISSING] Surface-an-engine/capability-boundary that can't be conjured as a human decision

- Theme: Surfacing lanes (refuse / draft-and-gate)
- Evidence: Source: orca-orchestration-prompts-FINAL.md:3013 (OpenMAIC AI-engine boundary 'surfaced as a human decision with buildable-now work separated from engine-blocked work') and idea #8 at :3059. Repo: grep for 'engine boundary' / 'AI-engine' / 'cannot.*conjur' returns ZERO hits. take-product-to-completion/SKILL.md tracks SCOPE/ROADMAP/IN-FIX (line 112) but has no concept of a capability boundary surfaced as a human decision that partitions buildable vs blocked.
- Recommendation: In skills/take-product-to-completion/SKILL.md add a CAPABILITY-BOUNDARY rail: when a root blocker is a capability the fleet cannot conjure (missing AI engine, unavailable API), surface it as a named human decision in DECISIONS.md and split the scope into buildable-now vs blocked-on-<boundary>, never fake the blocked half.
## Verified directly (the mapping workflow under-covered these)

The specialized-missions mapper returned only 2 of its items; these four were checked by hand against
the repo (grep over `skills/`):

### [P2] [MISSING] Inference-cost-optimization mission

- No cost mission exists (`ls skills/` has none). The doc's #18 is a measurement-first mission:
  baseline cost+quality harness, sanctioned levers only (model routing, prompt caching, batch/flex
  tier, provider abstraction, token hygiene), output-quality regression as a blocking gate, and an
  explicit REFUSAL of the ToS-violating subscription-token-as-backend hack.
- Recommendation: add `skills/inference-cost/SKILL.md` (Tier 1/2), with `MISSION_METRICS` entries
  (e.g. cost_before, cost_after, quality_regressed) and the sanctioned-levers + refuse-the-hack rail.

### [P2] [MISSING] Reuse-from a read-only REFERENCE library (TARGET vs REFERENCE dual-path)

- Prompts #2-#8 run with a TARGET repo to modify plus a REFERENCE repo to pull components from but
  NEVER modify ("not an Orca target"). The engine's PLACE primitive is about worktrees; there is no
  first-class "read-only reference input, never modify, never a target" mode. Only contract-first-build
  says "never modify" (about a frozen contract, not a reference repo).
- Recommendation: add a REFERENCE-INPUT concept to engine.md SELF-ORIENTATION (a path the fleet reads
  and adapts from but never writes to / never opens a PR against), used by design-integration and
  refactor-style missions.

### [P3] [MISSING] Research SPIKE (throwaway proof validates the protocol before the architecture is committed)

- Prompt #6 T3 builds one throwaway end-to-end proof to VALIDATE a streaming protocol before locking
  the architecture. The fleet has a RESEARCH DISCIPLINE but no spike/throwaway-validate-before-commit
  step distinct from "read the docs".
- Recommendation: add a SPIKE option to the RESEARCH DISCIPLINE in engine.md: for a load-bearing
  unknown, build one throwaway proof and record findings before the freeze, then discard it.

### [P3] [PARTIAL] Visual baseline before/after gate (replay the exact demo queries, compare shots)

- landing-page-convergence and design-integration reference screenshots/visual handling, but the
  prompt #7 discipline (record the exact demo queries that produced the baseline, replay them
  like-for-like in T_FINAL, confirm a strict improvement) is lighter than the source.
- Recommendation: in landing-page-convergence/design-integration, require recording the baseline
  capture commands so T_FINAL can replay them and produce an explicit before/after comparison.

## The meta-insight

The gaps are not scattered, they cluster almost perfectly in Stage 9: the RAILS for what an autonomous
fleet must refuse, draft-and-gate, or not inflate. Stages 1-8 (the engine: self-orientation, the file
ledger, worker placement, the PR pipeline, mechanical autonomy, the circuit-breaker, code-vs-OPS) are
fully in the library. The newest, hardest-won lessons (anti-inflation, the surfacing lanes, the frozen
scope boundary as an engine-level discipline) are the under-built frontier. The doc's own one-line
conclusion predicted this: "a stable engine, a swappable mission, and explicit rails for what the fleet
must refuse, discovered by building the engine fifteen times, distilling it, then pointing it at real
audits until the rails became as important as the machinery." The rails are the work that remains.

The single highest-value gap is the anti-inflation termination gate (Aula, throughline idea 9): a green
test suite is not proof a product works, the real end-to-end flow passing (verified by querying actual
result state, not exit codes) must be the termination gate. This is not theoretical: in the same session
that produced this analysis, the framework's own secure-ship blocked-halt shipped CI-green, validated,
and completely inert, and was caught only by an end-to-end run that queried the real exit code (recorded
in docs/secure-ship-e2e.md). The framework reproduced the exact Aula failure shape in its own code, which
is the strongest possible argument for making the anti-inflation gate structural.

## Recommended build order

1. P1 anti-inflation e2e gate, an engine-level invariant ("never terminate on green checkmarks alone,
   verify the real result state") + an `e2e_verified` fleet-outcome metric for completion/rebuild missions.
2. P1 FROZEN SCOPE BOUNDARY as an engine discipline so every mission inherits it.
3. P1 WT_CLEAN as a tracked task-row boolean gate with guard clauses + a T_FINAL sweep.
4. P2 the surfacing lanes (HUMAN_GATED draft-and-park + Lane-0 refuse + rotate-before-scrub), the EVID
   flag + root-cause clustering, the inference-cost mission, the upgrade maximal posture.
5. P3 polish: capability-boundary rail, the visual before/after gate, the duplicate-block cleanup in
   engine.md, the SPIKE and REFERENCE-INPUT concepts.
