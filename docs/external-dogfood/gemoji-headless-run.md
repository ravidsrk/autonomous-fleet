# Lane 2 — headless ship-with-proof on gemoji

**Status:** IN PROGRESS  
**Closes gap:** external dogfood headless path (interactive evidence exists; `grok -p` + `--repo` pending)  
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
(pending)
```

## Comparison to interactive run (2026-06-20)

| | Interactive | Headless (Lane 2) |
|--|-------------|-------------------|
| Runtime | Cursor Grok | `grok -p` via `run-campaign.sh` |
| Auth | N/A (in-IDE) | CLI auth required |
| `--repo` | Added during dogfood | Validated end-to-end |
| Archives | None on gemoji | TBD under `.fleet/runs/` |