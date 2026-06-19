# ship-with-proof dogfood evidence — gemoji (2026-06-20)

## Target

- Repo: `/tmp/gemoji` (clone of [github/gemoji](https://github.com/github/gemoji))
- Branch: `fleet/gemoji-ship-with-proof-base`
- Commit: `1541ce9` (local dogfood; not pushed upstream)

## Campaign

`external-gemoji-ship-with-proof`: audit → test-coverage → doc-sync

| Node | Status | Readiness | validate-fleet-outcome |
|------|--------|-----------|----------------------|
| audit | DONE | `docs/arch-build-readiness.md` | OK |
| tests | DONE | `docs/test-coverage-readiness.md` | OK |
| docs | DONE | `docs/doc-sync-readiness.md` | OK |

Program ledger: `docs/fleet-program-progress.md` → `PHASE: DONE`

Edge eval after audit: `audit → tests` (confirmed via `eval-campaign-edge.sh`)

## Code changes (3 findings closed)

| ID | Fix |
|----|-----|
| REL-001 | `assert_equal 0, custom.size` in `test/emoji_test.rb` |
| REL-002 | `edit_emoji` clears stale index keys in `lib/emoji.rb` + new test |
| REL-003 | `Minitest::Test` in `test/test_helper.rb` |

Tests: 22 + 4 runs, 0 failures (`ruby -Ilib:test test/*_test.rb`)

## Infrastructure learned

1. **`--repo` flag** — `run-campaign.sh` and `run-mission-headless.sh` now accept `--repo PATH` so campaigns target external checkouts.
2. **Headless Grok auth** — `grok -p … --cwd` failed with `Auth(AuthorizationRequired)`. Dogfood completed **interactively** in Cursor Grok. Re-run headless after `grok` login is configured on the host.

## Reproduce validation (no agents)

```bash
./scripts/validate-fleet-outcome.sh \
  /tmp/gemoji/docs/arch-build-readiness.md \
  /tmp/gemoji/docs/test-coverage-readiness.md \
  /tmp/gemoji/docs/doc-sync-readiness.md
```