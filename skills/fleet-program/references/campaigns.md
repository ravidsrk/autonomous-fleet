# Campaign DAGs (conditional + sequential)

Campaigns extend linear [programs.md](programs.md) with **`if` edges** read from each mission's
`fleet-outcome` block (`skills/autonomous-fleet-core/references/fleet-outcome.md`).

Store the active campaign spec in `docs/fleet-program-progress.md` under **Campaign spec** or
pass inline in the user request.

## Format

```yaml
campaign: <id>
repo: single                    # one REPO_ROOT for all nodes
# repo: multi                  # see Cross-repo parallel below
base: <BRANCH_PREFIX><slug>-base   # optional; default <prefix><campaign-id>-base
start: <node-id>
nodes:
  <node-id>:
    mission: <mission-skill-name>
edges:
  <node-id>:
    - to: <next-node-id>
      if: always
    - to: <other-node-id>
      if: p0_open > 0
```

Rules:

- Evaluate edges **in order**; take the **first** edge whose `if` is true.
- If no edge matches, campaign `PHASE: DONE` (or `BLOCKED` if `status == blocked` — record in
  DECISIONS.md).
- One mission active at a time on a single repo.
- After each node completes, copy `fleet-outcome` summary into the program ledger **Last outcome**.

## Preset: repo-health (linear)

```yaml
campaign: repo-health
start: docs
nodes:
  docs: { mission: doc-sync }
  tests: { mission: test-coverage }
  tidy: { mission: cleanup }
edges:
  docs: [{ to: tests, if: always }]
  tests: [{ to: tidy, if: always }]
  tidy: []
```

## Preset: audit-branch (conditional)

After adversarial review: if P0s remain open in metrics (shouldn't happen if mission DONE — use
findings/deferrals), route to dependency-update; else test-coverage. Always finish with doc-sync.

```yaml
campaign: audit-branch
start: audit
nodes:
  audit: { mission: adversarial-review-and-fix }
  deps: { mission: dependency-update }
  tests: { mission: test-coverage }
  docs: { mission: doc-sync }
edges:
  audit:
    - { to: deps, if: ops_queue_count > 0 }
    - { to: tests, if: always }
  deps: [{ to: docs, if: always }]
  tests: [{ to: docs, if: always }]
  docs: []
```

## Preset: docs-if-bugs (conditional)

```yaml
campaign: docs-if-bugs
start: docs
nodes:
  docs: { mission: doc-sync }
  bugs: { mission: bug-batch }
  tests: { mission: test-coverage }
edges:
  docs:
    - { to: bugs, if: code_bug_findings > 0 }
    - { to: tests, if: always }
  bugs: [{ to: tests, if: always }]
  tests: []
```

## Preset: secure-ship (linear)

Same as programs.md `secure-ship` — use linear edges or:

```yaml
campaign: secure-ship
start: audit
nodes:
  audit: { mission: adversarial-review-and-fix }
  deps: { mission: dependency-update }
  docs: { mission: doc-sync }
edges:
  audit: [{ to: deps, if: always }]
  deps: [{ to: docs, if: always }]
  docs: []
```

## Preset: ship-with-proof (linear + post-gates)

**When:** "ship this branch safely", "harden then open PR", "prove it before merge".

Audit → tests → docs. Community **post-gates** after the last node (not fleet mission nodes):
`ship`, `qa`. Coordinator runs manually after campaign DONE — see
[community-skills.md](../../autonomous-fleet-core/references/community-skills.md).

```yaml
campaign: ship-with-proof
start: audit
nodes:
  audit: { mission: adversarial-review-and-fix }
  tests: { mission: test-coverage }
  docs: { mission: doc-sync }
post_gates:
  - ship
  - qa
edges:
  audit: [{ to: tests, if: always }]
  tests: [{ to: docs, if: always }]
  docs: []
```

Headless: `./scripts/run-campaign.sh <runtime> --preset ship-with-proof`

## Preset: align-then-ship (Tier 3 + pre-gate)

**When:** "finish this stalled product", "take it to shippable", "complete the whole product".

Single Tier 3 node. **Pre-gates** (before `NODE-complete`): `grill-with-docs`, `office-hours` —
coordinator picks one if intent is fuzzy; save artifact path in program ledger **Handoff notes**.
Post-gate: `qa`.

```yaml
campaign: align-then-ship
start: complete
pre_gates:
  - grill-with-docs
  - office-hours
nodes:
  complete: { mission: take-product-to-completion }
post_gates:
  - qa
edges:
  complete: []
```

**Requires explicit user request** for Tier 3 — do not default vague "clean up" intent here.

Headless: `./scripts/run-campaign.sh <runtime> --preset align-then-ship`

## Preset: quality-gate (linear + post-gates)

**When:** "is this production-ready?", "quality gate before release", "acceptance check".

Lighter than `ship-with-proof` (no doc-sync node). Post-gates: `qa-only`, `health`.

```yaml
campaign: quality-gate
start: audit
nodes:
  audit: { mission: adversarial-review-and-fix }
  tests: { mission: test-coverage }
post_gates:
  - qa-only
  - health
edges:
  audit: [{ to: tests, if: always }]
  tests: []
```

Headless: `./scripts/run-campaign.sh <runtime> --preset quality-gate`

## Community skill hooks

Campaign YAML may include `pre_gates` and `post_gates` for documentation. The mechanical campaign
driver (`scripts/run-campaign.sh`) runs **mission nodes only**; coordinators execute gates per
[community-skills.md](../../autonomous-fleet-core/references/community-skills.md).

| Preset | Pre-gate | Post-gate |
|--------|----------|-----------|
| `ship-with-proof` | — | ship, qa |
| `align-then-ship` | grill / office-hours | qa |
| `quality-gate` | — | qa-only, health |

## Cross-repo parallel (different repos only)

**Not** concurrent missions on one repo. For multiple repositories, run **separate coordinator
sessions** (or separate Orca campaigns), one program ledger per repo:

```yaml
campaign: org-docs-sync
parallel_repos:
  - repo: /path/to/service-a
    campaign: { start: docs, nodes: { docs: { mission: doc-sync } }, edges: { docs: [] } }
  - repo: /path/to/service-b
    campaign: { start: docs, nodes: { docs: { mission: doc-sync } }, edges: { docs: [] } }
```

Program coordinator for `parallel_repos`: spawn/isolate each run; aggregate FINAL report when all
complete. No shared BASE across repos.