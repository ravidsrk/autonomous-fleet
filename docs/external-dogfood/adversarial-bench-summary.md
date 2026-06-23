# Adversarial bench — public summary

**Status:** ⬜ Results PENDING.

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

```bash
git clone https://github.com/ravidsrk/autonomous-fleet.git
cd autonomous-fleet
./scripts/install-skills.sh
./scripts/bench-adversarial.sh --target <name> --both
```

Each archive validates against the schemas in
`skills/autonomous-fleet-core/assets/`. Auditors can re-score with
their own weights via `scripts/analyze_seat.py`.

# Status as of 2026-06-23

Scaffolding shipped (driver script, targets YAML, methodology doc,
per-target stubs). Real runs gated on a working coder-adapter session
(Claude Code or Codex with credit) on an operator host. See plan
§3 Commit C in `docs/plans/way-ahead-2026-06-23.md`.
