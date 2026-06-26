<!-- title: Changelog | description: Release history for autonomous-fleet, Keep-a-Changelog style. | sidebar_order: 99 -->

# Changelog

All notable changes to `autonomous-fleet` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Dates are merge dates in IST.

**On this page:** [Unreleased](#unreleased) · [0.2.0](#020---2026-06-27) · [0.1.0](#010---2026-06-26) · [Conventions](#conventions)

## [Unreleased]

## [0.2.0] - 2026-06-27

Lane 1 + Lane 2 dogfood evidence, external archive emission, and adversarial-bench
infrastructure readiness.

### Added

- `record_headless_run` in `fleet_run` and `headless_trace` — alias for persisting headless archives.
- Tests for twice-emit on external git repos and post-runtime archive keep via `run-mission-headless.sh`.

### Changed

- `run-mission-headless.sh` — after real grok/claude/codex invocations, unconditionally emits and
  **keeps** `.fleet/runs/<run_id>/` under the target `--repo` (dry-run still cleans ephemeral copies).
- `docs/external-dogfood/gemoji-headless-run.md` — Lane 2 headless ship-with-proof evidence
  ([PR #56](https://github.com/ravidsrk/autonomous-fleet/pull/56), merge `87b9071`).
- `docs/external-dogfood/ship-with-proof-evidence.md` — interactive + headless validated.
- Adversarial bench docs (`adversarial-bench-2026-06.md`, `adversarial-bench-summary.md`, five
  per-target stubs) — status: infrastructure ready for operator A/B runs; metrics ⬜ pending.
- `docs/roadmap-gap-matrix.md` — A-real closed (Lane 1); C-bench / W-bench-pub headless path complete.

### Dogfood evidence (Lanes 1–2)

- **Lane 1:** First real substrate archive on `main`
  (`docs/external-dogfood/first-substrate-run.md`, PR #55).
- **Lane 2:** Headless `grok -p` + `run-campaign.sh --repo` on `ravidsrk/gemoji`
  (`docs/external-dogfood/gemoji-headless-run.md`, PR #56).

### 2026-06-26 (roadmap advance, codebase on main since PR #54)

Added

- `docs/roadmap-gap-matrix.md` — consolidated pending items from way-ahead (commits A–G),
  improvement-plan (Waves 1–3), and docs-site-plan with honest operator vs code-state columns.
- `fleet_run.plan_dryrun_trace_from_progress` — derive task_id and primitive statuses from
  verbatim `docs/<mission>-progress.md` excerpts (TASK / PHASE / REVIEWED / MERGED).
- `fleet_run.emit_dryrun_lifecycle_trace` and `write_headless_dryrun_archive` — mechanical
  eleven-primitive orchestration in `fleet_run` (not only emit_trace helpers); archives land
  under `--repo` while progress excerpts read from the fleet clone.
- `scripts/lib/headless_trace.py` and `scripts/emit_headless_dryrun_trace.py` — thin CLI/shell
  wrappers for headless dry-run entry points.
- `emit_full_primitive_trace()` — all 11 primitives including `GOAL_BLOCKED` and `ABORT`.
- `scripts/emit_representative_trace.py` and `emit_representative_mission_trace()` — standalone
  CLI for fixture refresh; superseded for entry points by headless_trace wiring.
- `tests/test_real_world_scenarios.py` — 67 direct exercises grounded in example-fixture,
  progress docs, and external-dogfood packs.
- "Real-world use cases" sections (≥3 examples each) in all 20 guide chapters and the three shipped
  mission READMEs (`doc-sync`, `test-coverage`, `adversarial-review-and-fix`).

Changed

- `.fleet/runs/example-fixture/trace.jsonl` expanded to 11 primitives (adds `GOAL_BLOCKED`,
  `ABORT`); manifest and generator updated; `write_manifest` refreshes `trace.jsonl` checksum
  after `T-FINAL` emit.
- `run-mission-headless.sh` and `run-campaign.sh` `--dry-run` now emit and validate traces via
  `headless_trace` (ephemeral archives cleaned up after emission).
- `docs/external-dogfood/` bench and dogfood READMEs — literal reproduction commands plus
  PENDING operator-run notes where live auth is still required.
- `docs/marketplace-submission/README.md` — v0.1.0 mechanical repro block and submit status.

## [0.1.0] - 2026-06-26

First tagged release: three shipped missions, four runtime adapters, four-layer verification
substrate, and 936-test validation gate (50 test files, 100% `scripts/lib` coverage).

### 2026-06-26

Added

- `scripts/bootstrap.sh` — one-command contributor setup (venv + deps + validate-all).
- `scripts/validate-headless.sh` — mechanical headless-path dry-run harness wired into
  `validate-all.sh`; `run-mission-headless.sh --dry-run` previews agent commands without
  runtime auth.
- Campaign registry lint — active campaign YAMLs must bind only shipped missions.
- `VERSION` file for release pinning.

Changed

- `venv-bootstrap.sh` now requires `coverage` alongside `yaml` and `pytest`, with post-install
  import verification.
- External dogfood `repo-health` campaign aligned to shipped missions only (removed demoted
  `cleanup` node).
- `docs/DECISIONS.md` and `docs/autonomous-fleet-review.md` baselines refreshed (933 tests).

Fixed

- Local dev friction when `.venv` existed without `coverage` installed.
- Stale README test inventory (37 → 49 files / 928+ tests).

### 2026-06-24

Added

- User-facing docs site plan (Stage 1 pure-markdown guide, Stage 2 Starlight-ready), refreshed
  against `main` after PR #41.
- Wave 1 ground-truth gates (PR #48): SHA-pin enforcement (`scripts/verify_sha_pin.py`,
  `scripts/lib/verify_sha_pin.py`, `assets/fleet-sha-pin.schema.json`) that flips a reviewer's
  `approve`/`PASS` verdict from REVIEWED to OUTDATED when the branch HEAD moves past the
  `reviewed_sha` recorded in `.fleet/runs/<run_id>/sha-pin.json` (a deleted-but-merged branch is
  N/A, not a failure); a foreground `render-dashboard.py --watch` poll loop that re-renders on
  ledger/trace mtime change (no daemon, socket, or PID); a ledger-contradiction guard in
  `scripts/lib/fleet_outcome.py` that rejects merged-but-never-built, merged-but-worktree-not-clean,
  and reviewed-before-PR task rows; and a trace `health_rollup`
  (`total`/`succeeded`/`failed`/`blocked`/`skipped`/`last_failure`) surfaced in the emit CLI and a
  separate dashboard panel kept distinct from the ledger zone counts.
- Wave 2 budget, recovery, and registry layer (PR #49): a round-budget validator
  (`scripts/verify_round_budget.py`) that BLOCKS any task exceeding `MAX_ROUNDS` (3) failed review
  rounds instead of letting it MERGE; a resume-time recovery scanner (`scripts/recovery_scan.py`)
  that classifies each task row `live`/`dead`/`partial`/`orphan` against `git worktree list` plus
  `gh pr list` and emits advisory CONTINUE / CLEANUP_WORKTREE / RE_DRIVE / ESCALATE_TO_DECISIONS /
  ARCHIVE_ORPHAN actions without executing them; a mission/adapter registry
  (`scripts/lib/fleet_registry.py`) as the single source that `mission_registry.py` and the
  `fleet_outcome.py` mission metrics derive from, linted by `scripts/registry_lint.py`; and a
  SKILL.md structural linter (`scripts/lib/skill_lint.py`) plus an adapter requires-block
  (`scripts/lib/adapter_preflight.py`, `scripts/preflight.sh`) with intent-gated SCM/PR checks.
- Wave 3 causal lineage, resume, isolation, and binding split (PR #50): trace events now carry an
  optional-but-generated unique `id` that `emit()` returns, with a worker COMMIT stamping its
  SPAWN_WORKER id as `parent_event` (the id factory is injectable so fixtures stay reproducible);
  `CONTINUE_WORKER` added as the optional 14th engine primitive that re-attaches a resumable session
  or ALIASes to `SPAWN_WORKER`, constrained to `live`-classified rows and capped at
  `MAX_RESUME_ATTEMPTS` (3) before the scanner escalates; a read-only reviewer sandbox
  (`scripts/run-sandboxed.sh --role reviewer`, `scripts/verify_reviewer_sandbox.py`) using
  sandbox-exec on macOS, bwrap on Linux, and a post-exec assertion fallback; run hash-namespacing
  (`scripts/lib/namespace.py`, `scripts/validate_namespacing.py`) that suffixes every isolated
  branch and worktree with the run short hash; and an explicit TRACKER vs SCM binding split in the
  engine spec where `gh`/GitHub is the default, not the contract.

Changed

- Wired `verify_sha_pin.py` (PR #48), `verify_round_budget.py`, `registry_lint.py` (PR #49),
  `verify_reviewer_sandbox.py`, and `validate_namespacing.py` (PR #50) into `validate-all.sh`, and
  `skill_lint.py` into `validate-skills.sh`, each guarded by a `FLEET_DISABLE_*` kill switch
  (`FLEET_DISABLE_SHA_PIN`, `FLEET_DISABLE_ROUND_BUDGET`, `FLEET_DISABLE_REGISTRY_LINT`,
  `FLEET_DISABLE_REVIEWER_SANDBOX`, `FLEET_DISABLE_NAMESPACING`).
- Updated all four adapters plus the adapter template with `CONTINUE_WORKER` and run-namespacing
  guidance (PR #50), without relaxing the conflict-aware, never-squash, or SHA-pin rules.

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
