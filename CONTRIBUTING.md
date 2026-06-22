# Contributing to autonomous-fleet

This framework is the distillation of real orchestration runs, not a
research catalog. Every concept in `engine.md` and every mission in
`skills/` exists because a specific run exposed a specific failure
mode that the concept prevents.

## The Distillation Discipline

The single rule that protects the framework's credibility:

> Every concept in `engine.md` and every mission in `skills/` must
> cite either (a) the run that produced it, or (b) the run that
> closed the failure mode it prevents.

This rule is the reason the README can claim "battle-tested
distillation" with no asterisks. Without it, the framework drifts
back into a research catalog.

## Where new patterns go

| Source of the pattern | Goes to |
|---|---|
| Failure caught in a real run | `engine.md` or a `skills/*` mission, with a corpus citation in the commit body |
| Found in a paper, blog, or research scan | `docs/exploratory/` with a header note that it has NOT been validated in this corpus |
| Plausibly load-bearing but unproven | `docs/exploratory/` |

## How to promote an exploratory pattern

1. Run a real autonomous-fleet mission that exhibits the failure
   mode the pattern would prevent (or run a mission that uses the
   pattern and ship a `-progress.md` / `-readiness.md` that
   exhibits the value).
2. Open a PR that moves the pattern from `docs/exploratory/` to
   `engine.md` or `skills/`.
3. The PR body must cite:
   - The run name + the progress/readiness doc that exhibits the
     pattern's value.
   - The specific failure mode the pattern prevents.
   - The fleet-outcome metric that would have shipped wrong without
     the pattern.

PRs that add to `engine.md` or `skills/` without a run citation are
moved to `docs/exploratory/` until a run validates them.

## Citations: corpus vs research

Corpus citations look like:
- `directives.md:L72-82` (the line range in the empirical corpus)
- `prompts.md:L3013` (Stage 9 Aula run)
- `docs/test-coverage-progress.md` "SIGNAL RECONCILIATION (a real catch)"

Research citations look like:
- `arXiv 2601.15195` (MSR 2026 AIDev dataset, 33,596 PRs) — this is
  legitimate and is the only research citation in `engine.md`.

If you cite a paper, the paper must contain the claim. The repo's
adversarial-audit-2026-06-20.md flagged misattribution as a class of
problem; do not reintroduce it.

## Anti-patterns to avoid

- Inventing a mission because a category seems missing.
- Citing a paper because the pattern is "in the literature" without
  reading the paper.
- Treating green CI as evidence the pattern works. The
  RESULT-STATE TERMINATION GATE in `engine.md` exists because
  green CI is not evidence of behavior.
- Adding to `engine.md` without checking whether the concept
  belongs in a mission instead. The engine is for invariants
  inherited by every mission; per-mission specifics go in the
  mission's `SKILL.md`.

## Workflow

1. Read `engine.md` and the relevant mission's `SKILL.md`.
2. Run the change.
3. Save the progress doc to `docs/<mission>-progress.md` and the
   readiness doc to `docs/<mission>-readiness.md`.
4. Open the PR with corpus citations in the body.
5. CI must pass (`./scripts/validate-all.sh`).
