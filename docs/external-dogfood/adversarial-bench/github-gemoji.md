# Adversarial bench — github/gemoji

**Status:** Tier A DONE (2026-07-05) · Lane 3 operator run

# Methodology

Per `docs/external-dogfood/adversarial-bench-2026-06.md`. Two runs:

1. `substrate-off` — `FLEET_DISABLE_*=1` env set; no Layer 1/2/3/4.
2. `substrate-on` — clean env; all four layers active.

Driver:

```bash
./scripts/bench-adversarial.sh --target github/gemoji --both --adapter grok
```

# Results

| Mode | run_id | Precision | Closed findings | validate_run_archive |
|---|---|---|---|---|
| off | `20260705T122027Z-adversarial-review-and-fix-fe34b6` | 0/2 | REL-002 (local merge) | disabled (Layer 4 off) |
| on | `20260705T122446Z-adversarial-review-and-fix-de6c0f` | 3/3 review; 1/1 skeptic | REL-001 | OK |

**Δ precision:** 0% → 100% (+100pp). Substrate-on run caught quote-grounding via
`verify_findings.py` (3/3) where off-mode accepted unverified review JSON.

Archive paths (on-mode survives on disk):

```
/tmp/fleet-bench/github-gemoji/.fleet/runs/20260705T122446Z-adversarial-review-and-fix-de6c0f/
```

Reproduce off-mode:

```bash
./scripts/bench-adversarial.sh --target github/gemoji --substrate off --adapter grok --scratch /tmp/fleet-bench
```