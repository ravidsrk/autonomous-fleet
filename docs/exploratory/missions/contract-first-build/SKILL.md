---
name: contract-first-build
description: >-
  [Tier 3 · high blast radius · expect rework · review the frozen build plan]
  Build the typed product depth (API/router, server, data/ORM, auth, payments,
  integrations, read-path persistence) to full depth against a PRE-FROZEN boundary,
  consuming docs/build-plan.md (the seam contract, invariants, and work-areas frozen by
  scaffold-align) without re-deriving any of it. Use after the build plan is frozen and the
  agents-live row can stay stubbed, to fill every typed work-area to real depth against the
  discovered seam plus its stub fixtures. NOT for deriving the boundary (scaffold-align owns
  that) and NOT for wiring the live agents impl (agents-layer owns that): never touch the live
  impl file or widen the seam interface. Expect rework; the artifact to eyeball is the
  pre-frozen docs/build-plan.md, not one this mission invents. Runs via the
  autonomous-fleet-core engine. Trigger on: "build the contract depth", "implement the build
  plan", "build the API/data/auth/payments layers", "fill in the typed product".
license: MIT
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "3"
  fleet-component: "mission"
---


# Mission: contract-first-build

This mission builds the typed product depth against a boundary that is already frozen. Instead
of re-deriving scope, it READS docs/build-plan.md (the artifact scaffold-align froze) and builds
every Work-areas row whose layer is not `agents-live` to full depth (real API/router, server,
data/ORM, auth, payments, and read-path persistence) against the seam contract and the hardened
stub fixtures. The discipline that makes it converge: the boundary is PRE-FROZEN; this mission
consumes it, never widens it, and records a finding (status blocked) rather than re-deriving a
fact that turns out wrong.

## When to use
- The build plan is frozen: docs/build-plan.md exists with a populated § Seam contract,
  § Invariants, and § Work areas, and scaffold-align reported `seam_frozen == true`.
- You want the typed layers (api / server / data / auth / payments / ui) built to real depth
  while the `agents-live` Work-areas row stays stubbed.
- The seam interface and its stub fixtures are the contract to build against, not something to
  change.

Not when: the boundary is not yet frozen or the seam is undiscovered (run `scaffold-align`
first); or the only remaining work is wiring the live agents implementation (run `agents-layer`,
which owns the `agents-live` row and the stub removal).

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. The `agents-live` row and any deferred scope
go to a future run or `fleet-program` (see the `handoff-to-product` campaign).

## Optional skills

Coordinator-only. Activate at most two; each only when its trigger applies.

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `office-hours` | A boundary in docs/build-plan.md is ambiguous and the user wants product framing before building the area | Build against the frozen plan as written; record the ambiguity as a finding |
| `design-review` | A UI Work-areas row's design source is ambiguous and the built screen needs a visual check against the recorded design tokens | Build to the recorded § Handoff sources design reference and defer to `design-integration` |

## Worker skills

Inject per role on DISPATCH (workers load these; coordinator does not). Use only these ids.

| Role | Skills | If unavailable |
|------|--------|----------------|
| @builder (typed depth: api / data / auth / payments) | addy `source-driven-development` (MANDATORY when the stack is newer than training data: verify the framework/ORM/auth/payments APIs against current source before coding), addy `api-and-interface-design`, addy `security-and-hardening`, addy `doubt-driven-development`, matt `domain-modeling`, matt `codebase-design`, matt `tdd` | Seam contract + § Invariants + the framework docs |
| @builder (UI rows) | gstack `frontend-design`, addy `frontend-ui-engineering` | The recorded § Handoff sources design reference |
| @reviewer (per-PR review) | — | Mission gate: § Invariants + the owned Work-areas rows |

## Deferred missions

ROADMAP / deferred items in DECISIONS.md + **Recommended next missions** in
`docs/contract-build-readiness.md`. Route to REUSED generic missions only; never invent a mission
and never inline another mission as a node.

