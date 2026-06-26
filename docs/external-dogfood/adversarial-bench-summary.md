# Adversarial bench — public summary

**Status:** Infrastructure ready for operator runs to produce real A/B numbers; headline metrics ⬜ pending.

# What this is

A reproducible benchmark of `adversarial-review-and-fix` on 5 public
OSS repos, with the 4-layer verification substrate switched OFF and
ON for each target. The delta is the falsifiable claim the substrate
must defend.

Methodology: [`adversarial-bench-2026-06.md`](adversarial-bench-2026-06.md).
Targets: [`adversarial-bench-targets.yaml`](adversarial-bench-targets.yaml).
Per-target archives: [`adversarial-bench/`](adversarial-bench/).

# Headline (when ready)

| Metric | Off → On Delta |
|---|---|
| Precision (verified / emitted) | ⬜ pending |
| Close-rate after blind-fix | ⬜ pending |
| Cost per closed finding | ⬜ pending |
| Stop-verify activations | ⬜ pending |

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

# Status as of 2026-06-27

Driver, targets YAML, methodology, per-target stubs, headless `--repo` path, and unconditional
archive emission (v0.2.0) are shipped. Lane 2 validated `run-campaign.sh` on
`ravidsrk/gemoji`. Real A/B numbers gated on authenticated operator sessions per target.
See `gemoji-headless-run.md` and plan §3 Commit C in `docs/plans/way-ahead-2026-06-23.md`.
