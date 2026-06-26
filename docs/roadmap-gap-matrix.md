# Roadmap gap matrix (consolidated 2026-06-26)

Sources: `docs/plans/way-ahead-2026-06-23.md`, `docs/plans/improvement-plan-from-ao-2026-06-24.md`, `docs/plans/docs-site-plan-2026-06-24.md`, `CHANGELOG.md` [Unreleased].

Legend: **Code** = shipped in repo · **Operator** = human/authenticated run · **This goal** = what this pass closes.

## Way-ahead commits (A–G)

| Gap ID | Item | Code state | Operator / human | This goal closes |
|--------|------|------------|------------------|------------------|
| A-real | Real `.fleet/runs/<run_id>/` from live adversarial run on main | Lane 1 archive + example-fixture | — | closed (PR #55, `first-substrate-run.md`) |
| B-blind | Blind-fix mechanical guard (Layer 3) | Shipped (`verify_blind_fix.py`) | — | — (already closed) |
| C-bench | Public bench numbers (5 OSS repos) | `bench-adversarial.sh` + headless `--repo` + archive keep | PENDING: authenticated A/B runs | headless + archive path complete |
| D-demote | Demote 9 unproven missions | Shipped → `docs/exploratory/missions/` | — | — (already closed) |
| E-trace | Full 11-primitive trace per run | `plan_dryrun_trace_from_progress` + `emit_dryrun_lifecycle_trace` + kept archives | Live coordinator partial | `run-mission-headless.sh` keeps archive under `--repo` |
| F-seat | Seat analysis + write locks | Shipped (`analyze_seat.py`, `locks.py`) | — | — (already closed) |
| G-market | Marketplace Console submit | Packet refreshed | PENDING: human submit | README repro + status |

## Way-ahead open items (§1)

| Gap ID | Item | Code state | Operator / human | This goal closes |
|--------|------|------------|------------------|------------------|
| W-proof | Mission proof for ≥10/12 missions | 3 shipped + 2 dogfood progress docs | PENDING per mission | Document promotion criteria |
| W-bench-pub | Public benchmark citation artifact | Methodology + headless/archive ready | PENDING numbers | adversarial-bench-2026-06.md updated |
| W-adopt | External adopters / install metrics | Marketplace packet | PENDING submit + feedback | marketplace README |
| W-gap1 | Non-busy WAIT (Codex/Grok ledger-poll) | Adapter prose | — | Documented in engine (degraded OK) |
| W-telemetry | analyze.js "earns its seat" lens | `analyze_seat.py` scaffold | PENDING bench archives | bench docs |

## Improvement plan Wave 1

| Gap ID | Item | Code state | Operator / human | This goal closes |
|--------|------|------------|------------------|------------------|
| W1-sha | SHA-pin enforcement validator | Shipped | — | — |
| W1-dash | `render-dashboard --watch` | Shipped | — | — |
| W1-ledger | Ledger contradiction guard | Shipped | — | — |
| W1-health | Trace `health_rollup` | Shipped | — | — |

## Improvement plan Wave 2

| Gap ID | Item | Code state | Operator / human | This goal closes |
|--------|------|------------|------------------|------------------|
| W2-round | Round-budget circuit breaker | Shipped | — | — |
| W2-recover | Recovery scanner (live/dead/partial/orphan) | Shipped | — | — |
| W2-orphan | Orphan sweep in recovery scanner | Shipped | — | — |
| W2-registry | Single fleet_registry + registry_lint | Shipped | — | — |
| W2-skill | SKILL.md structural linter | Shipped | — | — |
| W2-preflight | Adapter requires-block + preflight | Shipped | — | — |

## Improvement plan Wave 3

| Gap ID | Item | Code state | Operator / human | This goal closes |
|--------|------|------------|------------------|------------------|
| W3-lifeline | Worker causal lifeline (id + parent_event) | Shipped in fixture + emit | — | fixture 11 primitives |
| W3-continue | CONTINUE_WORKER optional primitive | Shipped in engine.md | — | — |
| W3-sandbox | Reviewer read-only sandbox | Shipped | — | — |
| W3-namespace | Hash-namespace worktree/branch | Shipped | — | — |
| W3-tracker | TRACKER vs SCM split in engine | Shipped | — | — |
| W3-trace11 | Trace schema 1.1 (optional id bump) | Deferred; 1.0 + optional id | — | Documented in improvement-plan |

## Docs / dogfood / headless

| Gap ID | Item | Code state | Operator / human | This goal closes |
|--------|------|------------|------------------|------------------|
| C-dogfood | External gemoji repo-health / ship-with-proof | Evidence pack exists | PENDING: interactive auth path | dogfood YAML + commands |
| H-headless | Headless E2E with runtime auth | `validate-headless.sh` + trace via dry-run | PENDING: `grok login` etc. | `headless_trace` + campaign dry-run invoke |
| M-promote | 12 exploratory missions | Demoted to `docs/exploratory/` | PENDING: archive triple each | promotion criteria in matrix |
| D-starlight | Public docs site (Starlight) | 20-chapter guide + examples | Deferred build | examples per chapter |

## Ordering (unchanged from way-ahead)

1. Citable artifacts (trace, fixture, bench docs)
2. Enforcing tests per artifact
3. Operator runs documented with exact commands