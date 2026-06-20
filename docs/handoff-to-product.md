# Handoff to product

A reference for the generic "build a product from a design+spec handoff" capability. Given a
repo that follows the supported convention (scaffolded on the better-t-stack family, with a
stub-first agent/service seam and a design reference + product spec in `docs/`), three new
missions take it from handoff to a built, agent-wired product. Per-product facts are
discovered, not hardcoded: the missions self-orient to your repo and freeze what they find
into one artifact the rest of the run consumes.

This doc covers the supported handoff convention, the methodology, the mission set and the
campaign, how setup config selects the scaffold convention and agents framework, the OPS/human
boundary, and a worked example against HeyCMO (the only place HeyCMO appears, as an example).

## What a supported handoff looks like

A handoff is a scaffolded repo, not a greenfield prompt. It conforms to the convention when:

- It is scaffolded on the configured `scaffold_convention` (default better-t-stack): a typed
  monorepo with a web app, a server app, and a shared package, plus a single build/typecheck/
  test toolchain.
- It carries a product spec under `docs/` (PRD, flows, screens, capability map, roadmap, or the
  subset the team wrote) and a design reference (a design-system doc and/or static design files
  under a design-reference directory).
- It exposes a stub-first agent/service seam: one exported interface (a typed boundary) with two
  implementations selected by an env flag. One implementation is a stub with fixtures so the UI
  and tests run with no backend. The other is the live implementation, which may not exist yet.
- The interface references a contract types module holding the request/response/model types that
  cross the boundary.

