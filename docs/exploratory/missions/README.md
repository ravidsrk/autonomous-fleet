# Exploratory missions

This directory holds mission skills that have been **documented but not yet
proven end-to-end**. They live here, not in `skills/`, so the framework's
shipped surface area maps 1:1 to missions with real-run evidence.

## Why these are here

A mission stays in `skills/` only if ALL three are true:

1. A `docs/<mission>-progress.md` written from a real run on a real repo
2. A `docs/<mission>-readiness.md` with a valid `fleet-outcome` block from
   the same run
3. At least one external-repo run-archive — either under `.fleet/runs/` in
   this repo with the mission named, or referenced from
   `docs/external-dogfood/`

The missions below fail at least one of those three checks, so they have
been moved out of `skills/`. This is the same rule already applied to
`docs/exploratory/missions/scaffold-align/`,
`docs/exploratory/missions/contract-first-build/`, and
`docs/exploratory/missions/agents-layer/` in 2026-06-22, generalised to the
post-Commit-C demotion of 2026-06-23.

The original demotion plan lives in
`docs/plans/way-ahead-2026-06-23.md` § 3 Commit D.

## Promotion criteria

A mission may move back to `skills/` only when all three of the following
artifacts exist and are referenced in the promotion PR:

| Artifact | Path |
|---|---|
| Progress doc | `docs/<mission>-progress.md` (real run, not stub) |
| Readiness doc | `docs/<mission>-readiness.md` with `fleet-outcome` block |
| External archive | `.fleet/runs/<run_id>/` produced by the mission, OR a referenced archive under `docs/external-dogfood/` |

Doctrine alone is not sufficient. Tests inherited from
`autonomous-fleet-core` are not sufficient. The promotion PR must cite a
real coding-agent run that produced the archive.

Mechanical gate (CI): `./scripts/validate_mission_promotion.py --require-ready <slug>`
must exit 0 before moving a mission back to `skills/`.

## Demoted missions (2026-06-23, Commit D)

### `bug-batch/`

[Tier 2] Close a batch of bugs from a list/tracker/described set, one PR
per bug, each gated by a FAILING TEST written first that reproduces the
bug. If promoted, would force exactness on the agent-weakest category
(bug-fixes). Currently: no progress doc, no readiness doc, no external
archive.

### `cleanup/`

[Tier 1] Behaviour-preserving code-health pass — dead-code removal,
duplication kill, named anti-pattern fix — without re-architecting. If
promoted, would be the lightest counterpart to `legacy-rebuild`.
Currently: a readiness doc exists (`docs/cleanup-readiness.md`) but no
progress doc and no external-repo run-archive. Demoted because the
three-artifact rule requires BOTH progress AND external archive.

### `dependency-update/`

[Tier 1] Update a repo's dependencies to current versions, fix bump
breakages, keep the suite green, one PR per logical group. If promoted,
would handle stale deps + security advisories autonomously. Currently: no
progress, no readiness, no external archive.

### `design-integration/`

[Tier 2] Adopt a fresh design across an existing product to full parity
(visual AND feature-wise) — reskin every screen and build the features the
design implies but the product lacks. If promoted, would be the
whole-app-redesign counterpart to single-page `landing-page-convergence`.
Currently: no progress, no readiness, no external archive.

### `inference-cost/`

[Tier 2] Reduce AI inference spend while holding output quality constant
— measurement-first cost optimization with a baseline cost+quality
harness, sanctioned levers only, and a hard refusal of
subscription-token-as-backend hacks. If promoted, would address one of the
clearest measurable outcomes a mission can ship. Currently: no progress,
no readiness, no external archive.

### `landing-page-convergence/`

[Tier 2] Force a production landing page that has DIVERGED from an
approved design back to full fidelity, section by section, with a named
divergence checklist as the forcing function. If promoted, would handle
single-page design-drift convergence (sibling to `design-integration`).
Currently: no progress, no readiness, no external archive.

### `legacy-rebuild/`

[Tier 3] Adversarially review a legacy app, research the best current
architecture, and rebuild end-to-end on a modern foundation while
preserving everything it currently does — incremental and shippable per
PR, against a captured behaviour floor. If promoted, would be the
highest-blast-radius mission with the strongest preservation guarantee.
Currently: no progress, no readiness, no external archive.

### `take-product-to-completion/`

[Tier 3] Drive a STALLED product to a full-fledged, shippable state via
adversarial review + market research + a FROZEN COHERENT PRODUCT BOUNDARY
+ full-depth build inside that boundary. If promoted, would be the
flagship Tier 3 mission for finishing started-but-unshipped products.
Currently: no progress, no readiness, no external archive.

### `targeted-migration/`

[Tier 2] Migrate ONE axis of a codebase (framework version, library swap,
language/runtime bump, DB/ORM change, API-version move) while preserving
everything else and keeping the suite green. If promoted, would handle
the one-axis-at-a-time slot between `dependency-update` and full
`legacy-rebuild`. Currently: no progress, no readiness, no external
archive.

## Promotion process

To re-promote a mission from `docs/exploratory/missions/<mission>/` back
to `skills/<mission>/`:

1. **Run the mission on a real repo** via a campaign (in this repo or an
   external one). The mission must produce a valid `fleet-outcome` block.
2. **Archive the run** to `.fleet/runs/<run_id>/` with a passing
   `validate_run_archive.py`. If the run was on an external repo,
   reference it under `docs/external-dogfood/<mission>-<repo>.md`.
3. **Write `docs/<mission>-progress.md`** documenting the run end-to-end
   (the actual builder/reviewer transcript, the findings closed, the
   metrics produced).
4. **Write `docs/<mission>-readiness.md`** with the `fleet-outcome` block
   from the run.
5. **`git mv docs/exploratory/missions/<mission> skills/<mission>`** to
   restore the skill.
6. **Remove `status: exploratory`** from the SKILL.md frontmatter and
   strip the exploratory admonition block at the top of the file.
7. **Update consumers** — re-add the mission to
   `skills/autonomous-fleet/SKILL.md`, `skills/autonomous-fleet/references/missions.md`,
   `README.md`'s mission list, and any `scripts/campaigns/*.yaml` that
   should re-include it.
8. **Update the marketplace packet** to mention the newly promoted
   mission.
9. **Open a PR** citing the run id, the archive path, the progress doc,
   and the readiness doc.

A demotion can be reversed; doctrine alone cannot promote. The artifact
is the gate.
