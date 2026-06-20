# External dogfood

Prove autonomous-fleet beyond self-dogfood on small OSS repos. Each pack has a campaign YAML,
setup steps, and success criteria.

| Pack | Campaign | Nodes | Community hooks |
|------|----------|-------|-----------------|
| [repo-health on gemoji](repo-health-gemoji.md) | `repo-health-campaign.yaml` | doc-sync → test-coverage → cleanup | None |
| [ship-with-proof on gemoji](ship-with-proof-gemoji.md) | `ship-with-proof-campaign.yaml` | audit → tests → docs | Optional gstack post-gates |
| [Evidence (interactive; headless pending)](ship-with-proof-evidence.md) | — | ravidsrk/gemoji @ `1541ce9` | Interactive dogfood 2026-06-20; headless path not yet validated |

## Shared target

[github/gemoji](https://github.com/github/gemoji) — small Ruby gem, real OSS, not autonomous-fleet.

## Quick dry-run (from this repo)

```bash
./scripts/run-campaign.sh grok --campaign docs/external-dogfood/repo-health-campaign.yaml --dry-run
./scripts/run-campaign.sh grok --campaign docs/external-dogfood/ship-with-proof-campaign.yaml --dry-run
```

## Before first run on any external repo

Run `/setup-autonomous-fleet` in the target repo (or follow manual steps in each pack).

## Related

- `docs/research-community-skills.md` — mix-and-match design
- `skills/autonomous-fleet-core/references/community-skills.md` — install matrix