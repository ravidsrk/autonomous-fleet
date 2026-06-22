# Exploratory Patterns

Patterns here look load-bearing but have NOT been validated in the
autonomous-fleet empirical corpus (the ~2 weeks of orchestration runs
distilled in Stage 8 of the prompt collection).

They live here, not in `skills/` or `engine.md`, so the framework's
core surface stays defensible: every shipped concept can answer
"show me the run."

Re-promote to `skills/` (for missions) or `engine.md` (for engine
patterns) on first real run that validates them. The promotion PR
should cite the run by name + the progress/readiness doc that
exhibited the pattern.

## Contents

- `missions/scaffold-align/` — moved 2026-06-22. Not on the Stage 8
  distillation list of 11 missions. No -progress.md or -readiness.md
  reference. Re-promote after a real "freeze a scaffold then build
  inside it" run.

- `missions/contract-first-build/` — moved 2026-06-22. Not on the
  Stage 8 distillation list. No real-run evidence. Re-promote after a
  real contract-first build is shipped through the engine.

- `missions/agents-layer/` — moved 2026-06-22. Not on the Stage 8
  distillation list. No real-run evidence. Re-promote after a real
  agents-layer build is shipped.

- `engine/durable-execution-patches.md` — moved 2026-06-22. The
  pattern (exactly-once, bounded waits, compensation, on the ledger
  not a runtime) is plausibly load-bearing but only appears in
  `docs/orchestration-landscape.md` (a research scan), never in any
  progress or readiness doc from a real run.
