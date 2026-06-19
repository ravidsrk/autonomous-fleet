---
name: dependency-update
description: >-
  [Tier 1 · high autonomous success ~0.84-0.87 merge · safe to run unattended] Update a
  repo's dependencies to current versions, fix the breakages each bump causes, and keep the
  suite green — one PR per logical group. Use when deps are stale, for routine maintenance,
  to clear security advisories, or before building on an old base. Handles version bumps,
  lockfile updates, and the code/config changes a bump requires (deprecations, renamed APIs,
  breaking changes); does NOT add features. Runs fully autonomously via the
  autonomous-fleet-core engine. Trigger on: "update dependencies", "bump packages", "our
  deps are out of date", "upgrade to latest", "fix security advisories", "dependency
  maintenance".
license: MIT
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "1"
  fleet-component: "mission"
---


# Mission: dependency-update

Apply the **autonomous-fleet-core** engine on your active adapter (load the core; load your runtime adapter; follow all core machinery) with the
parameters below.

**Empirical note:** chore/build tasks (which dependency updates are) merge at ~0.84-0.87 — among
the highest-trust categories, safe unattended. Risk concentrates in MAJOR version bumps with
breaking changes; group and test those carefully.

## GOAL
Bring dependencies to current, compatible versions with the suite green. For each update: bump
the version, update the lockfile, and make whatever code/config changes the bump requires
(handle deprecations, renamed/moved APIs, breaking changes per the changelog). Prioritize
security advisories. Group related deps so each PR is coherent and reviewable. Never leave the
build red or tests failing.

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
  GROUPS (e.g. a framework + its plugins together). Output `docs/dependency-update-audit.md`.
  Freeze, then update.
- **T-UPDATE… [per group, loop]** — each group is one PR. @claude bumps + updates lockfile +
  fixes breakages (read changelogs/migration notes for majors), runs build + full suite green →
  @codex reviews (right versions, breakages truly fixed, suite green) → @claude merges. Sequence
  groups that touch shared config; parallelize independent ones. Security fixes first. Update the
  UPDATE INDEX.
- **T-FINAL [@claude]** — build green, full suite green, no remaining known-vulnerable versions
  in scope. Output `docs/dependency-update-readiness.md` (update index done, versions
  before/after, advisories cleared, any deferred majors with reasoning, all PRs). Ship as the
  final PR.

## DONE
Every UPDATE-INDEX item `DONE` (or explicitly deferred with reasoning), every task terminal,
build + suite green, `docs/dependency-update-readiness.md` exists. Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)
- Security advisories first. A bump that fixes a CVE outranks a routine version bump.
- For a MAJOR/breaking bump, read the changelog/migration guide and fix the code properly — never
  pin-around or suppress to make it "pass" without actually migrating.
- Group related packages into one coherent PR; don't bump a framework without its ecosystem.
- If a major upgrade is genuinely large (a migration in its own right), DEFER it with reasoning
  in DECISIONS.md and note it for the targeted-migration mission — don't half-do it here.
- Suite must be green after every group; never merge a red bump.
- Any ambiguity → the safest upgrade path that keeps the suite green and clears the most risk.
