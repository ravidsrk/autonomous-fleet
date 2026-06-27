---
name: browser-qa-fix
description: >-
  [Tier 2 · moderate autonomy · full review gate · browser-grounded] Systematically QA a web
  application via real browser sessions, freeze findings with screenshot EVID, then fix and
  re-verify in a loop until health score meets threshold. Maps gstack /qa + /browse + /qa-only
  into fleet worktrees with build-blind review. Use when a staging or local URL exists and the
  user wants "test the site and fix bugs", "browser QA", or "dogfood this flow". Trigger on:
  "browser qa fix", "test the site and fix", "QA this app", "find UI bugs and fix them",
  "run QA on staging".
license: MIT
compatibility: Requires git and gh CLI; target app reachable at a URL (local or staging)
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
status: exploratory
---

> **Status: exploratory.** Derived from gstack `qa`, `qa-only`, and `browse`; not yet proven on
> an external repo archive. See `docs/exploratory/missions/README.md`.


# Mission: browser-qa-fix

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md`, `references/composition.md`, EVID rules
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `browse` / `gstack-browse` (gstack) | Headless `$B` or gstack browse daemon available | Playwright CLI / `browser` skill per adapter |
| `qa-only` (gstack) | User wants report-only pass first | T-QA-SCAN still runs; fix loop skipped until user confirms |
| `design-review` (gstack) | Visual/regression sampling after fixes | Screenshot diff in EVID only |
| `health` (gstack) | User wants composite health scorecard | Mission before/after health fields in readiness doc |

Community catalog: `autonomous-fleet-core` → `references/community-skills.md`. At most 2 optional
skills active.

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @grok (browser repro + fix) | `browser`, `qa` (gstack) when browse stack installed | Adapter browser tools + manual repro steps |
| @claude (QA plan, blind review) | — | Mission review gate |
| @claude (integrator) | — | Mission ship gate |

**Builder choice:** @grok retained for browser/visual fix loops (gstack `/qa` precedent). Fresh
build-blind @claude reviews each fix PR.

## Deferred missions

Record in `docs/qa-readiness.md` under **Recommended next missions**.

| Finding type | Route to |
|--------------|----------|
| Backend-only bug (no browser repro) | `bug-batch` (exploratory) |
| Systemic architecture issue | `adversarial-review-and-fix` (shipped) |
| Missing test coverage for fixed area | `test-coverage` (shipped) |
| Full design parity drift | `landing-page-convergence` (exploratory) |

## TARGET URL (user supplies)

Staging URL, preview deploy URL, or `http://localhost:<port>` with explicit start command recorded
in `docs/qa-progress.md`. HARD EXTERNAL DEPENDENCY if app cannot be reached — pause and document.

## GOAL

Drive a web app from **known-broken or unknown** to **QA health threshold met** with every
confirmed defect closed via a PR, each with browser EVID (screenshot + steps), and a before/after
health summary.

## ROLE PIPELINE

- @claude compiles **user-story checklist** and QA tier (Quick / Standard / Exhaustive per gstack
  `/qa` semantics).
- @grok (or coordinator with browse tools) **executes browser repro** for each story; failures →
  frozen `docs/qa-index.md` rows with EVID paths under `.fleet/evidence/` or `docs/qa-evidence/`.
- @grok **fixes** one defect per PR; attaches EVID after-state.
- Fresh build-blind @claude **reviews** each fix (repro replay + regression risk).
- @claude **integrates** and updates health scores in ledger.

## LEDGER

`docs/qa-progress.md` — per-story flags + rolling health score (before/after).

Frozen index: `docs/qa-index.md` — columns: `id`, `severity`, `story`, `repro_steps`, `evid_before`,
`fix_pr`, `evid_after`, `status: OPEN|FIXED|WONTFIX`.

## EVID GATE

Every OPEN row in qa-index must have `evid_before` with: URL, viewport, steps, screenshot path,
timestamp. FIXED requires `evid_after` replaying same steps. Screenshot existence alone is not
sufficient — steps must be copy-pasteable.

## TASK STRUCTURE

- **T-QA-PLAN [@claude]** — ingest URL + tier; write story checklist to `docs/qa-progress.md`;
  seed `docs/qa-index.md`.
- **T-QA-SCAN [@grok + browse]** — run stories; record failures with EVID; compute **health_before**.
- **T-FIX-LOOP [per qa-index OPEN row]** — @grok fix → fresh @claude review → @claude ship →
  update row FIXED + evid_after.
- **T-FINAL [@claude]** — re-run full scan at chosen tier; **health_after** must meet threshold
  (Quick: no critical/high open; Standard: no medium+; Exhaustive: cosmetic catalogued only).
  Output `docs/qa-readiness.md` with **`fleet-outcome` YAML** (`health_before`, `health_after`,
  `defects_open`, `defects_fixed`).

## Runtime goal

```
Mission browser-qa-fix DONE: docs/qa-progress.md complete, docs/qa-readiness.md with
fleet-outcome.status done, health_after meets tier threshold,
./scripts/validate-fleet-outcome.sh passes.
```

## DONE

All in-scope qa-index rows `FIXED` or `WONTFIX` with documented rationale, health threshold met,
all fix PRs merged, `docs/qa-readiness.md` with fleet-outcome present.

## DECISION DEFAULTS (mission-specific)

- Browser repro beats log-only claims; no fix without EVID before-state.
- One defect per PR; atomic commits per gstack `/qa` convention.
- Flaky repro → mark `FLAKY` in index, do not fix until repro stable.
- Cosmetic defects deferred in Quick tier; included in Exhaustive.
- If browse daemon unavailable, fall back to Playwright with same EVID schema.