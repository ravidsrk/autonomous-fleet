---
name: release-document
description: >-
  [Tier 2 · moderate autonomy · full review gate · post-ship docs] Post-ship documentation sweep
  and deploy verification checklist after a version lands. Maps gstack /document-release, /ship,
  /land-and-deploy, and /canary into fleet frozen artifacts. Use after merge or deploy when
  changelog, user docs, and canary notes need closure. Trigger on: "document this release",
  "post-ship docs", "release documentation mission", "update docs after ship", "canary doc sweep".
license: MIT
compatibility: Requires git and gh CLI; deploy URL or release tag supplied by user
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
status: exploratory
---

> **Status: exploratory.** Mapped from gstack `document-release`, `ship`, `land-and-deploy`,
> and `canary`; not yet field-proven. See `docs/exploratory/missions/README.md`.


# Mission: release-document

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md`
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `document-release` (gstack) | User wants gstack post-ship doc pipeline | Mission T-SWEEP checklist |
| `ship` (gstack) | Release just landed via gstack ship | User supplies VERSION + PR link |
| `land-and-deploy` (gstack) | Deploy verification needed | Mission deploy checklist rows |
| `canary` (gstack) | Canary monitoring notes requested | Manual canary section in checklist |
| `document-generate` (gstack) | Missing doc pages need stubs | Route gaps to `doc-sync` |

Community catalog: `autonomous-fleet-core` → `references/community-skills.md`. At most 2 optional
skills active.

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (doc sweep, checklist, freeze) | `document-release` when Optional active | Mission T-SWEEP |
| @codex (small doc PRs if in scope) | — | Only when user expands to fix gaps |
| @claude (integrator) | — | Ship gate |

## RELEASE CONTEXT (user supplies)

VERSION tag or merge commit, production/staging URL if deploy verification is in scope, and
CHANGELOG path. HARD EXTERNAL DEPENDENCY if release artifact cannot be identified — pause and
document.

## Deferred missions

Record in `docs/release-doc-readiness.md` under **Recommended next missions**.

| Gap type | Route to |
|----------|----------|
| Broad doc drift | `doc-sync` (shipped) |
| DX friction discovered during sweep | `devex-audit` (exploratory) |
| Security notes in deploy | `security-cso-audit` (exploratory) |
| User-facing QA before announce | `browser-qa-fix` (exploratory) |

## GOAL

Close the **post-ship documentation tail**: changelog alignment, user-facing doc updates checklist,
deploy verification notes, and canary/monitoring reminders — frozen before public announce.

## ROLE PIPELINE

- @claude inventories **release delta** (merged PRs, VERSION, CHANGELOG).
- @claude runs **doc sweep** against guide, README, API docs, and migration notes.
- @claude records **deploy checklist** (land, health, canary) with pass/fail or N/A.
- @claude **FREEZES** `docs/release-doc-checklist.md`.
- @claude writes `docs/release-doc-readiness.md` with **`fleet-outcome` YAML**.

## LEDGER

`docs/release-doc-progress.md`. Per-task flags: `PLANNED=<t/f> BUILT=<t/f> REVIEWED=<t/f>
SHIPPED=<t/f>`.

Frozen artifact: `docs/release-doc-checklist.md` — sections `CHANGELOG | USER_DOCS | DEPLOY | CANARY`
each row `PENDING | DONE | N/A`.

## TASK STRUCTURE

- **T-INVENTORY [@claude]** — identify release scope from git/gh; log in progress ledger.
- **T-SWEEP [@claude]** — walk doc surfaces; list required updates in checklist (DRAFT).
- **T-DEPLOY [@claude, optional]** — verify deploy URL health / canary notes if credentials supplied.
- **T-FREEZE [@claude]** — mark checklist FROZEN; outstanding items routed to Deferred missions.
- **T-FINAL [@claude]** — output `docs/release-doc-readiness.md` with **`fleet-outcome` YAML**
  (`version`, `checklist_complete`, `open_doc_items`).

## Runtime goal

```
Mission release-document DONE: docs/release-doc-checklist.md FROZEN,
docs/release-doc-readiness.md fleet-outcome.status done,
./scripts/validate-fleet-outcome.sh passes.
```

## DONE

Frozen checklist with all sections terminal or explicitly routed, valid fleet-outcome, release version recorded.

## DECISION DEFAULTS (mission-specific)

- No deploy mutations without explicit user approval — checklist only by default.
- Changelog accuracy beats marketing tone.
- Canary section is N/A when no production deploy exists.
- gstack ship skills advise; fleet checklist is authoritative.