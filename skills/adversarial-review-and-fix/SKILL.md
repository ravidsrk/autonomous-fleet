---
name: adversarial-review-and-fix
description: >-
  [Tier 2 · moderate autonomy · full review gate · the proven two-phase workhorse] Run a
  rigorous CODE-GROUNDED adversarial architecture review of a repo, FREEZE it as the source
  of truth, then close every confirmed finding one at a time until done. Use for a
  security/architecture/ reliability hardening pass, a pre-production audit-and-remediate,
  or "review the whole app and fix everything." Phase 0 reviews the actual source (not
  existing docs) and a skeptic narrows out false findings; Phase 1 fixes the confirmed set
  with full safety rails. Runs via the autonomous-fleet-core engine. Trigger on:
  "adversarial review and fix", "audit and remediate", "review the whole app and fix the
  issues", "harden this before production", "find and fix the architecture problems".
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.1"
  tier: "2"
  fleet-component: "mission"
---

<!-- Corpus: prompts.md L2962 (Stage 8 Tier 2 grouping) + the whole Stage-9 audit-driven fix-run lineage (prompts.md L2987-L3015: prompts 17/19/20/21/23/24/25) + L3013 (Aula final form). Real-run input: docs/adversarial-audit-2026-06-20.md. -->


# Mission: adversarial-review-and-fix

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `cso` | User asked for security-audit depth beyond mission defaults | Proceed with mission skeptic + review gate only |
| `health` | User wants composite quality scorecard (`quality-gate` / `ship-with-proof` tail) | Mission metrics in readiness doc only |

Community catalog: `autonomous-fleet-core` → `references/community-skills.md`.

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (Phase 0 audit, skeptic) | `security-and-hardening`; `cso` when Optional `cso` active | Code-only audit per mission |
| @codex (fix builder) | `code-simplification` when fix touches >50 lines or adds new abstraction | In-tree primitives per frozen review |
| @claude (fresh build-blind reviewer) | — | Mission review gate only |
| @claude (integrator) | — | Mission ship gate only |

