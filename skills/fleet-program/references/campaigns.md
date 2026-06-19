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