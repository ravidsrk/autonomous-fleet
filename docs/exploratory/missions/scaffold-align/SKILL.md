---
name: scaffold-align
description: >-
  [Tier 1 · verification-led · safe to run unattended] Self-orient to a design+spec handoff,
  certify the scaffold builds green, certify the agent/service seam (its typed stub/live
  boundary) and HARDEN the stub so it exercises the WHOLE contract, then FREEZE
  docs/build-plan.md as the single handoff artifact the downstream build missions consume. This
  is verification and freeze work only: it confirms the scaffold typechecks, lints, and builds
  via the repo's own scripts, enumerates the seam, and records discovered per-product facts in
  the artifact. NOT for building product depth (that is contract-first-build) and NOT for wiring
  the live agents impl (that is agents-layer) — it leaves the seam stubbed and the live impl
  untouched. Runs via the autonomous-fleet-core engine. Trigger on: "align the scaffold",
  "freeze the build plan", "certify the handoff", "prep this handoff for the fleet", "orient to
  the design+spec handoff".
license: MIT
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "1"
  fleet-component: "mission"
status: exploratory
---

> **Status: exploratory.** This mission is documented but has not yet been run end-to-end on an external repo with an archived run-archive. It is preserved for future promotion (see `docs/exploratory/missions/README.md` § Promotion criteria). Do not invoke this skill in a production fleet until it has been promoted.


# Mission: scaffold-align

Self-orient to a design+spec handoff, prove the scaffold is green, certify the agent/service
seam, and freeze `docs/build-plan.md` so the build missions never re-derive per-product facts.
The discipline that makes it converge: discover, do not assume; every product-specific fact
(paths, names, member counts, vendors) is READ off the handoff and the repo and written into the
artifact, never asserted in this mission. One writer, one frozen artifact, then stop.

## When to use

- Before any build mission runs against a freshly scaffolded handoff (a repo on the configured
  scaffold convention with a design reference and a product spec under `docs/`, plus an
  agent/service seam: an exported interface with a stub impl and a live impl selected by an env
  flag).
- When `docs/build-plan.md` does not yet exist, or the handoff changed and the plan must be
  re-frozen before building resumes.
- After `setup-autonomous-fleet` has recorded `scaffold_convention` and `agents_framework` in
  `docs/agents/fleet-config.md`.

Not when: the plan is already frozen and you want typed depth → use `contract-first-build`. Not
when the agents seam needs its live impl wired → use `agents-layer`. This mission leaves the seam
stubbed.

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program` (see the `handoff-to-product` campaign).

## Optional skills

Activate only when the trigger applies. Do not load unrelated catalog skills. Coordinator-only, max two active.

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `design-review` | The design reference is ambiguous and the seam needs a visual check before freezing tokens | Record the ambiguity in build-plan § Key decisions and freeze the most literal reading |
| `diagram` | The seam/architecture is non-obvious and a map helps verify the boundary before freezing | Describe the boundary in prose in build-plan § Seam contract |

## Worker skills

Inject per role on DISPATCH (workers load these; coordinator does not). Use only verified ids.

| Role | Skills | If unavailable |
|------|--------|----------------|
| @builder (certify scaffold, harden stub) | addyosmani `source-driven-development` (MANDATORY — the scaffold stack is newer than training data; read source, not memory), addyosmani `test-driven-development`, mattpocock `domain-modeling`, mattpocock `codebase-design` | The repo's own scripts + the interface source as ground truth |
| @builder (seam fixtures + contract test) | mattpocock `tdd`, addyosmani `api-and-interface-design` | The interface members as the test oracle |
| @reviewer (certify the freeze) | gstack `review` | Mission gate: build green + every interface member exercised |
| @integrator (ship) | — | Mission gate |

## Deferred missions

Record in `<LEDGER_DIR>/scaffold-align-readiness.md` under **Recommended next missions** and in DECISIONS.md.
Do not start another mission in the same run.

| Finding type | Route to |
|--------------|----------|
| Typed product depth to build against the frozen plan | `contract-first-build` (next campaign node) |
| Live agents impl to wire into the seam | `agents-layer` (after the build node) |
| Design reference diverges from the scaffolded UI | `design-integration` |
| Spec reveals a security gap in the scaffold | `adversarial-review-and-fix` |
| Scaffold's own docs are stale vs the code | `doc-sync` |
| Scaffold deps carry advisories | `dependency-update` |

**Empirical note:** there is no direct task category for scaffold/freeze work in arXiv 2601.15195,
but this mission is verification-led with a low blast radius (it confirms green, enumerates a
boundary, and writes one doc), so it is safe to run unattended. The control that matters is the
FROZEN artifact: `docs/build-plan.md` is what every downstream mission inherits, so the seam
member enumeration and the invariants are the things to eyeball.

## GOAL

Certify the scaffold builds green (typecheck, lint, build via the repo's own scripts), certify the
agent/service seam exercises its WHOLE contract through the stub (every member, every event and
variant the live impl must later produce, each with a realistic fixture and a contract test that
asserts the stub implements the entire interface), and FREEZE `docs/build-plan.md` per the artifact
schema below with every Work-areas row OPEN. After this mission, a downstream builder can build
typed depth or wire the live impl against the artifact alone, never re-deriving the handoff. If the
scaffold will not go green, or the seam cannot be enumerated and frozen, set status `blocked` —
do not freeze a plan over a red scaffold.

## ROLE PIPELINE

- @builder CERTIFIES the scaffold (runs the repo's typecheck/lint/build; fixes minimally if red)
  and HARDENS the stub (every interface member exercised, realistic fixtures, a contract test that
  the stub implements the whole interface), then drafts `docs/build-plan.md`.
- @reviewer REVIEWS each PR fresh and build-blind, graded only against the frozen invariants and
  the seam member list: scaffold green, every interface member covered by a fixture, the contract
  test asserts whole-interface implementation, the selector defaults to stub, no live impl touched,
  no product-specific fact invented (all read off the handoff or repo).
- @integrator SHIPS: opens the PR, merges (conflict-aware), cleans the worktree.

## LEDGER

`<LEDGER_DIR>/scaffold-align-progress.md`. Per-task flags: `CHECKED=<t/f> BUILT=<t/f> REVIEWED=<t/f>
MERGED=<t/f>`. Plus the frozen ALIGN INDEX: the invariant checklist (each invariant `OPEN | GREEN`)
and the seam-member coverage list (every interface member `UNCOVERED | FIXTURED via PR#n`). The
ALIGN INDEX is closed only when every invariant is GREEN and every seam member is FIXTURED.

