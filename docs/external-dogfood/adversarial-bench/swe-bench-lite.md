# Adversarial bench — swe-bench-lite

**Status:** Infrastructure ready for operator runs (headless `--repo`, archive emission); metrics ⬜ pending.

# Methodology

Per `docs/external-dogfood/adversarial-bench-2026-06.md`. Two runs:

1. `substrate-off` — `FLEET_DISABLE_*=1` env set; no Layer 1/2/3/4.
2. `substrate-on` — clean env; all four layers active.

Driver:

```
scripts/bench-adversarial.sh --target swe-bench-lite --both
```

# Results

Pending operator runs. Will be populated with:

- Per-mode archive paths under `.fleet/runs/swe-bench-lite-{off,on}-<ts>/`
- Output of `scripts/analyze_seat.py per-run` filtered to this target
- The substrate-on vs substrate-off DELTA on the four headline metrics
- Notes on any planted-bug recovery (bandit corpus only)
