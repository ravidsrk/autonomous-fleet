<!-- title: adversarial-review-and-fix | description: Code-grounded adversarial review that freezes into a spec, then closes every confirmed finding one at a time. | sidebar_order: 7 -->

# adversarial-review-and-fix

**On this page:** [When to use it](#when-to-use-it) · [What it produces](#what-it-produces) ·
[What it expects from your repo](#what-it-expects-from-your-repo) ·
[Common failure modes](#common-failure-modes) · [Quick install](#quick-install) ·
[Learn more](#learn-more)

<p align="center">
  <img src="assets/banner.png" alt="adversarial-review-and-fix, autonomous-fleet skill" width="100%">
</p>

> Run a rigorous CODE-GROUNDED adversarial architecture review of a repo, freeze it as the source
> of truth, then close every confirmed finding one at a time until done. Phase 0 reviews the actual
> source (not existing docs) and a skeptic narrows out false findings; Phase 1 fixes the confirmed
> set with full safety rails. Runs on the autonomous-fleet-core engine.

🟪 **Tier 2 · Mission**: the two-phase red-team-then-patch workhorse: review freezes into a spec,
fixes close against it.

```
 PHASE 0 (freeze the spec)             PHASE 1 (close the findings)
 ┌──────────────┐  ┌──────────────┐    ┌─────────┐  ┌──────────────┐  ┌────────────┐
 │ @claude      │─▶│ @codex       │─▶  │ @codex  │─▶│ fresh        │─▶│ @claude    │
 │ REVIEWER     │  │ SKEPTIC      │    │ BUILDS  │  │ build-blind  │  │ INTEGRATES │
 │ (from code)  │  │ confirm /    │    │ one fix │  │ @claude      │  │ conflict-  │
 │              │  │ refute       │    │ per task│  │ REVIEWS      │  │ aware merge│
 └──────────────┘  └──────────────┘    └─────────┘  └──────────────┘  └────────────┘
   confirmed findings = the frozen Phase 1 spec; refuted = never fixed
```

## When to use it

- You want a security, architecture, and reliability hardening pass on a whole repo.
- You need a pre-production audit-and-remediate, not just a report you then have to act on.
- You'd say "review the whole app and fix everything" or "harden this before production".
- You already have a frozen audit doc and only want the fixes: pass it as `__REVIEW_DOC__` to enter
  FIX-ONLY MODE, which skips Phase 0, transcribes findings verbatim, and runs only Phase 1.
- You want findings graded by lane: Lane A auto-merges, Lane B drafts both variants behind a human
  gate, Lane 0 ships a code mitigation and queues the out-of-band action.

## What it produces

- `docs/adversarial-review-fresh.md`, the frozen review: ranked, dependency-ordered findings, each
  with file:line evidence, a concrete fix, acceptance criteria, and a CODE vs CODE+OPS tag.
- `.fleet/runs/<run_id>/p0-review-findings.json` and `p0-skeptic-findings.json`, schema-verified
  findings (conformant to `fleet-review-findings.schema.json`), each quote checked against source.
- `docs/arch-build-progress.md`, the ledger: PHASE marker, the finding CLOSE-INDEX with each
  finding's lane and state, and per-fix-task rows flagged `CODED EVID PR_OPEN REVIEWED MERGED ACCEPT`.
- `docs/arch-ops-actions.md`, `HUMAN_ACTION_REQUIRED:<finding-id>` entries for Lane 0 OPS work.
- `docs/arch-build-readiness.md`, the final report, starting with a `fleet-outcome` YAML block
  (`p0_open`, `p1_open`, `findings_open`, `ops_queue_count`), then finding status and every PR.
- One PR per fix task, plus a final PR. Lane B findings open as `do-not-merge` labelled draft PRs.

## What it expects from your repo

- `git` and the `gh` CLI available in the target repo: the mission opens real PRs against it.
- A default branch at a clean HEAD. The mission branches BASE off it and writes fresh outputs. Any
  prior review docs or in-flight review branches are OUT OF SCOPE: not read, reused, or overwritten.
- `autonomous-fleet-core` plus one runtime adapter active. The final form needs `@codex` to build
  and a `@claude` reviewer in a separate fresh terminal (the cross-vendor build-blind reviewer rule).
- Reproducible evidence per finding. The EVID gate closes a finding only when its exact reproduction
  command stops reproducing, so a discoverable way to run the repro helps.

## Common failure modes

- Reviewer hallucination: a finding whose `quoted_line` does not match the cited source halts the run
  at P0-REVIEW. See [Troubleshooting](../../docs/guide/14-troubleshooting.md) → verification failure.
- Empty or missing `__REVIEW_DOC__` in FIX-ONLY MODE is a hard surface, not a spin-up. See
  [Troubleshooting](../../docs/guide/14-troubleshooting.md) → install/auth.
- Run-archive validation: blind-fix-before-findings and readiness-newest mtime ordering must hold or
  the manifest is rejected. See [Troubleshooting](../../docs/guide/14-troubleshooting.md) → archive validation.
- Shipping with `unverified_findings > 0` is a HARD precondition failure: status is `partial`, not
  `done`. See [Troubleshooting](../../docs/guide/14-troubleshooting.md) → mutation gate.
- A fix that is CI-green but never exercised the production path is not terminal evidence. See
  [Troubleshooting](../../docs/guide/14-troubleshooting.md) → verification failure.

## Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill adversarial-review-and-fix -y
```

Then activate in your agent (Claude Code, Cursor, Grok, Codex, or Orca) and reference by name.

## Learn more

- [Guide chapter 09 §adversarial](../../docs/guide/09-mission-catalog.md), the depth on this mission
- [SKILL.md](./SKILL.md), the agent-facing spec

[📖 Guide Index](../../docs/guide/README.md)
