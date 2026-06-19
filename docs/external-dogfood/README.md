# External dogfood — repo-health on gemoji

Prove autonomous-fleet beyond self-dogfood by running **repo-health** on a small external repo.

## Target

| Field | Value |
|-------|-------|
| Repo | [github/gemoji](https://github.com/github/gemoji) |
| Why | Small, real OSS app; README + tests + cleanup surface; not autonomous-fleet |
| Campaign | `repo-health-campaign.yaml` (doc-sync → test-coverage → cleanup) |

## Setup (on a machine with grok/claude + gh)

```bash
git clone https://github.com/github/gemoji.git /tmp/gemoji
cd /tmp/gemoji

npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill fleet-program \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-grok \
  --skill doc-sync \
  --skill test-coverage \
  --skill cleanup \
  -y

git checkout -b fleet/gemoji-repo-health-base
```

## Dry-run plan (no agents)

From the **autonomous-fleet** clone (validates campaign machinery):

```bash
./scripts/run-campaign.sh grok --campaign docs/external-dogfood/repo-health-campaign.yaml --dry-run
```

## Full run (interactive or headless)

From **gemoji** checkout:

```bash
# Plan
./scripts/run-campaign.sh grok --campaign /path/to/autonomous-fleet/docs/external-dogfood/repo-health-campaign.yaml --dry-run

# Execute (per node — long-running)
/path/to/autonomous-fleet/scripts/run-campaign.sh grok \
  --campaign /path/to/autonomous-fleet/docs/external-dogfood/repo-health-campaign.yaml \
  --max-turns 80
```

Or activate `fleet-program` in Grok with `/goal` per
`skills/autonomous-fleet-core/references/runtime-goals.md`.

## Success criteria

| Node | Readiness doc | Key metrics |
|------|---------------|-------------|
| doc-sync | `docs/doc-sync-readiness.md` | `drift_open: 0` |
| test-coverage | `docs/test-coverage-readiness.md` | `gaps_open: 0` |
| cleanup | `docs/cleanup-readiness.md` | `cleanup_items_open: 0` |

Program ledger: `docs/fleet-program-progress.md` with `PHASE: DONE`.

Record `run.duration_min` and `prs_merged` in each `fleet-outcome` (see fleet-outcome.md § Run telemetry).