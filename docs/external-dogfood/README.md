# External dogfood

Prove autonomous-fleet beyond self-dogfood on small OSS repos. Each pack has a campaign YAML,
setup steps, and success criteria.

| Pack | Campaign | Nodes | Community hooks |
|------|----------|-------|-----------------|
| [repo-health on gemoji](repo-health-gemoji.md) | `repo-health-campaign.yaml` | doc-sync → test-coverage | None |
| [ship-with-proof on gemoji](ship-with-proof-gemoji.md) | `ship-with-proof-campaign.yaml` | audit → tests → docs | Optional gstack post-gates |
| [Evidence (interactive)](ship-with-proof-evidence.md) | — | ravidsrk/gemoji @ `1541ce9` | Interactive dogfood 2026-06-20 |
| [Headless run (Lane 2)](gemoji-headless-run.md) | `ship-with-proof-campaign.yaml` | ravidsrk/gemoji fork | `grok -p` + `--repo` validation |

## Shared target

[github/gemoji](https://github.com/github/gemoji) — small Ruby gem, real OSS, not autonomous-fleet.

## Quick dry-run (from this repo)

```bash
./scripts/validate-headless.sh
./scripts/run-campaign.sh grok --campaign docs/external-dogfood/repo-health-campaign.yaml --dry-run
./scripts/run-campaign.sh grok --campaign docs/external-dogfood/ship-with-proof-campaign.yaml --dry-run
./scripts/bench-adversarial.sh --help
```

**Operator runs:** Headless driver + `--repo` + archive emission are ready (v0.2.0). Gemoji
ship-with-proof has interactive evidence (`1541ce9`) and headless validation (Lane 2, 2026-06-27).
Adversarial bench A/B **numbers** remain ⬜ pending authenticated operator sessions.

## Before first run on any external repo

Run `/setup-autonomous-fleet` in the target repo (or follow manual steps in each pack).

## Related

- `docs/research-community-skills.md` — mix-and-match design
- `skills/autonomous-fleet-core/references/community-skills.md` — install matrix