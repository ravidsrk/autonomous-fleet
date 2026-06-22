---
name: dependency-update
description: >-
  [Tier 1 · among the highest cross-agent merge-success categories (build/chore) · safe to run unattended] Update a
  repo's dependencies to current versions, fix the breakages each bump causes, and keep the
  suite green — one PR per logical group. Use when deps are stale, for routine maintenance,
  to clear security advisories, or before building on an old base. Handles version bumps,
  lockfile updates, and the code/config changes a bump requires (deprecations, renamed APIs,
  breaking changes); does NOT add features. Runs fully autonomously via the
  autonomous-fleet-core engine. Trigger on: "update dependencies", "bump packages", "our
  deps are out of date", "upgrade to latest", "fix security advisories", "dependency
  maintenance".
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "1"
  fleet-component: "mission"
---

<!-- Corpus: prompts.md L2961 (Stage 8 Tier 1 grouping) + Stage-9 prompt 22 "Upgrade-Everything-to-Latest (majors included, one-major-per-PR)" at prompts.md L3003. -->


# Mission: dependency-update

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| — | — | — |

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (bump, fix, integrator) | — | Package manager docs + changelogs |

## Deferred missions

Record in `docs/dependency-update-readiness.md` under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Major upgrade = migration in its own right | `targeted-migration` |
| Advisory exposes architectural flaw | `adversarial-review-and-fix` |
| Post-bump doc drift | `doc-sync` |

**Empirical note:** Documentation, CI, and build-update tasks show the highest merge-success
rate among AI-agent PRs (arXiv 2601.15195 — Ehsani et al., MSR 2026, AIDev dataset of ~33k PRs).
Dependency updates fall in the build/chore category — among the highest-trust, safe unattended.
Risk concentrates in MAJOR version bumps with breaking changes; isolate and test those carefully.

## GOAL
Bring dependencies to current, compatible versions with the suite green. For each update: bump
the version, update the lockfile, and make whatever code/config changes the bump requires
(handle deprecations, renamed/moved APIs, breaking changes per the changelog). Prioritize
security advisories. Group related non-major deps so each PR is coherent and reviewable; isolate
MAJOR bumps under the maximal posture below. Never leave the build red or tests failing.

## ROLE PIPELINE
- @claude plans the update groups, performs the bumps, and fixes resulting breakages.
- @codex REVIEWS each PR (fresh, build-blind): correct target versions, breakages properly fixed
  (not papered over), suite green, no behaviour drift introduced by the upgrade.
- @claude is the INTEGRATOR: opens PR, merges (conflict-aware), cleans worktree.

## LEDGER
`docs/dependency-update-progress.md`. Per-task flags: `BUMPED=<t/f> FIXED=<t/f> PR_OPEN=<t/f>
REVIEWED=<t/f> MERGED=<t/f>`. Plus an UPDATE INDEX: each dep/group with from→to version, security
flag, `OPEN | DONE via PR#n`.

## TASK STRUCTURE
- **T-AUDIT [@claude]** — inventory current vs latest for every dependency; flag security
  advisories; identify which are safe minors/patches vs major/breaking; propose logical UPDATE
  GROUPS for non-majors (e.g. a framework + its plugins together), and order majors by dependency
  floor (runtime/toolchain first, then dependents). Output `docs/dependency-update-audit.md`.
  Freeze, then update.
- **T-UPDATE… [per group, loop]** — each non-major group is one PR; each MAJOR bump is one PR.
  @claude bumps + updates lockfile + fixes breakages, runs build + full suite green → @codex
  reviews (right versions, breakages truly fixed, suite green) → @claude merges. Treat
  manifest+lockfile pairs as the universal hot file: serialize manifest-mutating tasks, and
  parallelize only independent ecosystems. Security fixes first. Update the UPDATE INDEX.
- **T-FINAL [@claude]** — build green, full suite green, no remaining known-vulnerable versions
  in scope. Output `docs/dependency-update-readiness.md` with **`fleet-outcome` YAML**
  (`advisories_open`, `majors_deferred`), update index done, versions
  before/after, advisories cleared, any deferred majors with reasoning, all PRs). Ship as the
  final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/dependency-update-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission dependency-update DONE: docs/dependency-update-progress.md all task flags true,
docs/dependency-update-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Every UPDATE-INDEX item `DONE` (or explicitly deferred with reasoning), every task terminal,
build + suite green, `docs/dependency-update-readiness.md` exists. Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)
- Security advisories first. A bump that fixes a CVE outranks a routine version bump.
- For a MAJOR/breaking bump, use maximal posture by default:
  one MAJOR per PR, never batched. A green build after several majors tells you nothing about
  which major broke what. Include only the ecosystem packages that must move with that major.
- For a MAJOR/breaking bump, research before code: read the changelog/migration guide for the
  crossed range, apply the official codemod before touching code, and fix the code properly. "Bump
  and pray" is reviewer FAIL; never pin-around or suppress to make it "pass" without migrating.
- For a MAJOR/breaking bump, dependency-order the work: runtime/toolchain floor first, then the
  packages, plugins, and apps that depend on that floor.
- Treat manifest+lockfile as the universal hot file. Any task mutating a manifest serializes with
  any task mutating its lockfile; independent ecosystems may still run in parallel.
- If a MAJOR/breaking bump will not go green after 3 fix rounds, mark it BLOCKED with the concrete
  reason, park it as a DRAFT PR, record it in DECISIONS.md/readiness, and keep the rest of the
  update campaign moving.
- Group related non-major packages into one coherent PR; don't bump a framework without its
  ecosystem.
- If audit proves a major upgrade is a migration in its own right before an update PR starts,
  DEFER it with reasoning in DECISIONS.md and note it for the targeted-migration mission.
- Suite must be green after every group; never merge a red bump.
- Any ambiguity → the safest upgrade path that keeps the suite green and clears the most risk.
