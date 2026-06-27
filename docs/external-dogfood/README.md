# External dogfood

Exercise autonomous-fleet's gates on small OSS repos beyond the self-dogfood. Each pack has a
campaign YAML, setup steps, and success criteria.

> **Status — gate-validation only.** No external run-archive with autonomously-landed PRs
> (`prs_merged > 0`) exists yet. The gemoji "external dogfood" below **re-validated pre-existing
> `PHASE: DONE` ledgers** (landed by hand during the 2026-06-20 interactive session), and the
> headless path **failed auth and was completed by hand**. These runs validate orchestration and
> gates against an external checkout — they are **not** evidence of autonomous PR landing or of
> build-blindness beyond the self-dogfood.

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

**Operator runs:** Headless driver + `--repo` + archive emission are wired (v0.2.0). Gemoji
ship-with-proof has interactive evidence (`1541ce9`) and a headless **gate-validation** pass
(Lane 2, 2026-06-27) that **re-validated pre-existing `DONE` ledgers** — the headless attempt hit
an auth failure and the landing work was completed by hand, so no PR was autonomously landed
(`prs_merged = 0`). Independent adversarial bench A/B **numbers**, and any external run-archive with
`prs_merged > 0`, remain ⬜ pending authenticated operator sessions.

## Before first run on any external repo

Run `/setup-autonomous-fleet` in the target repo (or follow manual steps in each pack).

## Related

- `docs/research-community-skills.md` — mix-and-match design
- `skills/autonomous-fleet-core/references/community-skills.md` — install matrix