## TASK STRUCTURE

- **T-ORIENT [@builder]** — self-orient to the handoff, no placeholders. Read the design reference
  and the product spec under `docs/`; read `docs/agents/fleet-config.md` for `scaffold_convention`
  (default better-t-stack) and `agents_framework` (default eve) and adapt to those. FIND the seam:
  the exported interface whose two implementations are chosen by an env flag, one a stub with
  fixtures and one a live impl (the live impl may not exist yet). FIND the design tokens and the
  contract types module the interface references. Record the discovered build/test/lint/typecheck
  commands (derived in SELF-ORIENTATION) and the handoff sources. This is the only discovery task;
  it produces no answer in mission text, only entries for the artifact. Example (illustrative only,
  your repo will differ): in a typical better-t-stack handoff the seam interface lives in a
  `packages/shared` module and the selector is a stub|live enum read in the server's env module,
  but you discover the actual paths and names, never assume them.
- **T-CERTIFY [@builder]** — confirm the scaffold is green using the repo's own scripts: typecheck,
  lint, and build all pass; the test command runs and passes. If red, fix minimally (the smallest
  change that makes the scaffold green, no product depth). Record each command + its green result
  as an invariant. If the scaffold cannot be made green with a minimal fix, set status `blocked`
  and stop — do not freeze a plan over a red scaffold. Sets the `check_green` metric.
- **T-HARDEN [@builder]** — extend the stub so EVERY member of the seam interface is exercised and
  has a realistic fixture covering every event and variant the live impl must later produce (the
  whole contract, not the happy path). Add a contract test that asserts the stub implements the
  entire interface (every member present, signatures conform) and that the selector defaults to
  stub. Do NOT touch the live impl file and do NOT widen the interface. These fixtures + this
  contract test ARE the behavioral acceptance contract `agents-layer` later checks the live impl
  against. Update the seam-member coverage list as each member becomes FIXTURED.
- **T-FREEZE [@builder]** — write `docs/build-plan.md` per the artifact schema below: Handoff
  sources, Seam contract (with the complete MEMBER LIST table — the count is whatever was
  discovered, never asserted here), Invariants (the green commands from T-CERTIFY + the stub-
  implements-interface and selector-defaults-to-stub checks from T-HARDEN), Work areas (one OPEN
  row per build area, layer tagged), Key decisions (discovered stack facts by role), and the
  verbatim Consumption contract. FREEZE the file: this mission is the only writer; downstream
  missions consume it read-only. Sets the `seam_frozen` metric.
- **T-FINAL [@integrator]** — build, lint, and the full suite green; every ALIGN-INDEX invariant
  GREEN and every seam member FIXTURED; `docs/build-plan.md` exists and is internally consistent.
  Write `<LEDGER_DIR>/scaffold-align-readiness.md` LED BY the **`fleet-outcome` YAML** block (metrics
  `align_items_open`, `check_green`, `seam_frozen`, `scaffold_ok`; see
  `autonomous-fleet-core/references/fleet-outcome.md`), then the align summary and **Recommended
  next missions**. Ship as the final PR.

