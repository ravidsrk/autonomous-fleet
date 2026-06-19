# Skill composition rules

How autonomous-fleet loads agentskills.io skills. Read when coordinating any run or authoring
missions.

## Required stack (every run)

| Layer | Count | Skills |
|-------|-------|--------|
| Engine | 1 | `autonomous-fleet-core` (+ `references/engine.md` when coordinating) |
| Adapter | 1 | `autonomous-fleet-adapter-{orca,claude-code,grok}` |
| Mission | 1 | Exactly one mission skill (`doc-sync`, `bug-batch`, …) |

**Do not** activate two mission skills in the same coordinator session. Conflicting ledgers,
BASE branches, and DONE conditions will corrupt the run.

## Optional skills

Missions may list optional third-party or auxiliary skills in `## Optional skills`. Rules:

- Activate **only** when the mission's trigger column applies.
- Do **not** load unrelated catalog skills (token noise, conflicting instructions).
- Prefer repo scripts over optional skills when both exist (e.g. `./scripts/validate-skills.sh`
  over `skill-creator` for a one-off validate).
- At most 1–2 optional skills active at once unless the mission explicitly allows more.

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

## Multi-mission programs

Use `fleet-program` when the user wants an ordered chain (e.g. doc-sync → test-coverage →
cleanup). The program skill:

- Runs **one mission at a time** to completion (DONE + readiness doc).
- Uses `docs/fleet-program-progress.md` as the program ledger.
- Sets the next mission's BASE from the previous mission's final merged state (see fleet-program
  skill).

## Progressive disclosure (agentskills.io)

| Tier | Content | Fleet usage |
|------|---------|-------------|
| 1 | name + description | Catalog at session start |
| 2 | SKILL.md body | On activation (core + adapter + mission) |
| 3 | references/, scripts/ | `engine.md`, mission-specific refs, on demand |

Keep mission `SKILL.md` under ~500 lines; move bulky reference material to `references/`.

## Readiness doc: Recommended next missions

Every mission's final readiness doc must include:

```markdown
## Recommended next missions

| Mission | Reason | Blocker |
|---------|--------|---------|
| `bug-batch` | Code bug found in T-AUDIT | none |
```

Empty table is fine when nothing to defer.