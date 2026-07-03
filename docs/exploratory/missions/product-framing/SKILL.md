---
name: product-framing
description: >-
  [Tier 2 · moderate autonomy · full review gate · pre-build] Turn vague product intent into a
  frozen, review-approved product spec before any implementation. Runs gstack-style office-hours
  forcing questions plus CEO/design/eng plan reviews (via optional community skills), then emits
  docs/product-spec.md as the single source of truth for downstream build missions. Use when the
  user has an idea, wedge, or feature direction but no frozen spec yet. Trigger on: "frame this
  product", "office hours on this idea", "is this worth building", "freeze the product spec",
  "run plan reviews before we code", "product framing mission".
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
  recommended-bundle: gstack-framing
  community-recommends:
    bundle: gstack-framing
    skills:
      - office-hours
      - autoplan
    mode: warn
status: exploratory
---

> **Status: exploratory.** Documented from gstack `office-hours` + `autoplan` + `plan-*` flows;
> not yet run end-to-end with an external archive. See `docs/exploratory/missions/README.md`.


# Mission: product-framing

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md`
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

```yaml community-recommends
bundle: gstack-framing
skills:
  - office-hours
  - autoplan
mode: warn
```

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `office-hours` (gstack) | User has raw idea / wedge uncertainty | Mission forcing-question script in T-FRAME |
| `autoplan` (gstack) | User wants full CEO+design+eng+DX review gauntlet with auto-decisions | Run T-REVIEWS manually per lens |
| `plan-ceo-review` (gstack) | Scope/ambition challenge needed | @claude CEO lens in T-REVIEWS |
| `plan-eng-review` (gstack) | Architecture/execution lock needed | @claude eng lens in T-REVIEWS |
| `plan-design-review` (gstack) | UX/HIG review needed | @claude design lens in T-REVIEWS |
| `spec` (gstack) | User supplied only a one-liner intent | Mission T-SPEC phases |

Community catalog: `autonomous-fleet-core` → `references/community-skills.md`. At most 2 optional
skills active per run (gstack ids count toward cap).

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (framing, reviews, freeze) | `office-hours`, `autoplan`, `plan-ceo-review`, `plan-eng-review`, `plan-design-review` when Optional rows active | Mission T-FRAME / T-REVIEWS scripts |
| @claude (integrator) | — | Mission ship gate only |

No @codex builder in this mission — implementation is explicitly out of scope until spec freeze.

## Deferred missions

Record in `<LEDGER_DIR>/framing-readiness.md` under **Recommended next missions**.

| Outcome | Route to |
|---------|----------|
| Spec ready; greenfield build | `contract-first-build` (exploratory) or operator-chosen build mission |
| Spec ready; stalled product | `take-product-to-completion` (exploratory) |
| Spec implies whole-app redesign | `design-integration` (exploratory) |
| Spec implies doc/onboarding gaps only | `doc-sync` (shipped) |

**Empirical note:** Tier 2 full review gate — the frozen spec is the control artifact. Anything
not in `docs/product-spec.md` after T-FREEZE is out of scope for downstream builders.

## GOAL

Produce a **frozen, review-approved product specification** that answers: who it is for, what wedge
it owns, what is explicitly out of scope, success metrics, UX constraints, and a phased build order.
Zero implementation PRs in this mission — only spec artifacts and review evidence.

## ROLE PIPELINE

- @claude runs **office-hours-style forcing questions** (demand, status quo, desperate specificity,
  narrowest wedge, observation, future-fit) and drafts the spec skeleton.
- @claude runs **plan review lenses** (CEO scope, design UX, eng execution, optional DX) — via
  gstack `autoplan` when installed, else sequential T-REVIEWS tasks.
- A fresh @claude **skeptic pass** narrows scope creep and flags unvalidated assumptions.
- @claude **FREEZES** `docs/product-spec.md` and writes `<LEDGER_DIR>/framing-readiness.md` with
  `fleet-outcome` YAML.

## LEDGER

`<LEDGER_DIR>/framing-progress.md`. Per-task flags: `PLANNED=<t/f> BUILT=<t/f> REVIEWED=<t/f>
SHIPPED=<t/f>`.

Frozen index: `docs/framing-index.md` — table of spec sections with `DRAFT | REVIEWED | FROZEN`
and links to review notes.

## TASK STRUCTURE

- **T-FRAME [@claude]** — office-hours forcing questions; capture answers in
  `<LEDGER_DIR>/framing-progress.md`. Output draft `docs/product-spec.md` (sections: Problem, Wedge, User,
  Non-goals, Success metrics, UX principles, Phased roadmap).
- **T-REVIEWS [@claude, sequential or autoplan]** — run CEO, design, eng (and DX if applicable)
  reviews against the draft. Each lens appends a short verdict block to `docs/framing-index.md`.
- **T-SKEPTIC [@claude, fresh session]** — challenge assumptions; mark refuted claims in
  `docs/framing-index.md`; trim scope creep in spec.
- **T-FREEZE [@claude, gated on T-REVIEWS+T-SKEPTIC]** — set spec status FROZEN; no further edits
  without new mission run. Output `<LEDGER_DIR>/framing-readiness.md` with **`fleet-outcome` YAML**
  (`spec_frozen`, `open_questions`, `recommended_next_missions`).

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `<LEDGER_DIR>/framing-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission product-framing DONE: <LEDGER_DIR>/framing-progress.md all task flags true,
<LEDGER_DIR>/framing-readiness.md with fleet-outcome.status done and spec_frozen=true,
./scripts/validate-fleet-outcome.sh passes.
```

## DONE

`docs/product-spec.md` marked FROZEN, every framing-index row `FROZEN`, all tasks
`PLANNED=t REVIEWED=t SHIPPED=t`, `<LEDGER_DIR>/framing-readiness.md` exists with valid fleet-outcome.
Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)

- **No code PRs** — any implementation urge → Deferred missions table.
- Wedge beats breadth; explicit non-goals are mandatory.
- gstack review skills are advisors; fleet frozen ledger is authoritative.
- Ambiguity → smaller scope, sharper wedge, measurable success metric.
- If user cannot answer a forcing question, record as `open_question` — do not invent demand.