The seam is the load-bearing part. The recognition rule is mechanical: find an exported
interface whose two implementations are chosen by an env flag, one a stub with fixtures, one
live. That interface, its selector, its stub, and its contract types are what the first mission
freezes. If a repo diverges from the convention, the missions adapt to the intent and record why
(the engine's MISSION-FIT CHECK), or set `status: blocked` if the seam is not recognizable.

## Methodology: derive missions from seams and invariants

The capability is built on two generalization rules.

Product-specifics are discovered, not hardcoded. The first mission self-orients to the handoff
(reads `docs/` and the design reference, finds the seam, finds the design tokens, finds the
contract types) and freezes a Build Plan artifact at `docs/build-plan.md`. That artifact holds
the seam contract (interface plus its complete member list), the machine-checkable invariants
that become acceptance metrics, the per-area work list, and the key decisions. Every downstream
mission consumes `docs/build-plan.md` read-only rather than re-deriving. Per-product facts (the
member count, the vendor names, the file paths) live in the artifact, never in mission text.

Stack-convention is configured, not hardcoded. `setup-autonomous-fleet` records
`scaffold_convention` and `agents_framework` in `docs/agents/fleet-config.md`. Missions read that
config and adapt; normative text says "the configured scaffold convention" and "the configured
agents framework", with the default named once in parentheses.

The Build Plan is the single source of per-product truth. Its frozen section layout (set by the
first mission, in this order):

- `# Build plan` with a one-line frozen-contract note.
- `## Handoff sources`: design reference path, product spec paths, `scaffold_convention`,
  `agents_framework`.
- `## Seam contract`: interface file, interface name, selector (env var plus values and the file
  that reads it), stub impl file, live impl file, contract types module, a MEMBER LIST table
  (one row per interface member: member, signature, purpose), the streaming/event surface if any,
  and the boundary rule.
- `## Invariants`: a numbered list of shell-checkable assertions plus the command that checks
  each. At minimum: build green, typecheck/lint green, test green, stub implements every interface
  member, the selector defaults to stub. These become downstream acceptance.
- `## Work areas`: a table the builders loop over (area, layer, depends-on-seam-members, spec
  source, design source, status), frozen OPEN.
- `## Key decisions`: stack facts discovered by role, the chosen selector default, anything
  adapted because the repo diverged.
- `## Consumption contract`: the verbatim rule that downstream missions build against the seam
  and stub fixtures, must not widen the interface or re-derive, and set `status: blocked` rather
  than silently re-deriving a wrong fact.

Missions are derived from seams and invariants, not from a feature list. The seam's member list
defines what to wire. The invariants define what "green" means and become each task's per-task
acceptance. The work areas define the per-area build loop. Because all three live in the frozen
artifact, the same three missions run against any conforming handoff.

## The mission set

Three new missions, run in order, one mission at a time per repo. Parallelism lives inside a
mission via independent worktrees on non-overlapping work-area rows.

`scaffold-align` (Tier 1, verification-led, safe to run unattended). Self-orients to the handoff,
confirms the scaffold builds and typechecks and tests green (fixes minimally if not), certifies
the seam by hardening the stub so every interface member is exercised with a realistic fixture,
adds a contract test that asserts the stub implements the whole interface, then freezes
`docs/build-plan.md` with work areas OPEN. It is the only writer of the Build Plan. The hardened
stub plus the contract test become the acceptance contract the agents mission later checks
against. Metrics: `align_items_open`, `check_green`, `seam_frozen`, `scaffold_ok`. Sets
`status: blocked` when the scaffold will not go green or the seam is not freezable.

`contract-first-build` (Tier 3, high blast radius, expect rework, review the frozen build plan).
Reads the pre-frozen Build Plan and builds typed depth for every work-area row whose layer is not
agents-live (api, server, data, auth, payments, ui), against the seam contract and the stub
fixtures, one PR per area. It must not touch the live impl file and must not widen the interface;
if depth needs an interface change, it records a finding (the plan is frozen) and defers. Metrics:
`in_items_open`, `roadmap_count`, `stubs_remaining`, `ops_queue_count`.

`agents-layer` (Tier 3, one-axis stub to live cutover, full review gate). Reads the seam contract
and the hardened stub fixtures as the acceptance contract, stands up the configured agents
framework alongside the stub, fills the live impl so it satisfies the same fixtures the stub does
(the selector flips to live in tests), then removes the stub once live passes every fixture. The
stub is the "old axis" of a stub to live cutover. Metrics: `migration_items_open`,
`seam_unwired_open`, `old_axis_removed`, `evals_passing`, `deploy_pending_ops`.

Reused generic missions (already generic, authored elsewhere, attach as deferred routes from any
node, never inline as a fourth mission): `design-integration` (design parity), `test-coverage`,
`doc-sync`, `dependency-update`, `bug-batch`, `adversarial-review-and-fix` (deep hardening). They
are routed via each mission's Deferred missions table, not chained inside a mission.

## The campaign

Nodes are mission names. Edges carry ordered if-conditions on the prior node's
`fleet-outcome.metrics` (first true wins; no match means the phase is done unless the prior node
set `status: blocked`, which halts the campaign).

This is the conceptual three-mission spine. The shipped campaign at
`scripts/campaigns/handoff-to-product.yaml` adds the `design-integration` node before the build
node and the full quality tail (`audit → deps → tests → docs → bugs`); see that file for the
runnable version.

```yaml
campaign: handoff-to-product
start: align
nodes:
  align:  { mission: scaffold-align }
  build:  { mission: contract-first-build }
  agents: { mission: agents-layer }
edges:
  align:
    - { to: build, if: seam_frozen == true }    # proceed only when the plan is frozen
  build:
    - { to: agents, if: stubs_remaining == 0 }   # typed depth done, wire live
  agents: []
```

A failed gate sets `status: blocked` in that node's fleet-outcome so the campaign halts instead
of misreading no-edge-match as done. `scaffold-align` blocks when `scaffold_ok == false` or
`seam_frozen == false`; `agents-layer` blocks when live cannot satisfy the stub fixtures.
Community and agents-framework skills attach only as Optional, Worker, or pre/post-gate skills
inside a node, never as a fourth node.

The metric frozensets are registered in `scripts/lib/fleet_outcome.py` (`MISSION_METRICS`). Every
metric value is int, float, or bool; the validator rejects strings. The `*_open`, `*_remaining`,
and `*_unwired` counts are what gate the campaign.

## Setup config selects the convention

`setup-autonomous-fleet` writes `docs/agents/fleet-config.md`, which now also records two fields
the handoff missions read during self-orientation:

- `scaffold_convention` (default better-t-stack): tells `scaffold-align` what monorepo shape and
  toolchain to expect when it derives the build/typecheck/test commands and locates the apps and
  shared package.
- `agents_framework` (default eve): tells `agents-layer` which framework to stand up for the live
  implementation.

Missions reference these by name from config, not by hardcoded literal. `scaffold-align` records
the resolved values into the Build Plan's `## Handoff sources` so downstream missions inherit them
without re-reading config. If the repo diverges from the recorded convention, the mission adapts
to the intent and records the divergence under `## Key decisions`, or blocks if it cannot.

## The OPS and human boundary

The missions land engineering on the base branch; they do not deploy. The boundary mirrors the
rest of the fleet: merge is not deploy, and anything that touches a live environment is queued for
a human.

- `contract-first-build` carries `ops_queue_count`: work it builds in code but that needs a human
  operational step (provisioning a managed database, configuring a payments vendor, setting
  production secrets) is recorded as an OPS item, not executed.
- `agents-layer` carries `deploy_pending_ops`: standing up the live agents endpoint, wiring real
  credentials, and the production cutover of the selector from stub to live are OPS items. The
  mission proves live satisfies the stub fixtures behind the flag in tests; flipping the default
  in production is human-owned.
- The base to default-branch promotion is always human-owned. Builds run on testnet or staging
  only.

The readiness doc each mission writes lists its OPS queue so a human can see exactly what is left
to operate before the product is live.

## Worked example (illustrative only, HeyCMO)

This section is the one place HeyCMO appears. It shows what the missions discover for one
conforming handoff. Your repo will differ; none of these names appear in mission text.

HeyCMO is a better-t-stack monorepo: `apps/web`, `apps/server`, `packages/shared`, with a
turbo/biome toolchain. Its spec lives under `docs/` (PRD.md, FLOWS.md, SCREENS.md,
CAPABILITY-MAP.md, DESIGN-SYSTEM.md, ROADMAP.md) and its design reference under
`design-reference/`.

Running `scaffold-align` self-orients and freezes `docs/build-plan.md`:

- Handoff sources: design reference `design-reference/` plus `docs/DESIGN-SYSTEM.md`; spec
  `docs/PRD.md`, `docs/FLOWS.md`, `docs/SCREENS.md`; `scaffold_convention: better-t-stack`;
  `agents_framework: eve`.
- Seam contract: interface file `packages/shared/src/agent.ts`, interface name `AgentGateway`,
  selector `AGENT_MODE=stub|live` read in `apps/server/src/env.ts`, stub impl
  `apps/server/src/agent/stub.ts`, live impl `apps/server/src/agent/http.ts`, contract types
  `packages/shared/src/models.ts`. The MEMBER LIST enumerates the interface (here 15 members,
  from `deriveContext` through `subscribe`); the count is whatever was discovered, never asserted
  in mission text. Streaming surface: a `subscribe(handler) -> unsubscribe` event channel over
  `AgentEvent`.
- Invariants: the discovered build, typecheck, and test commands green; the stub implements every
  `AgentGateway` member; `AGENT_MODE` defaults to stub.
- Work areas: rows for the typed layers (api, server, data, auth, payments, ui) marked OPEN plus
  one agents-live row, each tied to a spec section and a design source.

`contract-first-build` then reads that plan and builds the typed depth for the non-agents-live
rows against `AgentGateway` and the stub fixtures, one PR per area, without touching
`apps/server/src/agent/http.ts` or widening `AgentGateway`. Provisioning the managed database and
configuring the payments vendor are recorded as OPS items.

`agents-layer` reads the seam contract and the hardened stub fixtures, stands up the configured
agents framework (default eve, e.g. defineAgent/defineTool/eveChannel/routeAuth/defineEval)
alongside the stub, fills `apps/server/src/agent/http.ts` until it satisfies every stub fixture
with `AGENT_MODE=live` in tests, then removes the stub. The production flip of `AGENT_MODE` and
the live endpoint deploy are `deploy_pending_ops`, left for a human.

The same three missions run unchanged against any other conforming handoff; only the frozen
`docs/build-plan.md` differs.
