# External dogfood

Exercise autonomous-fleet's gates on small OSS repos beyond the self-dogfood. Each pack has a
campaign YAML, setup steps, and success criteria.

> **Status (2026-07-03).** The first external run-archive with autonomously-landed
> PRs exists: [`gemoji-autonomous-run.md`](gemoji-autonomous-run.md) — `doc-sync`
> on ravidsrk/gemoji (fork hard-synced to upstream first), 3 PRs opened /
> build-blind reviewed (one genuine FAIL→fix→PASS round) / merged by agents,
> `prs_merged: 3`, validated archive at
> `.fleet/runs/20260703T054520Z-doc-sync-3e8173/`. Topology: interactive
> claude coordinator + sandboxed codex builders + fresh codex reviewers
> (single-vendor caveat recorded). **Still open:** a single-process fully
> headless external run (the codex sandbox-bypass path needs explicit operator
> opt-in — denied under auto mode), and adversarial-bench A/B numbers. The
> older gemoji packs below (2026-06-19/27) remain what they were:
> gate-validation over hand-landed ledgers, not autonomous-landing evidence.

| Pack | Campaign | Nodes | Community hooks |
|------|----------|-------|-----------------|
| [**Autonomous run (2026-07-03)**](gemoji-autonomous-run.md) | — (single mission) | doc-sync, 3 PRs merged | None |
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
(Lane 2, 2026-06-27) that **re-validated pre-existing `DONE` ledgers** — that headless attempt hit
an auth failure and its landing work was completed by hand (`prs_merged = 0`). The external
run-archive with `prs_merged > 0` landed 2026-07-03
([gemoji-autonomous-run.md](gemoji-autonomous-run.md)). Independent adversarial bench A/B
**numbers**, and a single-process fully-headless external run, remain ⬜ pending
explicit operator opt-in sessions.

## Before first run on any external repo

Run `/setup-autonomous-fleet` in the target repo (or follow manual steps in each pack).

## Related

- `docs/research-community-skills.md` — mix-and-match design
- `skills/autonomous-fleet-core/references/community-skills.md` — install matrix