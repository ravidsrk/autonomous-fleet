# Lane 2 — headless ship-with-proof on gemoji

**Status:** DONE (2026-06-27)  
**Closes gap:** external dogfood headless path (`grok -p` + `--repo` validated)  
**Duration:** ~163s (3 nodes × verification pass on pre-completed fork)
**Fork:** [ravidsrk/gemoji](https://github.com/ravidsrk/gemoji) @ `fleet/gemoji-ship-with-proof-base`

## Why this run

Lane 1 proved substrate + headless auth on **autonomous-fleet**. Lane 2 proves the same headless
driver against an **external** checkout via `run-campaign.sh --repo`.

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

**Note:** Fork ledgers were already `PHASE: DONE` from interactive dogfood (2026-06-20). This run
proved headless orchestration end-to-end; nodes re-validated gates rather than re-landing PRs.
No `.fleet/runs/` archives were written on gemoji (missions did not enter Phase 0/1 anew).
Archive emission on external `--repo` checkouts is a follow-up item.

## Comparison to interactive run (2026-06-20)

| | Interactive | Headless (Lane 2) |
|--|-------------|-------------------|
| Runtime | Cursor Grok | `grok -p` via `run-campaign.sh` |
| Auth | N/A (in-IDE) | CLI auth required |
| `--repo` | Added during dogfood | Validated end-to-end |
| Archives | None on gemoji | None (verification-only; no new Phase 0) |
| Duration | Multi-session interactive | ~163s headless campaign |