Stage-9 final form (Aula prompt 24, prompts.md L3013): @grok retired. @codex builds; a fresh
build-blind @claude reviews; @claude integrates. The cross-vendor reviewer rule still holds — the
fresh @claude reviewer must not have seen the build conversation (the reviewer terminal is a fresh
session distinct from the builder's, and is handed the diff + acceptance contract as TEXT ONLY).

## Deferred missions

Record in `docs/arch-build-readiness.md` under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Finding needs one-axis migration | `targeted-migration` |
| Doc/runbook drift after fixes | `doc-sync` |
| Dependency-related finding | `dependency-update` |

**Empirical note:** this mission's fixes span fix/refactor/security work — categories AI agents
are weaker at than docs/build, so the full review gate is essential. (There is no published
category-level merge rate for this composite; per-task merge rates vary by agent, so treat the
tier ordering as qualitative.) The structural key is that Phase 0 produces a FROZEN, richly-shaped
review BEFORE any fixing begins, so Phase 1 executes against a finished spec rather than judging
and fixing in one loop. The skeptic pass prevents fixing phantom findings.

## CORE PRINCIPLE
The review is a frozen external artifact in the exact shape the fix-loop consumes. Phase 0's job
is not "find problems" — it's "produce a review document that is ranked, dependency-ordered, with
per-finding Fix + acceptance + which in-tree primitive to reuse, CODE vs CODE+OPS tagged, plus a
hot-file collision map and a validated-strengths do-not-touch list, with a skeptic-narrowed
confirmed/refuted split." Phase 1 then runs the engine's PR-per-task pipeline keyed off the
confirmed findings.

## FRESH-RUN NOTE
If prior review docs / in-flight review branches exist, they are OUT OF SCOPE: don't read, reuse,
or overwrite them; write fresh outputs (docs/adversarial-review-fresh.md); branch BASE off the
default branch at current HEAD; don't disturb sibling worktrees. The review is grounded in the
CODE, not in any existing doc.

## GOAL
Find and CLOSE the real architecture/reliability/security/data/coupling/cost/ops/version issues in
the repo. "CLOSED" = the Fix is implemented, a test exists where the Fix calls for one, and
acceptance is demonstrated on staging/testnet/fixtures. Converge to the confirmed Fixes; never
reinterpret beyond them; never fix a refuted non-issue.

## THREE-LANE REMEDIATION
Engine definition: see `engine.md` → LANE PATTERN. The engine defines Lane A IMPLEMENT+MERGE,
Lane B DRAFT-BOTH+HUMAN-GATE, and Lane 0 REFUSE+SURFACE as the three terminal lanes. This mission
inherits them; below are the mission-specific ledger flags that go in the CLOSE-INDEX.

After P0-SKEPTIC freezes CONFIRMED findings, classify every confirmed finding before BOOTSTRAP and
record its lane in the CLOSE-INDEX (`lane: A|B|0`):

- **Lane A** → fix task in the PR-per-task pipeline; terminal flag `MERGED=true`.
- **Lane B** → both variants drafted, recorded in `DECISIONS.md`, opened as a `do-not-merge`
  labelled draft PR; terminal flag `HUMAN_GATED=true`. Never auto-merge either variant.
- **Lane 0** → code-side mitigation ships in Lane A; the precise out-of-band action surfaces as
  `HUMAN_ACTION_REQUIRED:<finding-id>` in `docs/arch-ops-actions.md`; terminal flags
  `CODE_CLOSED=true, OPS_QUEUED=true`.

## ROLE PIPELINE
- PHASE 0: @claude REVIEWER produces findings FROM THE CODE → @codex SKEPTIC narrows/refutes
  AGAINST THE CODE → freeze.
- PHASE 1 (Stage-9 final form, Aula prompt 24, prompts.md L3013): @codex BUILDS each fix; a
  FRESH BUILD-BLIND @claude reviews each fix PR (different terminal session than any prior
  @claude that touched this run; cross-vendor reviewer rule); @claude INTEGRATES (opens PR,
  conflict-aware merge, worktree cleanup). @codex never reviews its own work; the reviewer
  @claude never writes code; the integrator never authors fixes.

## LEDGER
Engine definition: see `engine.md` → FROZEN-ARTIFACT CLOSE TEST (EVID). The engine defines EVID as
the standard close-test boolean for any frozen-artifact item; this mission's ledger uses it.

`docs/arch-build-progress.md`. PHASE marker (REVIEW | REVIEW_FROZEN | FIXING | VERIFY); a FINDING
CLOSE-INDEX (every confirmed ID by wave, with its `lane: A|B|0`, in state
`OPEN | CLOSED via PR#n | CODE_CLOSED via PR#n (OPS: …) | HUMAN_GATED via PR#n`); per-fix-task rows
with flags `CODED EVID PR_OPEN REVIEWED MERGED ACCEPT`; an OPS/VERIFY-AT-SCALE list + recorded
decisions. Example EVID repro (mission-specific): the worker re-runs the EXACT command from the
finding's Evidence block (the `curl` that returned the 500, the test that asserted the wrong
value, the script that reproduced the race) and sets `EVID=true` only when it no longer reproduces.

