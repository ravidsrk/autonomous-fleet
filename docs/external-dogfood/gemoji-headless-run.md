# Lane 2 — headless ship-with-proof on gemoji

**Status:** Gate-validation only (2026-06-27)  
**Exercises:** external dogfood headless path (`grok -p` + `--repo`)  
**Duration:** ~163s (3 nodes × verification pass on pre-completed fork)
**Fork:** [ravidsrk/gemoji](https://github.com/ravidsrk/gemoji) @ `fleet/gemoji-ship-with-proof-base`

> **Disclosure — gate-validation only.** No external run-archive with autonomously-landed PRs
> (`prs_merged > 0`) exists yet. This run **re-validated the fork's pre-existing `PHASE: DONE`
> ledgers** (landed by hand in the 2026-06-20 interactive session), and the headless invocation
> **failed auth and was completed by hand**. It validates `--repo` orchestration and the gates
> against an external checkout — it does **not** demonstrate autonomous PR landing or
> build-blindness beyond the self-dogfood.

## Why this run

Lane 1 exercised the substrate + headless auth on **autonomous-fleet** (a self-dogfood; see its
disclosure in `first-substrate-run.md`). Lane 2 exercises the same headless driver against an
**external** checkout via `run-campaign.sh --repo` — as a gate-validation pass, not an autonomous
landing.

## Reproduction

### Prerequisites

- Grok CLI authenticated (`grok -p "ping"` succeeds)
- Fork cloned: `git clone -b fleet/gemoji-ship-with-proof-base https://github.com/ravidsrk/gemoji.git /tmp/gemoji`
- Fleet skills installed in gemoji (see `ship-with-proof-gemoji.md`)

### Kickoff

```bash
cd /path/to/autonomous-fleet
git checkout -b dogfood/gemoji-headless-run   # optional

./scripts/run-campaign.sh grok \
  --campaign docs/external-dogfood/ship-with-proof-campaign.yaml \
  --repo /tmp/gemoji \
  --max-turns 50
```

Handoff (optional per-mission): `docs/handoff-gemoji-headless-run.md`

### Post-run validation

```bash
./scripts/validate-fleet-outcome.sh \
  /tmp/gemoji/docs/arch-build-readiness.md \
  /tmp/gemoji/docs/test-coverage-readiness.md \
  /tmp/gemoji/docs/doc-sync-readiness.md
ls /tmp/gemoji/.fleet/runs/
```

## Post-run evidence

```
== run-campaign.sh grok --campaign ship-with-proof-campaign.yaml --repo /tmp/gemoji ==
runtime: grok | repo: /tmp/gemoji | dry-run: 0

--- step 1: audit (adversarial-review-and-fix) ---
validate-fleet-outcome: OK arch-build-readiness.md
  next: tests

--- step 2: tests (test-coverage) ---
validate-fleet-outcome: OK test-coverage-readiness.md
  next: docs

--- step 3: docs (doc-sync) ---
validate-fleet-outcome: OK doc-sync-readiness.md
  next: <campaign done>

Campaign complete. Nodes visited: audit tests docs

./scripts/validate-fleet-outcome.sh (all three readiness docs) → All passed
```

**Note:** Fork ledgers were already `PHASE: DONE` from the interactive dogfood (2026-06-20). The
headless invocation failed auth and the work was completed by hand; the nodes above re-validated
the existing gates rather than re-landing PRs (`prs_merged = 0`). This validates `--repo`
orchestration and the gates against an external checkout — it is not an autonomous PR landing.
Lane 2 follow-up closed: unconditional archive emission is now wired in
`run-mission-headless.sh` / `run-campaign.sh` (kept under target `--repo` after real invocations).

## Comparison to interactive run (2026-06-20)

| | Interactive | Headless (Lane 2) |
|--|-------------|-------------------|
| Runtime | Cursor Grok | `grok -p` via `run-campaign.sh` |
| Auth | N/A (in-IDE) | CLI auth required |
| `--repo` | Added during dogfood | Validated end-to-end |
| Archives | None on gemoji | Emitted on subsequent runs (v0.2.0+ keep policy) |
| Duration | Multi-session interactive | ~163s headless campaign |