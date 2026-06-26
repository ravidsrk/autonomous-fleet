# Roadmap gap matrix (consolidated 2026-06-26)

Sources: `docs/plans/way-ahead-2026-06-23.md`, `docs/plans/improvement-plan-from-ao-2026-06-24.md`, `docs/plans/docs-site-plan-2026-06-24.md`, `CHANGELOG.md` [Unreleased].

| Gap ID | Item | Code state | Operator / human | This goal closes |
|--------|------|------------|------------------|------------------|
| A-real | Real `.fleet/runs/<run_id>/` from live adversarial run | Fixture only | PENDING: run `adversarial-review-and-fix` on main | Docs + repro commands |
| C-bench | Public bench numbers (5 OSS repos) | `bench-adversarial.sh` scaffold | PENDING: authenticated agent runs | Refresh bench docs + dry paths |
| C-dogfood | External gemoji repo-health / ship-with-proof | Evidence pack exists | PENDING: interactive auth path | Update dogfood YAML + commands |
| E-trace | Full 11-primitive trace per run | Representative 9-primitive path + fixture | Live coordinator wiring partial | `emit_representative_mission_trace` + fixture + headless gate |
| G-market | Marketplace Console submit | Packet refreshed | PENDING: human submit | README repro + status |
| M-promote | 12 exploratory missions | Demoted to `docs/exploratory/` | PENDING: external archive triple each | Document promotion criteria only |
| H-headless | Headless E2E with runtime auth | `validate-headless.sh` dry + trace emit | PENDING: `grok login` etc. | Dry-run + representative trace wired |
| D-starlight | Public docs site | 20-chapter guide + real-world sections | Deferred build | Examples added per chapter |

## Ordering (unchanged from way-ahead)

1. Citable artifacts (trace, fixture, bench docs)
2. Enforcing tests per artifact
3. Operator runs documented with exact commands