## TASK STRUCTURE
- **P0-REVIEW [@claude, Opus-class]** — CODE-GROUNDED adversarial review (read the actual source;
  IGNORE any existing review docs). Cover reliability, concurrency, security, data model,
  cost/abuse, coupling, ops blind spots, version hygiene. Per finding: area-prefixed ID, severity
  P0-P3, problem with PUBLIC file:line evidence from the code, concrete FIX + which in-tree
  primitive to reuse, acceptance criteria, CODE vs CODE+OPS tag. Plus: dependency-ordered ranking
  (mark FOUNDATION), root-cause CLUSTERS drafted from shared causes, hot-file collision map,
  validated-strengths do-not-touch list. Each cluster must be tagged `FOUNDATION|INDEPENDENT` with
  a `touches:` file-list and `CLOSES=[ids]`. Output docs/adversarial-review-fresh.md.

  **SCHEMA-VERIFIED FINDINGS (machine-checkable counterpart):** alongside the markdown review doc,
  the reviewer emits a JSON findings document conformant to
  `autonomous-fleet-core/assets/fleet-review-findings.schema.json` at
  `.fleet/runs/<run_id>/p0-review-findings.json`. Each finding's `evidence.quoted_line` MUST be the
  EXACT verbatim line from the cited source file. The coordinator immediately runs
  `python scripts/verify_findings.py .fleet/runs/<run_id>/p0-review-findings.json --repo <REPO_ROOT>
  --write --summary-out .fleet/runs/<run_id>/p0-verify-summary.json`. If exit != 0 (schema error or
  unverified finding), the run HALTS at P0-REVIEW — unverified findings are likely reviewer
  hallucination and MUST NOT enter the fix loop. The reviewer either fixes the quotes and re-emits,
  or omits the unverified findings. See `autonomous-fleet-core/references/review-findings.md` for the
  full protocol.
- **P0-SKEPTIC [@codex, fresh, gated on P0-REVIEW]** — stress every finding AGAINST THE CODE
  (open each cited file:line; verify it's real, severity right, Fix sound, named primitive
  exists, won't break a strength). Produce CONFIRMED (with narrowed scope) and REFUTED/DO-NOT-FIX
  sets. Finalize root-cause CLUSTERS over the CONFIRMED set, preserving `FOUNDATION|INDEPENDENT`,
  `touches:`, and `CLOSES=[ids]`. Update the doc inline. Set PHASE=REVIEW_FROZEN. Confirmed =
  Phase 1 spec; refuted = never fixed.

  Emit a parallel JSON skeptic doc at `.fleet/runs/<run_id>/p0-skeptic-findings.json` carrying ONLY
  the CONFIRMED set, same schema as P0-REVIEW. Re-run `scripts/verify_findings.py` against it; exit
  != 0 halts (a CONFIRMED finding whose quote no longer locates means the skeptic narrowed scope
  past the original line — re-cite or drop).
- **BOOTSTRAP** — transcribe confirmed finding IDs into the ledger CLOSE-INDEX (waves from the
  ranking: P0s first, then FOUNDATION, then rest); apply the THREE-LANE REMEDIATION classification;
  register Lane A fix tasks in the ledger and SYNC_TASK_STATE(ready) via the active adapter (create
  native tasks if the adapter supports them). Lane B and Lane 0 findings become named decision or
  human-action records, not auto-merged fix tasks. Set PHASE=FIXING.
- **FIX LOOP [Phase 1]** — P0s first, FOUNDATION early, parallel across non-colliding files, one
  in-flight task per hot file. Each fix runs the engine's PR-per-task pipeline (CODE→PR→REVIEW→
  FIX→SHIP conflict-aware). Before OPEN_PR, the builder re-runs the EXACT reproduction from the
  finding's Evidence block and sets `EVID` only when it no longer reproduces. Reviewer independently
  re-runs the same Evidence reproduction and re-demonstrates each finding's acceptance. Fix a
  FOUNDATION cluster's root cause once; dependent findings in that cluster's `CLOSES=[ids]` inherit
  closure through the same PR when their Evidence and acceptance gates pass.

  When schema-verified findings are in use, the FIX LOOP consumes ONLY the verified set from
  `.fleet/runs/<run_id>/p0-skeptic-findings.json` (i.e. findings where `verified: true`). A finding
  with `verified: false` is held for manual operator inspection — never fed to a builder. This is
  the corpus-grounded counter to reviewer hallucination: the orchestrator gates the loop, not the
  builder's good faith.

  **ANTI-ANCHORING — fresh build-blind reviewer commits its blind fix BEFORE reading the PR diff
  (engine.md ANTI-ANCHORING).** When a builder's PR is handed to the fresh @claude reviewer, the
  reviewer FIRST reads only the finding (the cited file:line + cascade paths from the schema-
  verified findings doc), forms an independent hypothesis about the correct point-of-creation fix,
  and writes that blind fix to `.fleet/runs/<run_id>/reviewer-blind-fix-<finding-id>.md` BEFORE
  opening the candidate PR diff. The blind-fix file names: the point of creation
  (file:function:line), the shape of the change, and the reviewer's pre-commit confidence (0-100).
  Only AFTER the blind fix is committed to disk does the reviewer open the candidate diff. The
  review then compares the candidate to its pre-committed blind fix; a candidate at a different
  call-stack depth than the blind fix triggers the ROOT_CAUSE_DEPTH HARD RULE and the reviewer
  emits a `category: root_cause_depth` finding (with `cascade_impact` listing the other paths
  the root cause still triggers — schema-required). A blind-fix file whose mtime is AFTER the
  candidate-findings file means the protocol was violated; the coordinator surfaces this and
  re-runs review on the affected PR.
