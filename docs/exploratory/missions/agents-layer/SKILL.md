---
name: agents-layer
description: >-
  [Tier 3 · one-axis stub→live cutover · full review gate] Fill the live implementation of the
  agent/service seam recorded in docs/build-plan.md, swapping the frozen stub for the configured
  agents framework (default eve) one seam-member-group at a time, behind the exact contract the
  stub froze, then remove the stub. Use after the build plan is frozen and the typed depth is
  done; acceptance is contract-tested against the stub fixtures plus local evals, with live
  deploy left to OPS. NOT for deriving the seam (scaffold-align owns that) and NOT for building
  typed API/data/UI depth (contract-first-build owns that); this mission only wires the live impl
  and cuts over the selector. Runs via the autonomous-fleet-core engine. Trigger on: "wire the
  live agents layer", "swap the agent stub for the real framework", "cut the agent seam over to
  live", "implement the agents framework behind the stub".
license: MIT
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "3"
  fleet-component: "mission"
---


# Mission: agents-layer

This mission performs a one-axis stub→live cutover of the agent/service seam frozen by
scaffold-align in `docs/build-plan.md`. It fills the seam's live implementation with the
configured agents framework, one seam-member-group at a time, keeping the hardened stub fixtures
as the behavioural acceptance contract: live must satisfy the SAME fixtures the stub does before
the selector flips to live. The discipline that makes it converge is the frozen contract — the
seam interface and its fixtures do NOT change here; only the implementation behind them does, and
the stub is removed only after live passes every fixture.

## When to use

- After scaffold-align has frozen `docs/build-plan.md` and the seam's live impl row (§ Work areas,
  layer `agents-live`) is still OPEN.
- After contract-first-build has closed the typed-depth rows, so the only remaining seam impl is
  the stub (typically when the prior node reports `stubs_remaining == 0` or `in_items_open == 0`).
- When the live agents layer must satisfy the exact contract the stub froze, with deploy deferred
  to OPS.

