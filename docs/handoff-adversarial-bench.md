# Handoff — adversarial bench (Lane 3, external OSS)

**Mission:** adversarial-review-and-fix  
**Repo:** external OSS target (bench clone under `/tmp/fleet-bench/`)  
**Runtime:** headless adapter (grok / claude / codex)  
**Comparator:** substrate-off vs substrate-on (env vars set by `bench-adversarial.sh`)

## Goal (bind with /goal)

Mission adversarial-review-and-fix DONE: the run's ledger (`docs/arch-build-progress.md`, run-keyed with `-<run_short>` per engine step 9) has `PHASE: DONE` (or `BLOCKED` with an explicit reason), its readiness doc (`docs/arch-build-readiness.md` run-keyed likewise) has `fleet-outcome.status: done` and `archive_enabled: true`, and a validated archive exists at `.fleet/runs/<run_id>/`.

## Bench-specific constraints

1. **External OSS** — do not push to upstream without an operator-owned fork. Local branches and local fixes are fine; record any deferred upstream work in the readiness doc.
2. **Archive first** — the bench measures substrate value via archive metrics (`analyze_seat.py`), not upstream merge count. Prefer completing Phase 0 (review + skeptic + freeze) and at least one closed finding in Phase 1 over chasing every finding.
3. **Substrate layers** — honor `FLEET_DISABLE_*` env vars inherited from the bench driver. Do not unset them mid-run.
4. **Turn budget** — if blocked, set `PHASE: BLOCKED` with the exact reason in `docs/arch-build-progress.md` and still emit the partial archive (trace + findings + manifest).
5. **Record run_id** — append the archive path and `run_id` to the per-target stub under `docs/external-dogfood/adversarial-bench/` when the coordinator can reach the fleet clone.

## What success looks like

1. **Phase 0** — Code-grounded review → skeptic → freeze. Emit `p0-review-findings.json` and `p0-skeptic-findings.json` under `.fleet/runs/<run_id>/`. Run `verify_findings.py` when substrate Layer 1 is active.
2. **Phase 1** — Fix at least one confirmed finding end-to-end (blind-fix attestation when Layer 3 is active).
3. **Archive** — Accrete artifacts under `.fleet/runs/<run_id>/`; call `fleet_run.write_manifest` when Layer 4 is active.
4. **Readiness** — Set `docs/arch-build-readiness.md` with `fleet-outcome.status: done` and `archive_enabled: true`.

Activate: `adversarial-review-and-fix`, `autonomous-fleet-core`, and the installed runtime adapter. Follow `engine.md` and the mission SKILL in full.