# Adversarial bench — public summary

**Status:** Tier A numbers published (2026-07-05) — `github/gemoji` + `pallets/click`.
Tier B (remaining three targets) pending.

# What this is

A reproducible benchmark of `adversarial-review-and-fix` on 5 public
OSS repos, with the 4-layer verification substrate switched OFF and
ON for each target. The delta is the falsifiable claim the substrate
must defend.

Methodology: [`adversarial-bench-2026-06.md`](adversarial-bench-2026-06.md).
Targets: [`adversarial-bench-targets.yaml`](adversarial-bench-targets.yaml).
Per-target archives: [`adversarial-bench/`](adversarial-bench/).

# Headline (Tier A, 2026-07-05)

| Metric | Off → On Delta |
|---|---|
| Precision (verified / emitted) | **+100pp** avg (0% off → 100% on, both targets) |
| Close-rate after blind-fix | not scored (chains incomplete / archive reuse) |
| Cost per closed finding | N/A (`cost_estimate` 0) |
| Stop-verify activations | 0 (no blocks in either mode) |

# Reproducing

Mechanical (no auth — validates driver + trace today):

```bash
git clone https://github.com/ravidsrk/autonomous-fleet.git
cd autonomous-fleet
./scripts/bootstrap.sh
./scripts/validate-headless.sh
./scripts/bench-adversarial.sh --help
./scripts/bench-adversarial.sh --target pallets/click --dry-run
```

Live A/B (ready for operator — headless `grok -p`, `--repo`, archive emission; metrics ⬜ pending):

```bash
./scripts/bench-adversarial.sh --target <name> --both
# then dispatch adversarial-review-and-fix twice per target (substrate off vs on)
```

Each archive validates against the schemas in
`skills/autonomous-fleet-core/assets/`. Auditors can re-score with
their own weights via `scripts/analyze_seat.py`.

# Status as of 2026-07-05

Lane 3 Tier A operator sessions complete (`issue #62`). `bench-adversarial.sh` now auto-dispatches
`run-mission-headless.sh` (install skills → substrate env → headless mission → validate →
`analyze_seat.py`). Reproduce:

```bash
./scripts/bench-adversarial.sh --target github/gemoji --both --adapter grok
./scripts/bench-adversarial.sh --target pallets/click --both --adapter grok
```

Full methodology: `adversarial-bench-2026-06.md`. Tier B targets remain in
`adversarial-bench-targets.yaml`.
