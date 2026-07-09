---
title: "Mission catalog"
description: "Every shipped autonomous-fleet mission: what it does, what it expects, what it produces, and how to run it, plus the exploratory roster and what each needs to ship."
sidebar:
  order: 9
---

# Mission catalog

A mission is the unit of work in autonomous-fleet. You point one at a repo, it freezes a plan,
spawns a fleet of workers, and lands a series of small PRs with an audit trail. This chapter is
the reference for picking the right one.

Three missions ship today with real-run evidence behind them: `doc-sync`, `test-coverage`, and
`adversarial-review-and-fix`. Everything else lives in `docs/exploratory/missions/` and is not
active until it earns the three-artifact promotion gate (covered at the end of this chapter).

If you have not read [Missions vs campaigns](/05-missions-vs-campaigns/) yet, read it first. It
explains the difference between running one mission and chaining several behind verification gates.
This chapter is about the single mission. Chaining is [Campaigns](/10-campaigns/). Writing a new
mission from scratch is [Extending](/13-extending/), not here.

**On this page:** [How to read a mission entry](#how-to-read-a-mission-entry) ·
[doc-sync](#doc-sync) · [test-coverage](#test-coverage) ·
[adversarial-review-and-fix](#adversarial-review-and-fix) ·
[Choosing between missions](#choosing-between-missions) ·
[The exploratory roster](#the-exploratory-roster) ·
[Promotion criteria](#promotion-criteria)

## How to read a mission entry

Every shipped mission below uses the same template, so you can scan for the field you care about
without reading the whole section:

```
What it does            One paragraph. The job, stated plainly.
When to use it          The trigger phrases and the real situations.
Input contract          What the mission expects from your repo before it starts.
Output contract         The ledger, the readiness doc, the fleet-outcome metrics.
Typical PRs it produces  The shape and granularity of what lands on your base branch.
Role pipeline           Who builds, who reviews, who integrates.
Edge cases              The corners the mission handles in a specific way.
Failure modes           What goes wrong and where to look (Troubleshooting cross-refs).
Example invocations     Copy-pasteable kickoffs.
```

A few terms recur. A quick gloss, with the full definitions in the [Glossary](/20-glossary/):

```
Ledger        A progress file the coordinator writes as it runs (docs/<mission>-progress.md).
Readiness doc The mission's final report (docs/<mission>-readiness.md), opened with a
              fleet-outcome YAML block.
fleet-outcome The machine-readable result block. status is done | partial | blocked, plus
              per-mission metrics that downstream campaign gates read.
Build-blind   The reviewer never saw the builder's conversation. It is handed the diff plus an
              acceptance contract as text only. This is structural, not a polite request.
```

One rule applies to every mission: one mission per repo at a time. A mission freezes a plan and
opens many PRs against one base branch. Two missions racing on the same repo means two frozen
plans fighting over the same files. To chain missions, use a [campaign](/10-campaigns/), which
runs them in sequence behind gates, never concurrently on the same base.

## doc-sync

> Tier 1. Highest cross-agent merge-success category (documentation). Safe to run unattended.

### What it does

`doc-sync` makes a repo's documentation TRUE to its current code. It reads the code and the docs
together, builds a frozen DRIFT INDEX of every place they disagree, then fixes the docs, one doc
area per PR. It never bends the code to match stale docs. Code is the ground truth; the docs move.

Scope covers `README`, everything under `docs/`, `AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING`,
API and reference docs, setup / install / usage instructions, configuration docs, and code-level
doc comments and inline examples that have drifted or no longer run.

This is a documentation mission only. It does not change application behaviour, logic, APIs, or
the meaning of tests. If a doc reveals an actual code bug, `doc-sync` does not fix the code. It
records the bug as a finding in `DECISIONS.md` for a separate mission.

### When to use it

- Docs are stale after a refactor or a dependency change.
- Onboarding or setup instructions are wrong and new contributors hit walls.
- The README claims behaviour the code no longer has.
- You want a periodic documentation-truth pass before a release.

Trigger phrases: "sync the docs", "our README is out of date", "docs don't match the code",
"update documentation", "fix onboarding/setup instructions", "documentation audit".

There is an empirical reason this is Tier 1. Documentation, CI, and build-update tasks show the
highest merge-success rate among AI-agent PRs (arXiv 2601.15195, Ehsani et al., MSR 2026, AIDev
dataset of ~33k PRs). Doc fixes are mechanically checkable: an example either runs or it does not,
a link either resolves or it does not. That checkability is why `doc-sync` is safe to run
unattended.

### Input contract

```
Requires    git and gh CLI in the target repository.
Assumes     There is documentation to sync (a README at minimum). A repo with no docs
            gives doc-sync nothing to do.
Best on     A repo whose examples and commands can actually be run in the run environment,
            so the verifier can prove each one works rather than eyeball it.
```

### Output contract

The ledger is `docs/doc-sync-progress.md`. Each task carries the flags
`WRITTEN=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f> MERGED=<t/f>`, plus a DRIFT INDEX where every
doc-vs-code discrepancy is tracked `OPEN | CLOSED via PR#n`.

The audit output is `docs/doc-sync-audit.md`, the frozen DRIFT INDEX produced by the single
discovery task.

The final report is `docs/doc-sync-readiness.md`. It opens with a `fleet-outcome` YAML block, then
a drift summary, then Recommended next missions. The metrics block carries:

```yaml
fleet-outcome:
  status: done # done | partial | blocked
  metrics:
    drift_open: 0 # every DRIFT-INDEX item must be CLOSED for status: done
    code_bug_findings: 0 # docs that revealed real code bugs, routed to another mission
```

`drift_open: 0` is the close condition. A run that ships with open drift items is `status:
partial`, not `done`.

### Typical PRs it produces

One PR per doc area, not one sweeping docs PR. `doc-sync` parallelizes across non-overlapping doc
files and serializes edits to the same file. A run on a repo whose README, setup guide, and API
reference all drifted produces roughly:

```
PR #1  doc-sync: align README with current install + usage
PR #2  doc-sync: fix setup guide (node version, env vars, gh auth step)
PR #3  doc-sync: correct API reference signatures + dead example commands
PR #N  doc-sync: readiness, drift_open: 0, code_bug_findings: 1   (the final PR)
```

The many-small-PRs shape is deliberate. Small per-area PRs merge at a higher rate than one giant
docs PR, and each one is independently reviewable and revertable.

### Role pipeline

```
@claude    AUDITS: produces the frozen DRIFT INDEX (the only discovery task).
@codex     WRITES the doc fixes, running each example/command to verify it works.
@claude    REVIEWS each PR build-blind: confirms the doc now matches the code, examples
           run, links resolve, nothing factually wrong remains. Fresh terminal.
@claude    INTEGRATES: opens the PR, merges conflict-aware, cleans the worktree.
```

The reviewer is a fresh build-blind @claude: a different session than the one that wrote the fix,
handed the diff and the acceptance criteria as text only. See
[Roles and blindness](/08-roles-and-blindness/) for why the reviewer is structurally separated
rather than just instructed to be impartial.

### Edge cases

- A doc reveals a real code bug. `doc-sync` does not touch the code. It records the bug in
  `DECISIONS.md` and lists `bug-batch` under Recommended next missions in the readiness doc.
- A broken setup step that is a dependency problem, not a wording problem, routes to
  `dependency-update` rather than being patched as prose.
- An undertested area surfaced during the audit routes to `test-coverage`.
- The mission preserves the docs' existing voice and structure. It corrects content, it does not
  restyle gratuitously.

### Failure modes

- An example command cannot run in the environment, so the verifier cannot prove it works. The
  fix lands only when the verifier can run it; otherwise the item stays OPEN. See
  [Troubleshooting](/14-troubleshooting/).
- Two doc areas turn out to overlap in the same file and a parallel edit conflicts. The engine
  serializes same-file edits, but if a conflict slips through it surfaces at integration. See
  [Troubleshooting](/14-troubleshooting/).
- The DRIFT INDEX is large and the run is interrupted. The ledger flags let a resumed run see
  which items are already CLOSED via which PR, so work is not redone.

### Example invocations

Interactive, on Claude Code, the chat / `/goal` path that is the supported flow today:

```
/doc-sync update the docs to match the code
```

Or the plain trigger phrasing the umbrella skill routes to `doc-sync`:

```
our README is out of date after the refactor, sync the docs
```

To install just this mission plus its dependencies:

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-claude-code \
  --skill doc-sync \
  -y
```

Replace `autonomous-fleet-adapter-claude-code` with `-orca`, `-grok`, or `-codex` for another
runtime. See [Installation](/02-installation/) for the full per-runtime setup.

## test-coverage

> Tier 1. Lower-than-doc/build cross-agent merge-success (test). Guard the hollow-test risk.

### What it does

`test-coverage` raises real test coverage on a repo or a named target area with
behaviour-exercising tests, not coverage-padding stubs. It maps the undertested areas by
importance, then fills them one area per PR, adding or strengthening unit, integration, and where
relevant UI tests that genuinely assert behaviour.

The defining constraint: every added test must FAIL if the behaviour it covers breaks. A test that
passes against intentionally-broken code is rejected. The mission chases real protection from
regressions, never a vanity coverage percentage. It does not change application logic to make
testing easier; if a change is needed for testability, it records that as a finding for another
mission.

### When to use it

- A module is undertested and you want a safety net before touching it.
- You are about to refactor and want to lock current behaviour first.
- A feature shipped without tests and you are paying down that debt.
- You want a periodic coverage pass on the regression-prone parts of the codebase.

Trigger phrases: "add tests", "raise coverage", "this module has no tests", "write tests for X",
"improve test coverage", "lock current behaviour with tests".

Tier 1, but with a real caveat. Test PRs merge at a materially lower cross-agent rate than
documentation and build-update tasks — roughly 61.5% versus ~84% for docs (same arXiv 2601.15195
dataset) — so the reviewer gate matters more here and this is not as hands-off as `doc-sync`: glance
at the result rather than leaving it fully unattended. Per-task merge rates vary by agent, so treat
the tier ordering as qualitative. The one failure mode to guard is hollow tests written to move a
number. The reviewer's explicit job is to reject those.

### Input contract

```
Requires    git and gh CLI in the target repository.
Assumes     A discoverable test runner and existing test framework (for example pytest, jest,
            or go test). The mapping task identifies the framework and conventions already in
            the repo, then matches them.
Best on     A repo where coverage tooling reports numbers, so before/after deltas can be
            recorded. The mission still works without coverage tooling; it just cannot report
            a delta.
```

### Output contract

The ledger is `docs/test-coverage-progress.md`, with per-task flags
`WRITTEN=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f> MERGED=<t/f>` and a GAP INDEX where each undertested
area is tracked `OPEN | COVERED via PR#n`, with before/after coverage where the tooling reports it.

The map output is `docs/test-coverage-map.md`, the frozen list of undertested areas ranked by
importance (core logic and regression-prone paths first, trivial getters last).

The final report is `docs/test-coverage-readiness.md`. It opens with a `fleet-outcome` YAML block:

```yaml
fleet-outcome:
  status: done # done | partial | blocked
  metrics:
    gaps_open: 0 # every GAP-INDEX item must be COVERED for status: done
    coverage_regressed: false # coverage must not regress anywhere
```

Both conditions hold for `status: done`: every gap COVERED and no regression elsewhere.

### Typical PRs it produces

One PR per area, parallelized across non-overlapping test files, serialized for same-file edits:

```
PR #1  test-coverage: cover the auth token refresh path (edge + error cases)
PR #2  test-coverage: cover the parser's empty/malformed-input branches
PR #3  test-coverage: regression tests for the date-rollover bug area
PR #N  test-coverage: readiness, gaps_open: 0, coverage_regressed: false   (final PR)
```

### Role pipeline

```
@claude    MAPS coverage gaps: the frozen GAP INDEX. Identifies the repo's test framework
           and conventions to match.
@codex     WRITES the tests: verifies they FAIL against intentionally-broken code, then pass.
@claude    REVIEWS each PR build-blind: tests assert real behaviour, would FAIL if the code
           broke (not tautological), cover meaningful paths, no coverage-padding, no logic
           changed. Fresh terminal.
@claude    INTEGRATES: opens PR, merges conflict-aware, cleans worktree.
```

### Edge cases

- A logic change is needed to make code testable. The mission does not make it. It records the
  need as a finding and routes to `bug-batch` or a scoped fix mission.
- A refactor is required for testability. It routes to `cleanup` (light) or `targeted-migration`,
  both of which are exploratory today.
- Only hollow coverage tooling exists. The mission uses the repo's existing test/coverage commands
  rather than introducing a new harness.
- No test framework exists at all. The mission matches the closest convention from the map rather
  than inventing a harness, unless none exists.

### Failure modes

- A test passes against the broken version of the code. The reviewer rejects it as tautological.
  The builder rewrites it to assert behaviour. See [Troubleshooting](/14-troubleshooting/).
- Coverage rises in the mapped area but regresses elsewhere. `coverage_regressed: true` blocks
  `status: done`. The run is `status: partial` until the regression is resolved.
- The full suite is red before the mission starts. The mapping task surfaces this; you cannot
  meaningfully add coverage on top of a broken suite.

### Example invocations

```
/test-coverage raise coverage on the payments module
```

Or a plain trigger:

```
this parser has no tests, write tests for it and lock the current behaviour
```

Install:

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-claude-code \
  --skill test-coverage \
  -y
```

## adversarial-review-and-fix

> Tier 2. Moderate autonomy, full review gate. The proven two-phase workhorse.

### What it does

`adversarial-review-and-fix` is a two-phase mission. Phase 0 runs a rigorous CODE-GROUNDED
adversarial review of the repo (reading the actual source, not existing docs), then a skeptic pass
narrows out false findings, and the confirmed set is FROZEN as the source of truth. Phase 1 closes
every confirmed finding one at a time with full safety rails, until done.

The structural key is that Phase 0 produces a frozen, richly-shaped review document BEFORE any
fixing begins, so Phase 1 executes against a finished spec rather than judging and fixing in one
loop. The skeptic pass exists to stop the fix loop from chasing phantom findings.

A "CLOSED" finding means the fix is implemented, a test exists where the fix calls for one, and
acceptance is demonstrated on staging / testnet / fixtures. The mission converges to the confirmed
fixes. It never reinterprets beyond them and never fixes a refuted non-issue.

### When to use it

- A security, architecture, or reliability hardening pass before production.
- A pre-production audit-and-remediate.
- "Review the whole app and fix everything."

Trigger phrases: "adversarial review and fix", "audit and remediate", "review the whole app and
fix the issues", "harden this before production", "find and fix the architecture problems".

This mission's fixes span fix / refactor / security work — categories AI agents merge at a lower
rate than documentation and build-update work (arXiv 2601.15195, Ehsani et al., MSR 2026) — so the
full review gate is essential. There is no published category-level merge rate for this composite,
and per-task merge rates vary by agent, so treat the tier ordering as qualitative. It is Tier 2
because it touches application logic, unlike the two Tier 1 missions which are documentation and
tests.

### Input contract

```
Requires    git and gh CLI in the target repository.
Fresh-run   If prior review docs or in-flight review branches exist, they are OUT OF SCOPE.
            The mission does not read, reuse, or overwrite them. It writes fresh outputs and
            branches BASE off the default branch at current HEAD. The review is grounded in
            the CODE, not in any existing doc.
Fix-only    If you supply an existing review/audit doc as __REVIEW_DOC__, the mission enters
            FIX-ONLY MODE: it skips Phase 0 entirely and runs only Phase 1 against your frozen
            findings (see Edge cases).
```

### Output contract

The ledger is `docs/arch-build-progress.md`. It carries a PHASE marker
(`REVIEW | REVIEW_FROZEN | FIXING | VERIFY`), a FINDING CLOSE-INDEX where every confirmed finding
ID is tracked by wave with its lane and state
(`OPEN | CLOSED via PR#n | CODE_CLOSED via PR#n (OPS: …) | HUMAN_GATED via PR#n`), and
per-fix-task rows with flags `CODED EVID PR_OPEN REVIEWED MERGED ACCEPT`.

`EVID` is the evidence-repro close-test: the worker re-runs the exact command from the finding's
Evidence block (the curl that returned the 500, the test that asserted the wrong value, the script
that reproduced the race) and sets `EVID=true` only when it no longer reproduces.

Phase 0 also emits machine-checkable findings. Alongside the markdown review doc
(`docs/adversarial-review-fresh.md`), the reviewer emits a JSON findings document conformant to
`autonomous-fleet-core/assets/fleet-review-findings.schema.json` at
`.fleet/runs/<run_id>/p0-review-findings.json`. Each finding's `evidence.quoted_line` must be the
exact verbatim line from the cited source file. The coordinator runs `scripts/verify_findings.py`
against it; if a finding's quote does not locate in the source, the run HALTS at P0-REVIEW.
Unverified findings are likely reviewer hallucination and must not enter the fix loop. The skeptic
emits a parallel `.fleet/runs/<run_id>/p0-skeptic-findings.json` carrying only the CONFIRMED set,
re-verified the same way.

The final report is `docs/arch-build-readiness.md`, opening with a `fleet-outcome` YAML block:

```yaml
fleet-outcome:
  status: done # done | partial | blocked
  run_id: <run_id>
  archive_enabled: true # set only after validate_run_archive.py passes
  metrics:
    p0_open: 0 # P0-severity findings still open
    p1_open: 2 # P1-severity findings still open
    findings_open: 0 # all confirmed findings closed for status: done
    ops_queue_count: 1 # out-of-band actions queued for a human
    # Optional, when schema-verified findings were used:
    verified_findings: 11
    unverified_findings: 0 # HARD precondition: must be 0 for status: done
    auto_applicable_findings: 9
    human_gated_findings: 2
```

`unverified_findings == 0` is a hard precondition for `status: done`. A T-FINAL that ships with
unverified findings still in flight is a reviewer-hallucination leak and must be `status: partial`
instead. `archive_enabled: false` is incompatible with `status: done`. The validator rejects that
combination, because the archive is the audit trail.

### Three lanes

Every confirmed finding is classified into one of three terminal lanes before fixing begins. The
engine defines the lanes (see [The engine](/06-the-engine/)); the mission records the lane in the
CLOSE-INDEX as `lane: A|B|0`:

```
Lane A   IMPLEMENT + MERGE. A normal fix task in the PR-per-task pipeline. Terminal flag
         MERGED=true.
Lane B   DRAFT-BOTH + HUMAN-GATE. Both variants drafted, recorded in DECISIONS.md, opened as a
         do-not-merge labelled draft PR. Terminal flag HUMAN_GATED=true. Never auto-merged.
Lane 0   REFUSE + SURFACE. The code-side mitigation ships in Lane A; the precise out-of-band
         action surfaces as HUMAN_ACTION_REQUIRED:<finding-id> in docs/arch-ops-actions.md.
         Terminal flags CODE_CLOSED=true, OPS_QUEUED=true.
```

### Typical PRs it produces

One PR per confirmed finding (or per FOUNDATION cluster), waves ordered P0s first, then FOUNDATION,
then the rest:

```
PR #1  fix(P0): close the auth bypass on the admin route   (Lane A, EVID re-run, MERGED)
PR #2  fix(P1): bound the unbounded retry loop             (Lane A)
PR #3  draft(do-not-merge): two options for the schema migration   (Lane B, HUMAN_GATED)
PR #N  adversarial-review-and-fix: readiness, findings_open: 0, ops_queue_count: 1   (final PR)
```

Lane 0 findings do not produce a merge. They surface as named human-action records in
`docs/arch-ops-actions.md` and as `ops_queue_count` in the metrics.

### Role pipeline

```
PHASE 0
  @claude    REVIEWER produces findings FROM THE CODE (Opus-class).
  @codex     SKEPTIC narrows/refutes AGAINST THE CODE → freeze the CONFIRMED set.

PHASE 1 (Stage-9 final form)
  @codex     BUILDS each fix. Re-runs the Evidence repro and sets EVID when it stops reproducing.
  @claude    REVIEWS each fix PR build-blind. Different terminal session than any prior @claude
             that touched this run. Handed the diff + acceptance contract as TEXT ONLY.
  @claude    INTEGRATES: opens PR, conflict-aware merge, worktree cleanup.
```

`@codex` never reviews its own work; the reviewer `@claude` never writes code; the integrator never
authors fixes. In the Stage-9 final form, `@grok` was retired from this pipeline.

There is one extra discipline worth knowing about. Before reading a builder's PR diff, the fresh
reviewer first reads only the finding, forms an independent hypothesis about the correct
point-of-creation fix, and writes that blind fix to
`.fleet/runs/<run_id>/reviewer-blind-fix-<finding-id>.md`. Only after that blind fix is committed
to disk does the reviewer open the candidate diff. A candidate fix at a different call-stack depth
than the blind fix triggers a `root_cause_depth` finding. This is the anti-anchoring rule; see
[The substrate](/07-the-substrate/).

### Edge cases

- FIX-ONLY MODE. When you supply `__REVIEW_DOC__` (an existing adversarial review, an audit
  dossier, a frozen finding set), the mission skips Phase 0 entirely, transcribes every finding ID
  into the CLOSE-INDEX verbatim (no renumbering, no silent dropping), classifies each into a lane,
  and runs only Phase 1. The supplied doc is the frozen truth; reinterpretation is forbidden.
- An empty or missing `__REVIEW_DOC__` is a hard surface, not a spin-up. If the doc is missing,
  empty, or has no confirmed findings, the coordinator surfaces it to you rather than spinning up a
  fix run with nothing to fix.
- A FOUNDATION cluster's root cause is fixed once and closes its dependent findings only when the
  shared PR satisfies every dependent finding's Evidence and acceptance gates.
- A finding needs load or production data the swarm cannot see. The mission ships code plus a plan,
  marks `CODE_CLOSED + VERIFY_AT_SCALE`, and never blocks the loop on data it cannot reach.

### Failure modes

- A reviewer hallucinates a finding whose quote does not exist in the source. `verify_findings.py`
  catches it and HALTS at P0-REVIEW. See [Troubleshooting](/14-troubleshooting/).
- A confirmed finding's Evidence repro still reproduces after the fix. `EVID` stays false, the
  finding stays OPEN, and the run does not reach `status: done`.
- The run-archive validator (`validate_run_archive.py`) exits non-zero because the mtime ordering
  of blind-fix / findings / verify-summary / readiness files is wrong. The fix is to re-create or
  re-order the misplaced file and re-emit the manifest before shipping. See
  [Run-archive anatomy](/15-run-archive/).

### Example invocations

```
/adversarial-review-and-fix harden this service before we ship to production
```

Fix-only, against an audit you already have:

```
run adversarial-review-and-fix in fix-only mode against docs/my-existing-audit.md
```

Install:

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-claude-code \
  --skill adversarial-review-and-fix \
  -y
```

## Choosing between missions

A quick decision aid. When the intent maps cleanly to one mission, run that mission. When it names
multiple missions or a conditional flow ("if the audit finds P0s, then…"), use a
[campaign](/10-campaigns/) instead.

```
+----------------------------------------+----------------------------+-------+
| You want to...                         | Mission                    | Tier  |
+----------------------------------------+----------------------------+-------+
| Make stale docs true to the code       | doc-sync                   | 1     |
| Lock behaviour / raise real coverage   | test-coverage              | 1     |
| Audit the app and fix what's confirmed | adversarial-review-and-fix | 2     |
| Run a healthy-repo pass (docs + tests) | repo-health campaign       | 10    |
| Audit then test then sync docs         | ship-with-proof campaign   | 10    |
| Audit then test, with post gates       | quality-gate campaign      | 10    |
+----------------------------------------+----------------------------+-------+
```

Two reasons to reach for the Tier 1 missions first on a repo you have not run the fleet on before:
they sit among the higher-merging cross-agent task categories, and they are the lowest-risk to run
with little supervision. `doc-sync` is the safest (documentation merges highest, ~84% cross-agent);
`test-coverage` merges lower (~61.5%), so glance at its result rather than leaving it fully
unattended. Per-task merge rates vary by agent, so treat the tier ordering as qualitative. Save
`adversarial-review-and-fix` for when you specifically want code changes behind a full review gate.

## The exploratory roster

Everything below is documented but not yet proven end-to-end. These missions live in
`docs/exploratory/missions/`, not in `skills/`, so the framework's shipped surface area maps 1:1
to missions with real-run evidence. They do not load via the umbrella skill. To run one, you must
promote it first (see [Promotion criteria](#promotion-criteria)) or invoke it manually as a one-off
operator action, knowing it has no field hours.

Each entry below is what the mission WOULD do if shipped, and what it is currently missing. The
gloss for each is drawn from `docs/exploratory/missions/README.md` and the mission catalog
reference. None of these has a progress doc, a readiness doc with a `fleet-outcome` block, and an
external-repo run-archive all three, which is exactly why they are here.

### Tier 1 candidates

```
cleanup
  Would do:  A behaviour-preserving code-health pass (dead-code removal, duplication kill,
             named anti-pattern fix) without re-architecting. The lightest counterpart to
             the archived full-rebuild design.
  Missing:   A readiness doc exists (docs/cleanup-readiness.md) but there is no progress doc
             and no external-repo run-archive. Demoted because the three-artifact rule
             requires BOTH a progress doc AND an external archive.

dependency-update
  Would do:  Update a repo's dependencies to current versions, fix bump breakages, keep the
             suite green, one PR per logical group. Would handle stale deps and security
             advisories autonomously.
  Missing:   No progress doc, no readiness doc, no external archive.
```

### Tier 2 candidates

```
bug-batch
  Would do:  Close a batch of bugs from a list/tracker/described set, one PR per bug, each
             gated by a FAILING TEST written first that reproduces the bug. Would force
             exactness on the agent-weakest category (bug fixes).
  Missing:   No progress doc, no readiness doc, no external archive.

targeted-migration
  Would do:  Migrate ONE axis of a codebase (framework version, library swap, language/runtime
             bump, DB/ORM change, API-version move) while preserving everything else and
             keeping the suite green. The one-axis-at-a-time slot between dependency-update and
             the archived full-rebuild design.
  Missing:   No progress doc, no readiness doc, no external archive.

design-integration
  Would do:  Adopt a fresh design across an existing product to full parity (visual AND
             feature-wise): reskin every screen and build the features the design implies but
             the product lacks. The whole-app-redesign counterpart to the archived single-page
             design-convergence variant.
  Missing:   No progress doc, no readiness doc, no external archive.

inference-cost
  Would do:  Reduce AI inference spend while holding output quality constant: measurement-first
             cost optimization with a baseline cost+quality harness, sanctioned levers only, and
             a hard refusal of subscription-token-as-backend hacks.
  Missing:   No progress doc, no readiness doc, no external archive.

browser-qa-fix
  Would do:  Browser-grounded QA with screenshot evidence and a fix loop until the target health
             threshold is met.
  Missing:   No progress doc, no readiness doc, no external archive.

incident-investigate
  Would do:  Root-cause analysis with a frozen incident RCA and a mandatory regression test.
  Missing:   No progress doc, no readiness doc, no external archive.
```

### Tier 3 candidates

```
take-product-to-completion
  Would do:  Drive a STALLED product to a full-fledged, shippable state via adversarial review +
             market research + a FROZEN COHERENT PRODUCT BOUNDARY + full-depth build inside that
             boundary. The flagship Tier 3 mission for finishing started-but-unshipped products.
  Missing:   No progress doc, no readiness doc, no external archive.
```

Three more missions (`scaffold-align`, `contract-first-build`, `agents-layer`) were moved to
`docs/exploratory/missions/` earlier, on 2026-06-22, for the same reason: they are not on the
Stage 8 distillation list and have no real-run evidence. They are not in the shipped surface.

> Note on archived campaigns. Because some exploratory or parked missions were nodes in campaign
> presets, the affected presets are archived in place. `align-then-ship`, `handoff-to-product`,
> `secure-ship`, and `gstack-quality` reference demoted or parked missions and are intentionally
> empty until those missions are promoted. Only `repo-health`, `ship-with-proof`, and `quality-gate`
> remain populated. See [Campaigns](/10-campaigns/).

## Promotion criteria

A mission may move back from `docs/exploratory/missions/<mission>/` to `skills/<mission>/` only
when all three of these artifacts exist and are cited in the promotion PR. This is the
three-artifact rule:

```
+----------------+---------------------------------------------------------------+
| Artifact       | Path                                                          |
+----------------+---------------------------------------------------------------+
| Progress doc   | docs/<mission>-progress.md  (a real run, not a stub)           |
| Readiness doc  | docs/<mission>-readiness.md with a fleet-outcome block         |
| External       | .fleet/runs/<run_id>/ produced by the mission, OR a referenced |
| archive        | archive under docs/external-dogfood/                           |
+----------------+---------------------------------------------------------------+
```

Doctrine alone is not sufficient. Tests inherited from `autonomous-fleet-core` are not sufficient.
The promotion PR must cite a real coding-agent run that produced the archive. A demotion can be
reversed; doctrine alone cannot promote. The artifact is the gate.

The promotion process itself (run the mission, archive the run, write the two docs, `git mv` the
skill back, strip the exploratory marker, update consumers, open the PR) is the contributor task
covered in [Extending](/13-extending/). This chapter only documents the criteria, not the
mechanics.

> Why the bar is this high. Keeping the shipped surface 1:1 with missions that have real-run
> evidence is the same honesty discipline the framework applies to its own claims. A mission you
> can run is a mission someone has actually run on a real repo and archived the result of. If you
> need one of the roster missions today, promote it through the gate above rather than trusting the
> doctrine alone.
## Real-world use cases

### Example — three shipped missions

Registry lint + `validate-headless.sh` iterate `doc-sync`, `test-coverage`,
`adversarial-review-and-fix` × grok/claude/codex dry-runs.

### Invocation — demoted missions stay exploratory

Twelve missions under `docs/exploratory/missions/` await external archive triple promotion —
documented in `docs/roadmap-gap-matrix.md` gap M-promote.

### Real run on adversarial fixture mission

`.fleet/runs/example-fixture/manifest.json` mission field:
`adversarial-review-and-fix` — canonical archive for the review-and-fix validators.

---

← [Roles and blindness](/08-roles-and-blindness/) ·
[Guide Index](/) ·
[Campaigns](/10-campaigns/) →