Not when: the seam itself is not yet frozen (run scaffold-align first), or the work is typed
API/server/data/auth/payments/ui depth against the stub (that is contract-first-build). This
mission is the LAST of the three; it wires live and cuts over, nothing else.

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`
(this is the `agents` node of the `handoff-to-product` campaign).

## Optional skills

Activate only when the trigger applies. At most 2 active; coordinator-only.

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `cso` | The live impl handles untrusted input or credentials and needs a security read before cutover | Use the seam's boundary rule + addy `security-and-hardening` at the worker |
| `health` | User wants a composite score on the live-wired repo before the final cutover | Use the frozen invariants in `docs/build-plan.md` as the bar |

## Worker skills

Inject per role on DISPATCH (workers load these; coordinator does not). Verified ids only.

| Role | Skills | If unavailable |
|------|--------|----------------|
| @builder (wire live impl) | the configured agents framework (default eve) — e.g. `defineAgent` / `defineTool` / `eveChannel` / `routeAuth` / `defineEval` — as the live-impl reference for the framework recorded in `docs/build-plan.md` § Handoff sources | Installed framework's own docs at the pinned version |
| @builder (verify signatures) | addy `source-driven-development` — MANDATORY: read the framework's installed pinned source/types, not training memory, before writing against any `define*` primitive | Framework changelog + types in `node_modules` |
| @builder (model the live boundary) | matt `codebase-design`; addy `api-and-interface-design` | § Seam contract member list in `docs/build-plan.md` |
| @builder (stub removal) | addy `deprecation-and-migration` | Grep every reference to the stub impl file before deleting |
| @builder (live evals) | the configured framework's eval primitive (default eve `defineEval`) | Local fixture-driven assertions against the stub fixtures |
| @reviewer | — | Mission gate: live satisfies the stub fixtures, selector flips, stub gone |

## Deferred missions

Record in `docs/agents-layer-readiness.md` under **Recommended next missions** and in
DECISIONS.md. Do not start another mission in the same run.

| Finding type | Route to |
|--------------|----------|
| Live impl needs an interface change (build plan is frozen) | record finding, `status: blocked` — defer; do not widen the seam here |
| Design polish on agent-facing UI surfaced while wiring | `design-integration` |
| Live behaviour reveals a contract/data bug behind the seam | `adversarial-review-and-fix` |
| Eval/fixture coverage gap on a wired member | `test-coverage` |
| Framework setup/run docs drifted after wiring | `doc-sync` |

**Empirical note:** filling a live agents implementation is feature/cross-module work with no
direct category in arXiv 2601.15195, so expect rework — a full review gate is required. The single
control that makes it converge: the stub fixtures frozen by scaffold-align ARE the acceptance
contract; live is correct when it passes the same fixtures the stub passed, member by member.

## CORE TENSION (read first)

"Make the agents real" is open-ended and tempts a rewrite of the boundary. The fix is to treat
this as ONE axis: the seam interface and its fixtures (frozen in `docs/build-plan.md`) are held
constant, and only the implementation behind them moves from stub to live. The stub is the "old
axis" — it is removed only after the live impl satisfies every fixture the stub satisfied. If the
contract turns out to be wrong, that is a finding for scaffold-align, not a license to re-derive
the seam here.

## GOAL

Cut the agent/service seam over from stub to live: fill the live implementation file (recorded in
`docs/build-plan.md` § Seam contract) using the configured agents framework, wire EVERY member of
the seam interface (the member list in § Seam contract), keep the stub fixtures as the acceptance
contract (live passes the same contract test the stub passes), flip the selector default to live
in the cutover, and remove the stub once live is green. Stand up the agent orchestration as a
separate project where the configured framework requires it. The gate is code-complete
(`seam_unwired_open == 0`), NOT a live deploy — deploy stays an OPS item. Behaviour and every
other axis are preserved exactly: no interface change, no typed-depth rework.

## ROLE PIPELINE

- @builder WIRES each seam-member-group's live impl against the framework and the frozen fixtures,
  and codes the cutover (selector flips to live in tests). Graded only against the frozen
  invariants and the stub fixtures.
- @reviewer REVIEWS each PR (fresh, build-blind): the wired members satisfy the SAME fixtures the
  stub did, no `any` crosses the boundary, the interface is untouched, nothing other than the live
  impl + selector changed, suite green, no half-wired reachable state.
- @integrator (the coordinator) opens the PR, merges (conflict-aware), cleans the worktree.

## LEDGER

`docs/agents-layer-progress.md`. Per-task flags: `MIGRATED=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f>
MERGED=<t/f>`. Plus a MIGRATION INDEX whose rows are the seam members to wire live (from § Seam
contract member list) grouped into member-groups, each `OPEN | DONE via PR#n`, PLUS the
stub-removal item (`OPEN | DONE via PR#n`). The index is frozen from the build plan — it is not
re-derived.

## TASK STRUCTURE

