---
name: incident-investigate
description: >-
  [Tier 2 · moderate autonomy · full review gate · incident-response] Root-cause investigation
  with frozen RCA document and mandatory regression test per confirmed cause. Maps gstack
  /investigate, /retro, and /learn into fleet worktrees. Use for production incidents, SEV
  postmortems, or recurring failures needing durable learnings. Trigger on: "investigate this
  incident", "root cause analysis", "incident mission", "write the RCA", "retro this outage",
  "regression test for this bug".
license: MIT
compatibility: Requires git and gh CLI; incident timeline or error evidence supplied by user
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
  recommended-bundle: gstack-security
  community-recommends:
    bundle: gstack-security
    skills:
      - investigate
    mode: warn
status: exploratory
---

> **Status: exploratory.** Mapped from gstack `investigate`, `retro`, and `learn`; not yet
> field-proven. See `docs/exploratory/missions/README.md`.


# Mission: incident-investigate

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md`, `references/composition.md`, EVID rules
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

```yaml community-recommends
bundle: gstack-security
skills:
  - investigate
mode: warn
```

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `investigate` (gstack) | Structured root-cause pass requested | Mission T-RCA template |
| `retro` (gstack) | Team retro / blameless review | T-LEARN section in RCA |
| `learn` (gstack) | Persist learnings to project memory | `docs/incident-learnings.md` in repo |
| `careful` (gstack) | Repro steps touch production | Core sandbox + careful prompts |

Community catalog: `autonomous-fleet-core` → `references/community-skills.md`. At most 2 optional
skills active.

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (RCA, retro, freeze) | `investigate`, `retro` when Optional active | Mission T-RCA |
| @codex (regression test + fix) | — | One PR per confirmed root cause |
| @claude (fresh build-blind reviewer) | — | Mission review gate |
| @claude (integrator) | — | Ship gate |

Stage-9 cross-vendor rule: @codex writes regression tests; fresh @claude reviews without build context.

## INCIDENT INPUT (user supplies)

Timeline, error signatures, logs, or ticket link. HARD EXTERNAL DEPENDENCY if no reproducible
signal — pause at T-SCOPE and document unknowns.

## Deferred missions

Record in `docs/incident-readiness.md` under **Recommended next missions**.

| Finding type | Route to |
|--------------|----------|
| Multiple unrelated bugs | `bug-batch` (exploratory) |
| Security root cause | `security-cso-audit` (exploratory) |
| Missing coverage broadly | `test-coverage` (shipped) |
| Browser-only repro | `browser-qa-fix` (exploratory) |

## GOAL

Produce a **frozen RCA** with confirmed root cause, contributing factors, regression test merged,
and learnings persisted — not a narrative-only postmortem.

## ROLE PIPELINE

- @claude **scopes** incident and collects EVID (logs, traces, repro steps).
- @claude drafts **RCA** with five-whys or equivalent; separates confirmed vs hypothetical.
- @claude **skeptic pass** refutes weak causal claims.
- @codex adds **regression test** reproducing the failure mode, then minimal fix if still broken.
- Fresh build-blind @claude **reviews** test + fix PR.
- @claude writes `docs/incident-readiness.md` with **`fleet-outcome` YAML** and learnings.

## LEDGER

`docs/incident-progress.md`. Per-task flags: `PLANNED=<t/f> BUILT=<t/f> REVIEWED=<t/f>
SHIPPED=<t/f>`.

Frozen artifacts:
- `docs/incident-rca.md` — timeline, root cause, contributing factors, action items.
- `docs/incident-close-index.md` — rows `OPEN | CONFIRMED | REFUTED | CLOSED` per hypothesis.

## TASK STRUCTURE

- **T-SCOPE [@claude]** — define incident boundary; log unknowns in progress ledger.
- **T-RCA [@claude]** — investigate; output `docs/incident-rca.md` (DRAFT) + close-index hypotheses.
- **T-SKEPTIC [@claude, fresh session]** — refute weak causes; update REFUTED rows.
- **T-FREEZE [@claude]** — confirmed root cause frozen; drives fix loop only.
- **T-REGRESS [@codex → @claude review]** — failing test first, then fix; CLOSE-INDEX `CLOSED`.
- **T-LEARN [@claude]** — append learnings; output `docs/incident-readiness.md` with **`fleet-outcome`
  YAML** (`root_cause_confirmed`, `regression_test_merged`, `learnings_count`).

## Runtime goal

```
Mission incident-investigate DONE: docs/incident-rca.md FROZEN, regression test merged,
docs/incident-close-index confirmed rows CLOSED, docs/incident-readiness.md fleet-outcome.status done,
./scripts/validate-fleet-outcome.sh passes.
```

## DONE

Frozen RCA, regression test in mainline, learnings recorded, all confirmed hypotheses terminal.

## DECISION DEFAULTS (mission-specific)

- Failing test before fix — non-negotiable for confirmed causes.
- Hypotheses without evidence stay REFUTED or OPEN — never ship fixes on vibes.
- Blameless retro tone; fleet ledger holds facts and EVID paths.
- gstack investigate skills advise; frozen RCA is authoritative.