## BUILD-PLAN ARTIFACT SCHEMA (frozen by T-FREEZE)

`docs/build-plan.md` is the single home for every per-product fact. Exact H2 layout, in order:

```markdown
# Build plan

Frozen handoff contract for <product>. Downstream missions consume this; they do NOT re-derive.
Written by scaffold-align on <date>.

## Handoff sources
- design reference: <discovered path>
- product spec: <discovered path(s) under docs/>
- scaffold convention: <scaffold_convention from fleet-config, default better-t-stack>
- agents framework (configured): <agents_framework from fleet-config, default eve>

## Seam contract
- interface file: <discovered path>
- interface name: <discovered exported interface symbol>
- selector: <env var + values that pick stub vs live> read in <discovered file>
- stub impl file: <discovered path>
- live impl file: <discovered path, may not exist yet>
- contract types module: <discovered path holding the request/response/model types>
- MEMBER LIST: a table, one row per interface member —
  `member | signature (params -> return) | one-line purpose`
  (the complete enumeration of the boundary; the count is whatever was discovered)
- streaming/event surface: <discovered event type/channel, else "none">
- boundary rule: <verbatim from the interface's doc comment if present, else
  "no `any` crosses this boundary; adapt live shapes here">

## Invariants
Numbered. Each = one shell-checkable assertion + the command that checks it. MUST include:
1. build command green
2. typecheck/lint green
3. test command green
4. the stub implements every interface member (contract test passes)
5. the selector defaults to stub
(downstream missions turn the relevant subset into per-task acceptance)

## Work areas
`area | layer (api|server|data|auth|payments|ui|agents-live) | depends-on-seam-members |
spec source (file#section) | design source | status (OPEN)`
(one row per build area; all frozen OPEN here)

## Key decisions
Mirror of the relevant DECISIONS.md entries: stack facts discovered (framework versions, db, auth
lib, payments lib — by ROLE, not as normative claims), the chosen selector default, anything
adapted because the repo diverged from the convention.

## Consumption contract
contract-first-build builds typed depth for every Work-areas row whose layer != agents-live,
against the Seam contract + stub fixtures, and MUST NOT touch the live impl file or widen the
interface. agents-layer fills the live impl file for the agents-live row using the configured
agents framework, keeping the stub fixtures as the acceptance contract, then removes the stub.
Neither mission re-derives anything above; if a fact here is wrong they record a finding and set
status: blocked rather than silently re-deriving.
```

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `<LEDGER_DIR>/scaffold-align-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission scaffold-align DONE: <LEDGER_DIR>/scaffold-align-progress.md all task flags true,
<LEDGER_DIR>/scaffold-align-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE

Every ALIGN-INDEX invariant `GREEN` and every seam member `FIXTURED`, every task
`CHECKED=t BUILT=t REVIEWED=t MERGED=t`, `docs/build-plan.md` frozen with every section populated
and every Work-areas row OPEN, `<LEDGER_DIR>/scaffold-align-readiness.md` exists, the scaffold builds green,
and the live impl is untouched (the seam is still stubbed). Then send the FINAL report.

## DECISION DEFAULTS (mission-specific; on top of the engine's)

- DISCOVER, never hardcode. Every per-product fact (paths, interface name, member list and its
  count, selector flag, db/auth/payments vendors) is read off the handoff and the repo and written
  into `docs/build-plan.md`. Never assert a count or a name in mission output; reference the seam
  by role and where it is recorded.
- Read stack convention from config. `scaffold_convention` and `agents_framework` come from
  `docs/agents/fleet-config.md` (defaults better-t-stack and eve). If the repo diverges from the
  convention, adapt to the intent and record why in § Key decisions (per the engine MISSION-FIT
  check).
- Recognize the seam by shape, not by name: an exported interface whose two implementations are
  selected by an env flag, one a stub with fixtures, one live. If no such boundary exists, the
  handoff does not match this mission — record a finding and set status `blocked`.
- Harden to the WHOLE contract, not the happy path. The stub must produce every event and variant
  the live impl will, because those fixtures become `agents-layer`'s acceptance contract.
- Do not build product depth and do not touch the live impl file. Minimal fixes to make the
  scaffold green are allowed; anything beyond is a Work-areas row for `contract-first-build`.
- Gate is hard: scaffold not green (`check_green` false) or seam not freezable (`seam_frozen`
  false) → status `blocked`, so the campaign halts instead of reading no-edge-match as DONE.
- Any ambiguity → the most literal reading of the handoff that lets the plan freeze, with the
  ambiguity recorded in § Key decisions for a downstream mission to resolve.