| Finding type | Route to |
|--------------|----------|
| The `agents-live` row (live impl wiring) | `agents-layer` (next campaign node) |
| A build-plan fact is wrong (seam needs widening, an invariant is unsatisfiable) | Record in DECISIONS.md, set status `blocked`; re-freeze is scaffold-align's job |
| Security hardening beyond what an area needs | `adversarial-review-and-fix` |
| Design parity gap on a built UI row | `design-integration` |
| A coverage gap surfaced while building an area | `test-coverage` |
| Setup/usage docs drifted from the built layers | `doc-sync` |

**Empirical note:** this is high-blast-radius typed work. Feature and cross-module build has no
direct category in arXiv 2601.15195 (documentation merges at ~84% cross-agent, the highest
observed rate; build/feature work has no such floor and broad runs thrash). The single control
that matters is the FROZEN docs/build-plan.md: review that artifact; this mission consumes it and
must not expand it, so full review gate and expect rework.

## CORE TENSION (read first)
"Build the whole typed product" is unbounded unless the boundary is fixed. Here it already is:
scaffold-align froze the seam contract, the invariants, and the work-areas, so the temptation is
not to expand scope but to QUIETLY re-derive it: to widen the seam interface to make an area
easier, to touch the live impl file, or to reinterpret an invariant. Resist all three. Build every
non-`agents-live` Work-areas row to real depth (no stubs left in the typed layers, no half-built
screens) AGAINST the frozen contract exactly. If depth genuinely needs an interface change, that is
a finding (the plan is frozen), not an edit.

## GOAL
Every Work-areas row whose layer is not `agents-live` is built to full typed depth against the
§ Seam contract and the hardened stub fixtures: real API/router, server, data/ORM with read-path
persistence, auth, payments, and integrations, each satisfying the relevant § Invariants and with
real behaviour-exercising tests. Zero stubs remain in the typed layers (the seam's own stub stays
in place for `agents-layer`). The seam interface is untouched and the live impl file is untouched.
"This is the real typed product wired to the frozen contract," not "it compiles."

## ROLE PIPELINE
- @builder reads docs/build-plan.md and CODES each owned Work-areas row to full depth against the
  § Seam contract + stub fixtures (build-blind to nothing; the plan is the spec).
- @reviewer REVIEWS each PR (fresh, build-blind), graded ONLY against the frozen § Invariants and
  the owned § Work-areas rows: area complete and full-depth, real tests, no stub left in a typed
  layer, the seam interface unchanged, the live impl file untouched, no regression to a prior area.
- @integrator SHIPS: opens PR, merges (conflict-aware), cleans worktree.

## LEDGER
`docs/contract-build-progress.md`. Per-task flags: `PLANNED=<t/f> BUILT=<t/f> REVIEWED=<t/f>
SHIPPED=<t/f>`. The frozen INDEX is the set of Work-areas rows this mission owns (every § Work
areas row with layer != `agents-live`), each `OPEN | DONE via PR#n`, plus an OPS QUEUE (rows
blocked on a human-supplied secret: DB / auth creds / payment keys) and a ROADMAP list (deferred,
never built this run).

## TASK STRUCTURE
- **T-READ-PLAN [@builder, gated on docs/build-plan.md existing]:** load docs/build-plan.md and do
  NOT re-derive anything in it. Read § Seam contract (the interface file, interface name, member
  list, contract types module, and the selector + its stub|live values, the boundary this mission
  must NOT widen and the live impl file it must NOT touch); § Invariants (the shell-checkable
  assertions + their commands, these are the per-task acceptance); and § Work areas (the build
  list). Copy every row whose layer != `agents-live` into the ledger INDEX as OPEN; copy the
  `agents-live` row to DECISIONS.md as deferred to `agents-layer`. Read § Consumption contract and
  obey it verbatim. If § Seam contract or § Invariants is missing or unparseable, set status
  `blocked` and stop; scaffold-align must re-freeze.
