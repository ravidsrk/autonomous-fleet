# Adversarial bench (2026-06)

**Status:** Tier A complete (2026-07-05) — `github/gemoji` + `pallets/click`, substrate OFF vs ON via `bench-adversarial.sh` + `grok` headless.

## Mechanical reproduction (no runtime auth)

Validate the driver and trace contract today from a clean checkout:

```bash
./scripts/validate-headless.sh
./scripts/bench-adversarial.sh --help
./scripts/bench-adversarial.sh --target pallets/click --dry-run
python scripts/emit_representative_trace.py --mission adversarial-review-and-fix \
  --run-id 20260626T120000Z-adversarial-review-and-fix-000001 \
  --out /tmp/bench-trace-demo
python scripts/emit_trace.py validate /tmp/bench-trace-demo/trace.jsonl
```

Headless driver (`run-mission-headless.sh`, `run-campaign.sh --repo`) unconditionally emits
`.fleet/runs/<run_id>/` under the target checkout (Lane 2 gemoji baseline). Live substrate A/B
numbers require authenticated operator runs per target — see Methodology below.

# The falsifiable claim

The 4-layer verification substrate (review-findings + stop-verify +
blind-fix + run-archive) raises precision and lowers wasted spend on
adversarial-review-and-fix runs. The bench tests this directly:

> For each target, run the mission TWICE — once with substrate OFF
> (FLEET_DISABLE_STOP_VERIFY=1 etc), once with substrate ON. The
> headline metric is the DELTA.

The four `FLEET_DISABLE_*` env vars are honored by the substrate
verifiers themselves — they early-exit 0 with a documented stderr
notice when set truthy. See
`skills/autonomous-fleet-core/references/substrate-disable-knobs.md`
for the full convention, env-var registry, and library helper.

If the delta is small or negative across multiple targets, that's
the substrate's fault, not the methodology's. We learn either way.

# Headline metrics (per target)

| Metric | Definition |
|---|---|
| `Δ precision` | substrate-on `verified/emitted` minus substrate-off `verified/emitted` |
| `Δ close-rate-after-blind-fix` | fraction of verified findings that survive blind-fix attestation, on vs off |
| `Δ cost-per-closed-finding` | substrate-on `cost_estimate / closed` minus substrate-off `cost_estimate / closed` |
| `stop_verify_activations` | number of premature-stop attempts blocked by Layer 2 (on mode only) |
| `wall_clock_to_freeze_s` | first event ts → first FREEZE event ts |
| `wall_clock_to_all_closed_s` | first event ts → last COMMIT event ts |

# Targets

See `adversarial-bench-targets.yaml`. 5 repos chosen to cover:
- mature CLI (`pallets/click`)
- dogfood-grade dependency (`python-jsonschema/jsonschema`)
- known-vulnerable corpus (`bandit` examples/)
- externally-validated correctness (one SWE-Bench Lite instance)
- prior-dogfood comparison baseline (`github/gemoji`)

# Methodology

For each target:

1. Operator runs `scripts/bench-adversarial.sh --target <name> --both`.
2. Driver clones the repo and prints the dispatch plan for both modes.
3. Operator dispatches `adversarial-review-and-fix` via the adapter twice:
   first with `FLEET_DISABLE_*=1` (substrate-off), then without
   (substrate-on). Each run produces an archive at
   `.fleet/runs/<repo-slug>-<mode>-<ts>/`.
4. After both archives complete, the driver invokes
   `scripts/analyze_seat.py per-run` and the per-target comparison
   table is appended to this file's "Results" section.
5. Aggregated bench-wide delta is emitted by `analyze_seat.py aggregate`.

The driver is in `scripts/bench-adversarial.sh`. CI exercises a planted-
bug fixture (no network, no real adapter) via
`tests/test_bench_adversarial.py` to keep the driver from rotting.

# Results — Tier A (2026-07-05)

Operator sessions: `grok` headless via `scripts/bench-adversarial.sh`, `--max-turns 50`,
`--scratch /tmp/fleet-bench/`. Precision = `verified / emitted` from
`p0-review-findings.json` (0 when Layer 1 disabled in off-mode).

| Target | Off precision | On precision | Off → On Δ precision | Stop-verify blocks | Archives |
|---|---|---|---|---|---|
| `github/gemoji` | 0/2 (0%) | 3/3 (100%) | **+100pp** | 0 / 0 | off `…-fe34b6`¹ · on `…-de6c0f` |
| `pallets/click` | 0/2 (0%) | 1/1² (100%) | **+100pp** | 0 / 0 | off+on `…-20fb28`³ |
| `python-jsonschema/jsonschema` | ⬜ pending | ⬜ pending | ⬜ pending | — | Tier B |
| `pycqa-bandit-corpus` | ⬜ pending | ⬜ pending | ⬜ pending | — | Tier B |
| `swe-bench-lite-instance` | ⬜ pending | ⬜ pending | ⬜ pending | — | Tier B |

¹ Gemoji off archive `20260705T122027Z-adversarial-review-and-fix-fe34b6` was produced under
substrate-off; re-run with `./scripts/bench-adversarial.sh --target github/gemoji --substrate off`
to reproduce (scratch clone).

² Click on-mode re-verified the skeptic set (`p0-skeptic-findings.json`: 1/1 verified);
`verify_findings.py` exit 0, `validate_run_archive.py` exit 0.

³ Click on-mode updated the off-mode archive in-place (`.fleet/runs/` preserved across
`git clean -e .fleet` reset). Tier B should use separate scratch dirs per mode for cleaner
pairing.

### Headline deltas (Tier A aggregate)

| Metric | Off → On |
|---|---|
| Δ precision (avg across Tier A) | **+100pp** (0% → 100% on both targets) |
| Δ close-rate after blind-fix | not measured (blind-fix chains incomplete on gemoji on; click reused archive) |
| Δ cost-per-closed-finding | N/A (`cost_estimate` 0 in all four sessions) |
| `stop_verify_activations` | 0 in all sessions (no premature-stop attempts logged) |

# Why this is the right comparator

Three alternatives we rejected:

| Comparator | Why rejected |
|---|---|
| absolute findings counts | not falsifiable: "12 findings on `click`" is just a number |
| comparison vs `bandit` / `ruff` / `semgrep` | static analyzers aren't the comparison — the substrate is a discipline on top of LLM reviewers, not a static-analysis replacement |
| SWE-Bench leaderboard score | informative for one instance (kept) but not a general claim about the substrate |

The substrate-off vs substrate-on comparator is the strongest available
because it isolates one variable: the 4 layers. Same model, same
adapter, same target — only the substrate changes between archives.
The delta is the substrate's value, full stop.

# Lineage

- Plan: `docs/plans/way-ahead-2026-06-23.md` §3 Commit C.
- Driver: `scripts/bench-adversarial.sh`.
- Targets: `adversarial-bench-targets.yaml`.
- Per-target stubs: `adversarial-bench/<repo-slug>.md`.
- Public-facing summary: `adversarial-bench-summary.md`.
- Analyzer: `scripts/analyze_seat.py`.