- **T-READ-PLAN [@builder/coordinator]** — load `docs/build-plan.md`: read § Seam contract (the
  interface file, the interface name, the selector env var + values that pick stub vs live and the
  file that reads it, the stub impl file, the live impl file, the contract types module, the full
  MEMBER LIST, the streaming/event surface, the boundary rule) and § Invariants (the build/
  typecheck/lint/test commands and the "stub implements every member" + "selector defaults to
  stub" checks). Also read § Handoff sources for the configured agents framework, and
  `docs/agents/fleet-config.md` for `agents_framework` (default eve) and its pinned version. Locate
  the hardened stub fixtures scaffold-align added in its T-HARDEN — these ARE the acceptance
  contract. Do NOT re-derive any of this. Build the MIGRATION INDEX from the member list +
  stub-removal item. If a build-plan fact is wrong (member missing, file path stale, selector not
  as recorded), record a finding and set `status: blocked`; do not silently re-derive.
- **T-FOUNDATION [@builder]** — stand up the configured agents framework ALONGSIDE the stub
  (install at the pinned version, base config, auth/channel wiring the framework needs), as a
  separate orchestration project where the framework requires it. Read the framework's installed
  source/types (source-driven-development) before writing against any `define*` primitive. The
  selector still defaults to stub; nothing is cut over yet. Gates the per-member wiring.
- **T-WIRE… [per seam-member-group, loop]** — each member-group is one PR. @builder fills the live
  impl for those members so it satisfies the SAME stub fixtures (the contract test that asserts the
  interface is satisfied now runs against live with the selector flipped to live in that test),
  matching the streaming/event surface where § Seam contract records one. No interface change; no
  `any` crosses the boundary (adapt live framework shapes inside the impl). @reviewer reviews
  (live passes the stub fixtures, behaviour preserved, interface untouched, only live impl +
  test-selector changed) → @integrator merges. Parallelize independent member-groups in separate
  worktrees; serialize members that share live state. Update the MIGRATION INDEX.
- **T-CLEANUP [@builder]** — once EVERY member is wired and live passes all fixtures, flip the
  selector default to live in app config, then remove the stub impl (the "old axis"): delete the
  stub file and any stub-only dead code, confirm nothing references it (grep the stub impl path),
  and keep the stub fixtures wired to the live contract test as the standing acceptance. One PR.
- **T-FINAL [@integrator]** — build + lint + full suite green; the contract test passes against
  live for every member; local evals pass; the selector defaults to live; the stub is gone and
  unreferenced; live deploy remains an OPS item (not gated here). Output
  `docs/agents-layer-readiness.md` starting with the **`fleet-outcome` YAML** block
  (`migration_items_open`, `seam_unwired_open`, `old_axis_removed`, `evals_passing`,
  `deploy_pending_ops` in metrics; see `autonomous-fleet-core/references/fleet-outcome.md`), then
  the migration summary + **Recommended next missions**. Ship as the final PR.

The `fleet-outcome` block T-FINAL writes:

```yaml
---
fleet-outcome:
  mission: agents-layer
  status: done            # blocked if seam_unwired_open > 0 or a build-plan fact was wrong
  repo: <REPO_ROOT>
  base_branch: <BASE>
  prs_merged: <n>
  metrics:
    migration_items_open: 0   # MIGRATION-INDEX rows still OPEN (members + stub-removal)
    seam_unwired_open: 0      # seam members not yet satisfied by the live impl — the GATE
    old_axis_removed: true    # stub impl deleted and unreferenced
    evals_passing: true       # local evals + the contract test green against live
    deploy_pending_ops: true  # live deploy deferred to OPS (bool; not gated by this mission)
  deferred_missions:
    - id: doc-sync
      reason: "..."
      blocker: null
---
```

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/agents-layer-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission agents-layer DONE: docs/agents-layer-progress.md all task flags true,
docs/agents-layer-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE

Every MIGRATION-INDEX item `DONE` (every seam member wired live + the stub-removal item), every
task `MIGRATED=t PR_OPEN=t REVIEWED=t MERGED=t`, `docs/agents-layer-readiness.md` exists, the live
impl satisfies the stub fixtures for every member, the selector defaults to live, the stub is gone
and unreferenced, build + suite + local evals green. `seam_unwired_open == 0`. Then send the FINAL
report.

## DECISION DEFAULTS (mission-specific; on top of the engine's)

- Read every per-product fact from `docs/build-plan.md` (§ Seam contract, § Invariants, § Work
  areas) and the configured framework + version from `docs/agents/fleet-config.md`. Never hardcode
  a member count, interface name, file path, selector name, or framework name in the work itself.
- A build-plan fact that is wrong (member missing from the interface, stale path, selector not as
  recorded, fixture that does not match the contract) → record a finding and set `status: blocked`.
  Do not re-derive the seam; that is scaffold-align's job.
- Change ONLY the implementation axis: fill the live impl file and flip the selector. Do NOT modify
  the interface, the contract types, or the typed depth contract-first-build built. If live depth
  genuinely needs an interface change, that is a finding (the build plan is frozen), not an edit.
- The stub fixtures are the acceptance contract: live is correct when it passes the SAME fixtures
  the stub passed. Verify framework signatures against the installed pinned source before writing
  against them (source-driven-development is mandatory; the stack is likely newer than training).
- Remove the stub only AFTER every member is wired live and passes its fixtures; never leave a
  half-wired reachable state. Keep the stub fixtures wired to the live contract test after removal.
- The gate is code-complete (`seam_unwired_open == 0`), not a live deploy. Leave deploy as an OPS
  item with `deploy_pending_ops: true`; do not block the mission on infrastructure.
- Commit as the discovered MAINTAINER; no `Co-authored-by` / "Generated with" / agent trailers.
- Any ambiguity → the cutover path that keeps the suite green and the seam contract intact while
  wiring one member-group at a time.