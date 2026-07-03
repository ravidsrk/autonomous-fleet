# Contributing to autonomous-fleet

This framework is the distillation of real orchestration runs, not a
research catalog. Every concept in `engine.md` and every mission in
`skills/` exists because a specific run exposed a specific failure
mode that the concept prevents.

When you borrow a mechanism from another open-source project, add credits in
[`ATTRIBUTIONS.md`](ATTRIBUTIONS.md) (and [`NOTICE`](NOTICE) when the upstream license
requires retained notices). Link the upstream license and document the port map under
`skills/autonomous-fleet-core/references/` or `docs/`.

## Maintenance status

autonomous-fleet is a single-maintainer, pre-1.0 project. There is one
maintainer (@ravidsrk), and there is no fixed release cadence — fixes
and features land on `main` as they are ready.

There are no tagged releases yet, so **pinning to a commit is the
stability story**: pin to a specific commit if you need stability, then
re-pin forward when a fix you need merges. (See also "Supported
versions" in `SECURITY.md`.) Cutting a tagged release once the headless
path has a real end-to-end run behind it is on the roadmap, and is the
recommended next step for anyone who wants a more stable pin than a raw
commit SHA.

Because it is pre-1.0 and single-maintainer, review latency varies and
APIs/mission contracts can change between commits without a deprecation
window. File issues and PRs anyway — they are read.

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

`prompts.md` and `directives.md` are the **private upstream source corpus** (raw
run logs + directives) this repo is distilled from; they are not shipped in the
tree. Those citations record provenance — which run a rule came from — not links
you can open here. `docs/*` citations, by contrast, do resolve in-repo.

Research citations look like:
- `arXiv 2601.15195` (MSR 2026 AIDev dataset, 33,596 PRs) — this is
  legitimate and is the only research citation in `engine.md`.

Mind which paper a number actually comes from. `arXiv 2601.15195`
(the 33,596-PR AIDev dataset) supports the directional ranking of
task categories (docs/CI/build merge best, performance/fix worst). It
does **not** source the per-task merge-rate *decimals*: per
`docs/adversarial-audit-2026-06-20.md`, those per-task figures come
from Pinna et al. (`arXiv 2602.08915`, 7,156 PRs), a different and
smaller paper. Attaching the "33k PRs" provenance to a per-task decimal
is exactly the misattribution the audit flagged.

If you cite a paper, the paper must contain the claim. The repo's
`docs/adversarial-audit-2026-06-20.md` flagged misattribution as a
class of problem; do not reintroduce it.

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


## Skill versioning policy (issue #90)

- Skills version **independently** (semver-ish; adapters need not move in
  lockstep — Orca legitimately leads). What IS enforced:
  1. **Any content change bumps `metadata.version`** in the same commit and
     refreshes `skills-lock.json` (`lib.registry_lint.content_hash`) — the
     lock-version-sync lint fails otherwise.
  2. **Tests must never hard-code a skill version string** (`version: "X.Y.Z"`)
     — two incidents (ebd33d3, PR #112) broke CI on routine bumps. Use
     version-agnostic regexes; `registry_lint` fails on literals (schema
     versions like `schema_version: "1.0"` are pinned contracts and exempt).
  3. Version rationale goes in the commit message, not a per-skill changelog.
