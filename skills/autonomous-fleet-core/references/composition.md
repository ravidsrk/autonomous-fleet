# Skill composition rules

How autonomous-fleet loads agentskills.io skills. Read when coordinating any run or authoring
missions.

## Required stack (every run)

| Layer | Count | Skills |
|-------|-------|--------|
| Engine | 1 | `autonomous-fleet-core` (+ `references/engine.md` when coordinating) |
| Adapter | 1 | `autonomous-fleet-adapter-{orca,claude-code,grok,codex}` |
| Mission | 1 | Exactly one mission skill (`doc-sync`, `bug-batch`, …) |

**Do not** activate two mission skills in the same coordinator session. Conflicting ledgers,
BASE branches, and DONE conditions will corrupt the run.

## Three skill attachment types

| Section | Who loads it | Purpose |
|---------|--------------|---------|
| `## Required skills` | Coordinator | core + adapter (always) |
| `## Optional skills` | Coordinator | Orchestration-time extras (MCP auth, validate tooling) |
| `## Worker skills` | **Workers** via DISPATCH preamble | Domain capability (frontend-design, SEO, etc.) |

### Optional skills (coordinator)

- Activate **only** when the mission's trigger column applies.
- Do **not** load unrelated catalog skills (token noise, conflicting instructions).
- Prefer repo scripts over optional skills when both exist.
- At most 1–2 optional skills active at once unless the mission explicitly allows more.

### Worker skills (builders/reviewers)

- Listed per pipeline role in the mission's `## Worker skills` table.
- Coordinator copies the list into each worker task spec (engine WORKER SKILLS block).
- Workers activate those skills in **their** session — not in the coordinator context.
- Makes composition intentional: the mission guarantees `frontend-design`, not "hope the worker
  finds it."

## Deferred missions (same run)

When work is out of mission scope:

1. Record the finding in `docs/DECISIONS.md`.
2. Add a row to the mission readiness doc under **Recommended next missions** (mission id,
   reason, blocker if any).
3. **Do not** start the deferred mission in the same run.

Cross-mission handoff is owned by `fleet-program` (sequential runs), not by loading another
mission skill mid-session.

## Parallelism

| Scope | Allowed? | Mechanism |
|-------|----------|-----------|
| Tasks inside one mission | Yes | `PLACE(independent)` + hot-file rule (see engine.md) |
| Missions on same repo | No | One BASE, one ledger, one coordinator |
| Missions on different repos | Yes | Independent runs |

## Runtime goals (native loop binding)

Hosts with goal APIs (Grok `/goal` + `update_goal`, Claude `/goal`, Codex `/goal`) bind them to
ledger DONE via primitives 9–12 in `engine.md`. See [runtime-goals.md](runtime-goals.md).

- **File ledger** = authoritative completion (survives compaction).
- **Native goal** = turn-continuation harness (prevents early stop).
- `GOAL_COMPLETE` only after readiness + `validate-fleet-outcome.sh`.
- Orca: ledger + `check --wait` loop only (no `/goal`).
- Headless CI: `scripts/run-mission-headless.sh`.

## Multi-mission programs and campaigns

Use `fleet-program` for sequential chains **and** conditional DAGs (campaigns). The program skill:

- Runs **one mission at a time** per repo to completion (DONE + readiness doc).
- Uses `docs/fleet-program-progress.md` as the program ledger.
- Reads **`fleet-outcome`** YAML from each readiness doc to evaluate `if` edges ([fleet-outcome.md](fleet-outcome.md), [campaigns.md](../../fleet-program/references/campaigns.md)).
- Sets the next mission's BASE from the previous mission's final merged state.
- **Never** parallelizes two missions on the same repo (cross-mission file locking is out of scope).
- **Cross-repo parallel:** separate sessions per repo ([campaigns.md](../../fleet-program/references/campaigns.md)).

## Progressive disclosure (agentskills.io)

| Tier | Content | Fleet usage |
|------|---------|-------------|
| 1 | name + description | Catalog at session start |
| 2 | SKILL.md body | On activation (core + adapter + mission) |
| 3 | references/, scripts/ | `engine.md`, mission-specific refs, on demand |

Keep mission `SKILL.md` under ~500 lines; move bulky reference material to `references/`.

## Community skills (third-party)

Attach gstack, agent-skills, mattpocock/skills, and other catalogs **only** as Optional
(coordinator) or Worker (DISPATCH) — never as a second mission skill. Use `fleet-program`
presets (`ship-with-proof`, `align-then-ship`, `quality-gate`) for multi-step runs that
optionally call community **pre-gates** and **post-gates**.

Full install matrix, bundles, and anti-patterns: [community-skills.md](community-skills.md).
Research: `docs/research-community-skills.md`.

## Readiness doc: fleet-outcome + Recommended next missions

Every mission's final readiness doc must:

1. **Start with** a YAML `fleet-outcome` frontmatter block ([fleet-outcome.md](fleet-outcome.md)).
2. Include markdown **Recommended next missions** (human-readable; mirror `deferred_missions` in
   the YAML).

```markdown
---
fleet-outcome:
  mission: doc-sync
  status: done
  ...
---

## Recommended next missions

| Mission | Reason | Blocker |
|---------|--------|---------|
| `bug-batch` | Code bug found in T-AUDIT | none |
```

Empty deferral list is fine when nothing to route.