- **T-AREA… [per owned Work-areas row, loop, gated on T-READ-PLAN]:** each row is one PR.
  @builder builds that row to FULL typed depth against the § Seam contract + the hardened stub
  fixtures: real API/router and server logic, data/ORM with read-path persistence, auth, payments,
  or integrations as the row's layer requires, with all loading/empty/error/edge states and real
  behaviour-exercising tests. The row passes the § Invariants subset it touches (build, typecheck,
  lint, tests green) → @reviewer reviews (complete + full-depth + tests real + seam interface
  unchanged + live impl file untouched + no regression) → @integrator merges. Parallelize
  non-overlapping rows in independent worktrees; serialize rows that share hot files. Update the
  INDEX as rows close. A row needing a human-supplied secret (DB URL, auth creds, payment keys)
  goes to the OPS QUEUE with its build done against fixtures/test config; do not commit secrets.
- **T-FINAL [@integrator]:** run the § Invariants commands: build green, lint clean, full suite
  green; confirm every owned INDEX row is DONE and zero stubs remain in the typed layers (the
  seam's own stub is intentionally retained for `agents-layer`); confirm the seam interface and the
  live impl file are untouched. Output `docs/contract-build-readiness.md` LED BY the `fleet-outcome`
  YAML block (metrics `in_items_open`, `roadmap_count`, `stubs_remaining`, `ops_queue_count`; see
  `autonomous-fleet-core/references/fleet-outcome.md`), plus boolean readiness fields for each
  OPS-QUEUE secret still pending (e.g. `db_credentials_pending`, `auth_credentials_pending`,
  `payment_keys_pending`) so a human/OPS knows what to provision; these are readiness fields, NOT
  branch metrics. Then the index/roadmap summary and **Recommended next missions**. Ship as the
  final PR.

If `stubs_remaining > 0` at T-FINAL (a typed layer still ships a stub instead of real depth), set
`status: blocked`; the campaign must not read an unfinished typed layer as DONE.

The `fleet-outcome` block leads the readiness doc, for example:

```yaml
---
fleet-outcome:
  mission: contract-first-build
  status: done
  repo: <REPO_ROOT>
  base_branch: <BASE>
  prs_merged: <n>
  metrics:
    in_items_open: 0
    roadmap_count: <n>
    stubs_remaining: 0
    ops_queue_count: <n>
  db_credentials_pending: false
  auth_credentials_pending: false
  payment_keys_pending: false
---
```

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/contract-build-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission contract-first-build DONE: docs/contract-build-progress.md all task flags true,
docs/contract-build-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Every owned INDEX row `DONE`, every task `PLANNED=t BUILT=t REVIEWED=t SHIPPED=t`,
`docs/contract-build-readiness.md` exists, zero stubs remain in the typed layers, the seam
interface and the live impl file are untouched, and the build/lint/suite § Invariants pass. Then
send the FINAL report.

## DECISION DEFAULTS (mission-specific; on top of the engine's)
- Read every per-product fact (interface name, member list, file paths, selector, db/auth/payments
  vendors, design tokens) from docs/build-plan.md and `docs/agents/fleet-config.md`. NEVER hardcode
  one or re-derive it from the repo; the plan is the single source of truth.
- A build-plan fact that turns out wrong (the seam needs widening, an invariant is unsatisfiable as
  written) → record a finding in DECISIONS.md and set status `blocked`. Do NOT silently re-derive
  or widen the interface; re-freezing is scaffold-align's job.
- Never touch the live impl file recorded in § Seam contract and never modify the seam interface or
  the contract types it references. Build only against the interface + the hardened stub fixtures.
- Build each owned area to FULL depth: real persistence on the read path, real auth/payments wiring
  against fixtures or test config, all loading/empty/error/edge states; no stub left in a typed
  layer and no half-built screen. The seam's own stub stays; `agents-layer` removes it.
- Anything needing a real secret (DB URL, auth creds, payment keys) → OPS QUEUE, build against
  fixtures/test config, surface the pending secret as a boolean readiness field. Never commit a
  secret; env vars only.
- Tests real and behaviour-exercising; reject coverage-padding. Bar = every built area exercised
  against the contract and green; the § Invariants test command passes.
- Prefer many small per-area PRs (higher merge success) over one sweeping build PR; serialize rows
  that share hot files, parallelize the rest in independent worktrees.
- Any other ambiguity → the option that builds the most complete typed depth against the frozen
  contract while still converging; new scope ideas → DECISIONS.md ROADMAP, never a wider seam.
