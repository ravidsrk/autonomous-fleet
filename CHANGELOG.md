<!-- title: Changelog | description: Release history for autonomous-fleet, Keep-a-Changelog style. | sidebar_order: 99 -->

# Changelog

All notable changes to `autonomous-fleet` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project has not cut a tagged
release yet, so everything to date lives under `[Unreleased]`, grouped by the date the work
landed on `main`. Dates are the merge dates in IST.

**On this page:** [Unreleased](#unreleased) · [Conventions](#conventions)

> No git tags exist yet. When the first version is tagged, the entries below move under a
> versioned heading and `[Unreleased]` resets to empty.

## [Unreleased]

### 2026-06-24

Added

- User-facing docs site plan (Stage 1 pure-markdown guide, Stage 2 Starlight-ready), refreshed
  against `main` after PR #41.

### 2026-06-23

Added

- Inference-cost measurement harness (`analyze_cost`) with a measurement-first gate and a
  routing audit, plus a mutation entry pinning the aggregation.
- Structured trace stream (`emit_trace.py`, `fleet-trace.schema.json`) as the vibe-kanban /
  Agent View telemetry contract.
- Run-archive example fixture with a size cap, covered by a generator smoke test.
- Adversarial benchmark driver and comparator scaffolding.
- Write-lock discipline and seat analysis (`analyze_seat.py`).

Changed

- Demoted nine unproven missions to `docs/exploratory/missions/`, leaving three shipped
  missions: `doc-sync`, `test-coverage`, `adversarial-review-and-fix`.
- Refreshed the marketplace packet for re-submission.

Fixed

- Addressed post-merge deep-review findings: trace ordering (T-FINAL now emits before the
  manifest write), `details` redaction enforced by `validate_event` + `emit()`, lock
  second-liveness safety, and removal of a coverage-hack test.

### 2026-06-22

Added

- Four-layer verification substrate: schema-enforced findings (Layer 1), the stop-verify hook
  (Layer 2), the blind-fix mechanical guard (Layer 3), and the run-archive mutation gate
  (Layer 4).
- Per-layer `FLEET_DISABLE_*` kill switches across all four layers.
- Mutation coverage tests for the verification substrate.

Changed

- Moved the stop-verify hook into the Claude Code adapter.
- Collapsed `STOP_VERIFY_DISABLED` into one kill-switch knob per layer.

Fixed

- Constrained `verify_findings` paths, size-capped reads, and hardened glob/count edges.

### 2026-06-21

Added

- Way-ahead roadmap plan (six commits ordered A through F, ground-truth-first).
- Per-mission role-topology regression guards.

Changed

- Enforced the canonical `@codex`-builds / fresh-`@claude`-reviews role topology.
- Made shellcheck version-robust in CI and added least-privilege CI permissions, caching, and
  broader triggers.

Fixed

- Gated `--yolo` against external repos and pinned the `npx skills` version.
- Switched `skills-lock.json` to a GitHub source instead of an author-machine path.

### 2026-06-20 and earlier

Added

- Initial `autonomous-fleet` skill framework on the agentskills.io format with the `npx skills`
  CLI and `skill-creator` validation.
- The engine spec, distillation-discipline rule, and `docs/` index.

Fixed

- Closed P0/P1 findings from early audits: duplicate blocks, role drift, mission-count drift,
  and ungrounded citations.

## Conventions

This changelog is hand-curated from `git log --oneline --no-merges`, grouped by merge date and
categorized by commit-prefix intent (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`)
into Keep-a-Changelog buckets:

```text
Added      new capabilities, missions, scripts, schemas, docs
Changed    behavior or structure that already existed
Fixed      bug fixes and review-finding closures
Removed    deleted capabilities (none yet)
```

Every PR description should open with a one-line changelog entry so this file stays current. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the distillation discipline that governs what lands here.

← [Guide Index](README.md)
