# Handoff — Lane 2 headless ship-with-proof on gemoji (COMPLETE 2026-06-27)

**Campaign:** `external-gemoji-ship-with-proof` (audit → tests → docs)  
**Repo:** `/tmp/gemoji` (fork `ravidsrk/gemoji`, branch `fleet/gemoji-ship-with-proof-base`)  
**Fleet root:** autonomous-fleet clone (scripts + validators)  
**Runtime:** Grok headless (`grok -p`)

## Goal

Headless path validated on an **external** repo: `docs/fleet-program-progress.md` in gemoji has
`PHASE: DONE`, all three node readiness docs pass `./scripts/validate-fleet-outcome.sh`, and at
least one `.fleet/runs/<run_id>/` archive exists under the **gemoji** checkout with manifest +
trace. Update `docs/external-dogfood/gemoji-headless-run.md` in autonomous-fleet with validator
output when complete.

## Context

Interactive dogfood completed 2026-06-20 (see `docs/external-dogfood/ship-with-proof-evidence.md`).
Code fixes and readiness docs already exist on the fork. This run proves **`--repo` headless**
works with Grok auth (Lane 1 validated auth on autonomous-fleet).

## Per-node success

| Node | Mission | Readiness |
|------|---------|-----------|
| audit | adversarial-review-and-fix | `docs/arch-build-readiness.md` |
| tests | test-coverage | `docs/test-coverage-readiness.md` |
| docs | doc-sync | `docs/doc-sync-readiness.md` |

## Mechanical validation (from autonomous-fleet clone)

```bash
AF=/Users/ravindra/projects/autonomous-fleet
$AF/scripts/validate-fleet-outcome.sh \
  /tmp/gemoji/docs/arch-build-readiness.md \
  /tmp/gemoji/docs/test-coverage-readiness.md \
  /tmp/gemoji/docs/doc-sync-readiness.md
ls /tmp/gemoji/.fleet/runs/
```

## Constraints

- Do **not** force-push upstream `github/gemoji`; work stays on fork branch.
- Prefer confirming existing fixes over large new scope; produce archives + evidence.
- If auth or turn budget blocks completion, set `PHASE: BLOCKED` in gemoji
  `docs/fleet-program-progress.md` with exact reason.

Activate: `fleet-program`, `autonomous-fleet-core`, `autonomous-fleet-adapter-grok`, and each
node mission skill. Follow `engine.md`.