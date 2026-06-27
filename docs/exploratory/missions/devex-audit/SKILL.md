---
name: devex-audit
description: >-
  [Tier 2 · moderate autonomy · full review gate · developer-experience] Run a live developer
  experience audit with frozen DX scorecard and ranked documentation gaps. Maps gstack
  /devex-review and /plan-devex-review into fleet ledgers with optional document-generate
  follow-ups. Use when onboarding friction, CLI help, or docs TTHW need evidence before ship.
  Trigger on: "DX audit", "developer experience review", "devex mission", "audit onboarding",
  "score the getting started flow", "plan devex review".
license: MIT
compatibility: Requires git and gh CLI; target repo must be buildable locally
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
  recommended-bundle: gstack-devex
  community-recommends:
    bundle: gstack-devex
    skills:
      - plan-devex-review
      - devex-review
    mode: warn
status: exploratory
---

> **Status: exploratory.** Mapped from gstack `devex-review`, `plan-devex-review`, and
> `document-generate`; not yet field-proven. See `docs/exploratory/missions/README.md`.


# Mission: devex-audit

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md`
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

```yaml community-recommends
bundle: gstack-devex
skills:
  - plan-devex-review
  - devex-review
mode: warn
```

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `devex-review` (gstack) | Live DX walkthrough with browse timing | Mission T-WALK script + manual timing |
| `plan-devex-review` (gstack) | Pre-ship DX plan review needed | T-SCORECARD lenses in mission |
| `document-generate` (gstack) | User wants generated doc stubs for gaps | Record gaps only; defer to `doc-sync` |
| `health` (gstack) | Composite scorecard requested | Mission scorecard fields only |

Community catalog: `autonomous-fleet-core` → `references/community-skills.md`. At most 2 optional
skills active.

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (DX walkthrough, scorecard, freeze) | `devex-review`, `plan-devex-review` when Optional active | Mission T-WALK / T-SCORECARD |
| @claude (integrator) | — | Ship gate |

No @codex builder unless user explicitly requests doc PRs from gap list — default is audit-only.

## Deferred missions

Record in `docs/devex-readiness.md` under **Recommended next missions**.

| Outcome | Route to |
|---------|----------|
| Doc drift / README fixes | `doc-sync` (shipped) |
| Missing tutorial content | `document-generate` (gstack) or manual doc PR |
| Product spec unclear after DX pass | `product-framing` (exploratory) |
| Security friction in onboarding | `security-cso-audit` (exploratory) |

## GOAL

Produce a **frozen DX scorecard** with time-to-hello-world evidence, friction-ranked touchpoints,
and a documentation gap index — without rewriting the whole docs tree in this mission.

## ROLE PIPELINE

- @claude runs **live DX walkthrough** (install → first success path) with timestamps and notes.
- @claude builds **scorecard** (TTHW, CLI help, error messages, discoverability) per gstack devex lenses.
- @claude **skeptic pass** drops vanity metrics; only reproducible friction enters gap index.
- @claude **FREEZES** `docs/devex-scorecard.md` and `docs/devex-gaps-index.md`.
- @claude writes `docs/devex-readiness.md` with **`fleet-outcome` YAML**.

## LEDGER

`docs/devex-progress.md`. Per-task flags: `PLANNED=<t/f> BUILT=<t/f> REVIEWED=<t/f> SHIPPED=<t/f>`.

Frozen index: `docs/devex-gaps-index.md` — rows `OPEN | DOC_STUB | ROUTED | WONT_FIX` with evidence links.

## TASK STRUCTURE

- **T-WALK [@claude]** — execute getting-started path; capture notes + optional screenshots in
  `docs/devex-progress.md`.
- **T-SCORECARD [@claude]** — score dimensions (install, first run, CLI, errors, docs nav); output
  `docs/devex-scorecard.md` (DRAFT).
- **T-GAPS [@claude]** — rank documentation and tooling gaps; output `docs/devex-gaps-index.md`.
- **T-SKEPTIC [@claude, fresh session]** — refute weak friction claims; trim scorecard.
- **T-FREEZE [@claude]** — mark scorecard FROZEN; gaps index is fix-loop input for downstream missions.
- **T-FINAL [@claude]** — output `docs/devex-readiness.md` with **`fleet-outcome` YAML**
  (`tthw_minutes`, `gaps_ranked`, `scorecard_frozen`).

## Runtime goal

```
Mission devex-audit DONE: docs/devex-scorecard.md FROZEN, docs/devex-gaps-index.md complete,
docs/devex-readiness.md fleet-outcome.status done, ./scripts/validate-fleet-outcome.sh passes.
```

## DONE

Frozen scorecard, gap index with evidence, all task flags terminal, valid fleet-outcome in readiness doc.

## DECISION DEFAULTS (mission-specific)

- Measure real paths — no hypothetical onboarding.
- Scorecard beats prose; every gap links to repro steps.
- Doc fixes are deferred unless user explicitly expands scope.
- gstack devex skills advise; fleet frozen ledger is authoritative.