# Handoff — first real substrate archive (Lane 1)

**Mission:** adversarial-review-and-fix  
**Repo:** autonomous-fleet (this checkout)  
**Base:** `main`  
**Runtime:** Grok (headless)

## Goal (bind with /goal)

Mission adversarial-review-and-fix DONE: `docs/first-substrate-progress.md` has `PHASE: DONE`, all TASK rows have `CODED=t REVIEWED=t MERGED=t` (or documented human gates), `docs/first-substrate-readiness.md` has `fleet-outcome.status: done` and `archive_enabled: true`, and a validated archive exists at `.fleet/runs/<run_id>/`.

## What success looks like

1. **Phase 0** — Code-grounded review of the scope listed in `docs/first-substrate-progress.md`. Freeze findings to `docs/first-substrate-review.md` and `.fleet/runs/<run_id>/p0-review-findings.json`. Run skeptic pass. Verify with `verify_findings.py` (`unverified_findings: 0`).
2. **Layer 3** — For each verified finding you close, write `reviewer-blind-fix-<id>.md` before fixer sees findings; populate blind-fix chain in attestations.
3. **Phase 1** — Fix confirmed findings one at a time; cross-vendor review where the mission requires it.
4. **Archive** — Accrete all artifacts under `.fleet/runs/<run_id>/`, call `fleet_run.write_manifest`, validate with `validate_run_archive.py` and `verify_blind_fix.py`.
5. **Trace** — Ensure `trace.jsonl` records coordinator transitions (not only T-FINAL).
6. **Ledger** — Update `docs/first-substrate-progress.md` after every task state change.
7. **Readiness** — Set `docs/first-substrate-readiness.md` fleet-outcome when done; set `run_id` and `archive_enabled: true`.
8. **Dogfood doc** — Append validator stdout to `docs/external-dogfood/first-substrate-run.md` § Post-run evidence.

## Commands (mechanical)

```bash
./scripts/validate-first-substrate-archive.sh <run_id>
./scripts/validate-all.sh
```

## Constraints

- Do **not** edit `.fleet/runs/example-fixture/` (canonical CI fixture).
- Prefer **small, reviewable PRs** or a single branch `dogfood/first-substrate-run` if merging is blocked.
- If auth or turn budget blocks completion, set `PHASE: BLOCKED` with exact reason in progress doc.

Activate: `adversarial-review-and-fix`, `autonomous-fleet-core`, `autonomous-fleet-adapter-grok`. Follow `engine.md` and the mission SKILL in full.