- **T-FINAL [@claude]** — build green, lint clean, full suite green incl. added tests; every
  confirmed finding CLOSED or CODE_CLOSED(+OPS recorded). Output `docs/arch-build-readiness.md`
  starting with **`fleet-outcome` YAML** (`p0_open`, `p1_open`, `findings_open`, `ops_queue_count`;
  see fleet-outcome.md), then finding status, OPS queue, **Recommended next missions**, all PRs.
  When schema-verified review findings were emitted, also surface
  `verified_findings`, `unverified_findings`, `auto_applicable_findings`, and
  `human_gated_findings` in the metrics block (sourced from
  `.fleet/runs/<run_id>/p0-verify-summary.json`). `unverified_findings == 0` is a HARD precondition
  for `status: done` — a T-FINAL that ships with unverified findings still in flight is a
  reviewer-hallucination leak and MUST be `status: partial` instead.

  **ROOT_CAUSE_DEPTH attestation (engine.md ROOT_CAUSE_DEPTH).** Set top-level
  `root_cause_audited: true` in the fleet-outcome WHEN every `category: root_cause_depth` finding
  closed in this mission had its `cascade_impact` paths re-EVIDed by the builder (each cited
  cascade path's own reproduction was run and stopped reproducing). Set `root_cause_audited: false`
  if any cascade path was deferred to a follow-up mission (which MUST then appear in
  `deferred_missions`). Omit the field entirely when no root-cause-depth findings were filed.
  This makes the discipline auditable across runs without bloating non-applicable readiness docs.

  **Run-archive manifest (engine.md ARCHIVE_ENABLED).** Before opening the final PR, T-FINAL
  writes `manifest.json` to the run's archive directory `.fleet/runs/<run_id>/` by walking the
  directory and emitting one entry per first-class artifact (every findings JSON, verifier
  summary, blind-fix file, prompt, response, diff, this readiness doc, the progress doc). Use
  `python scripts/lib/fleet_run.py` style — typically driven by a worker step that calls
  `fleet_run.write_manifest(archive_root, run_id=..., mission='adversarial-review-and-fix',
  files=[...])`. Then run `python scripts/validate_run_archive.py .fleet/runs/<run_id>/`. The
  validator enforces three mtime-ordering invariants from Commits 1-3 disciplines: blind_fix
  before findings (per producer), verify_summary after findings, readiness with the latest mtime
  in the archive. A validator that exits non-zero means the discipline is unsatisfied — fix the
  archive (re-create the missing/re-order the misplaced file) and re-emit the manifest before
  shipping. Set top-level `archive_enabled: true` in the fleet-outcome ONLY after the validator
  passes; also set top-level `run_id: <run_id>` so post-hoc tools (INFLATION POST-MORTEM,
  dashboards) can jump straight to the archive. `archive_enabled: false` is incompatible with
  `status: done` — the fleet-outcome validator rejects that combination (the archive IS the
  audit trail). Missions that emitted no first-class artifacts (rare for adversarial-review-and-
  fix — should never happen) OMIT both fields rather than asserting them false.

  Ship as the final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/arch-build-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission adversarial-review-and-fix DONE: docs/arch-build-progress.md all task flags true,
docs/arch-build-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Review frozen; every confirmed finding CLOSED or CODE_CLOSED(+OPS recorded); every fix task
terminal; docs/arch-build-readiness.md exists. Terminal state = engineering landed on BASE + OPS
queue surfaced — NOT deployed, NOT promoted to main. Then send the FINAL report.

## FIX-ONLY MODE — when the review is already done
Source: Stage-9 prompt 25 (Fix-Only Variant), prompts.md L3015-L3017. This is the most-recurring
real shape across prompts 19-24 — each was a specialization of this generic fix-only template
against a specific real audit. When the user supplies `__REVIEW_DOC__` (e.g. an existing adversarial
review markdown, an audit dossier, a frozen finding set), enter FIX-ONLY MODE:

- **SKIP Phase 0 entirely** — no P0-REVIEW, no P0-SKEPTIC, no re-reviewing the code. The supplied
  `__REVIEW_DOC__` IS the frozen source of truth; reinterpretation is forbidden.
- **BOOTSTRAP from `__REVIEW_DOC__`** — coordinator ingests `__REVIEW_DOC__`, transcribes every
  finding ID into the CLOSE-INDEX verbatim (no renumbering, no silent dropping), classifies each
  into Lane A / B / 0 per the engine's LANE PATTERN, and derives the wave order and hot-file map
  from the doc if it doesn't already state them.
- **Run only Phase 1** — fix → PR → fresh build-blind review → merge per the engine's PR-per-task
  pipeline. The EVID gate (engine: FROZEN-ARTIFACT CLOSE TEST) still applies: every finding closes
  only when its own Evidence repro stops reproducing.
- **Cross-vendor reviewer rule still holds** — the fresh build-blind reviewer for Phase 1 is the
  Stage-9 final-form @claude reviewer (different terminal session than the @codex builder; handed
  the diff + acceptance contract as TEXT ONLY; must not have seen the build conversation).
- **Fresh-run semantics retarget to fix-only** — ignore prior fix ledgers and in-flight fix
  branches; start a clean ledger and a clean BASE off the default branch at current HEAD.
- **Empty/missing `__REVIEW_DOC__` is a hard surface, not a spin-up** — if the supplied doc is
  missing, empty, or has no confirmed findings, the coordinator surfaces it as a hard gate to the
  user rather than spinning up a fix run with nothing to fix.

## DECISION DEFAULTS (mission-specific)
- The review is grounded in the CODE, not any existing doc. Phase 1 converges to CONFIRMED Fixes;
  never fixes a REFUTED non-issue.
- REUSE in-tree primitives over new infra wherever the review names one.
- KEEP validated strengths — close findings around them, never refactor them.
- Findings needing load/prod data the swarm can't see → ship code + plan, mark CODE_CLOSED +
  VERIFY_AT_SCALE; never block the loop.
- One in-flight task per hot file; the BASE→main promotion and any OPS apply are human-owned and
  out of scope.
- Fixes must be exercised the way production runs them, not just CI-green. Use
  `docs/secure-ship-e2e.md` as the caution rail: validation is not terminal evidence unless it
  traverses the same invocation, wiring, and result path production uses.
- Fixing a FOUNDATION cluster's root cause once closes its dependent findings only when the shared
  PR satisfies every dependent finding's Evidence and acceptance gates; mark inherited dependents
  `CLOSED via PR#n`.
- Any ambiguity → close the finding most faithfully to its Fix while keeping the loop
  terminating, the prod path safe, the strengths intact, history clean.
