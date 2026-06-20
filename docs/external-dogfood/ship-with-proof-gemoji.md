# External dogfood — ship-with-proof on gemoji

Prove community-skill integration and the **ship-with-proof** campaign on a small external repo.

## Target

| Field | Value |
|-------|-------|
| Repo | [github/gemoji](https://github.com/github/gemoji) |
| Why | Real OSS Ruby gem; audit + tests + docs surface; not autonomous-fleet |
| Campaign | `ship-with-proof-campaign.yaml` |
| Community (optional) | `health` post-gate; `ship` only if opening a meta-PR (gstack default unprefixed ids) |

## Setup

```bash
git clone https://github.com/github/gemoji.git /tmp/gemoji
cd /tmp/gemoji

# Fleet skills (from autonomous-fleet clone)
AF=/path/to/autonomous-fleet
npx skills add "$AF" \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet \
  --skill fleet-program \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-grok \
  --skill adversarial-review-and-fix \
  --skill test-coverage \
  --skill doc-sync \
  -y

# Run setup once in the agent
# /setup-autonomous-fleet → adapter grok, prefix fleet/, bundle ship-with-proof

git checkout -b fleet/gemoji-ship-with-proof-base
```

### Optional gstack (post-gates only)

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup --host cursor  # or your host
```

Install only `health` and `ship` if you plan post-gates — not the full catalog. (Prefixed
`gstack-*` ids require `SKILL_PREFIX=1 ./setup`; campaign YAML uses unprefixed ids.)

## Dry-run (from autonomous-fleet clone)

```bash
./scripts/run-campaign.sh grok \
  --campaign docs/external-dogfood/ship-with-proof-campaign.yaml \
  --dry-run
```

Expected nodes: `audit` → `tests` → `docs`.

## Full run (from gemoji checkout)

```bash
$AF/scripts/run-campaign.sh grok \
  --campaign $AF/docs/external-dogfood/ship-with-proof-campaign.yaml \
  --repo /tmp/gemoji \
  --max-turns 80
```

Or interactive: activate `fleet-program` with preset `ship-with-proof` and `/goal` per
`skills/autonomous-fleet-core/references/runtime-goals.md`.

## Success criteria

| Node | Readiness doc | Key metrics |
|------|---------------|-------------|
| audit | `docs/arch-build-readiness.md` | Frozen review; fixes closed |
| test-coverage | `docs/test-coverage-readiness.md` | `gaps_open: 0` |
| doc-sync | `docs/doc-sync-readiness.md` | `drift_open: 0` |

Program ledger: `docs/fleet-program-progress.md` with `PHASE: DONE`.

Each readiness doc: valid `fleet-outcome` YAML; `./scripts/validate-fleet-outcome.sh` passes.

## Post-gates (manual, after campaign DONE)

| Gate | When for gemoji |
|------|-----------------|
| `health` | Optional scorecard on repo |
| `ship` | Only if promoting BASE → default branch via PR |
| `qa` | Skip — no web staging URL |

Record `run.duration_min` and `prs_merged` in each `fleet-outcome` (fleet-outcome.md § Run telemetry).

## Evidence checklist

- [x] Dry-run visited audit, tests, docs
- [x] Each node readiness doc exists with `status: done`
- [x] `validate-fleet-outcome.sh` passed per node
- [x] DECISIONS.md records adapter, prefix, any gstack post-gate outcome

**Completed 2026-06-20.** See [ship-with-proof-evidence.md](ship-with-proof-evidence.md).

**Note:** Headless `grok -p` requires CLI auth; interactive dogfood used when auth unavailable. Use `--repo /tmp/gemoji` on campaign scripts.