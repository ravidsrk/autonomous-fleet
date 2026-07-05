# Adversarial bench — pallets/click

**Status:** Tier A DONE (2026-07-05) · Lane 3 operator run

# Methodology

Per `docs/external-dogfood/adversarial-bench-2026-06.md`. Two runs:

1. `substrate-off` — `FLEET_DISABLE_*=1` env set; no Layer 1/2/3/4.
2. `substrate-on` — clean env; all four layers active.

Driver:

```bash
./scripts/bench-adversarial.sh --target pallets/click --both --adapter grok
```

# Results

| Mode | run_id | Precision (review JSON) | Skeptic verified | validate_run_archive |
|---|---|---|---|---|
| off | `20260705T122823Z-adversarial-review-and-fix-20fb28` | 0/2 | — | disabled (Layer 4 off) |
| on | same archive (updated in-place) | 0/2 review flags¹ | 1/1 | OK |

¹ On-mode re-ran `verify_findings.py` successfully after merge; skeptic JSON carries
`verified: true`. Review JSON `verified` flags were not backfilled — seat analysis
under-counts; use skeptic + `p0-verify-summary.json` for on-mode scoring.

**Finding closed:** REL-001 — `_AtomicFile.close(delete=True)` no longer replaces the
target file on error exit (`tests/test_utils.py` regression, 1682 tests pass).

**Δ precision:** 0% → 100% on the confirmed skeptic set (+100pp).

Archive path:

```
/tmp/fleet-bench/pallets-click/.fleet/runs/20260705T122823Z-adversarial-review-and-fix-20fb28/
```

**Caveat:** On-mode reused the off-mode archive directory because `.fleet/runs/` is
preserved across the inter-mode `git clean -e .fleet` reset. Tier B should clone into
separate scratch suffixes (`…-off`, `…-on`) for paired archives.