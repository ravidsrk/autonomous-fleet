# secure-ship campaign: end-to-end dogfood (2026-06-21)

Drove the actual `run-campaign.sh` loop through the wired secure-ship gates. The mission BODIES were
stubbed to scripted readiness outcomes (the missions are dogfooded individually in #24/#26/#27, and a
real 3-mission headless run is gated here: grok auth is broken, codex exec is single-shot per the E-2
finding). So this exercises the campaign DRIVER + the new gating logic for real, against a throwaway
git repo with a stub mission runner.

## Scenarios (real run-campaign.sh, exit codes asserted)
| scenario | path | exit |
|----------|------|------|
| happy-path | audit -> deps -> docs -> complete | 0 |
| blocked audit | audit (status: blocked) -> HALT "Campaign BLOCKED at node audit" | 2 |
| re-audit back-edge | audit -> deps (major deferred) -> audit -> deps (clean) -> docs | 0 |
| non-converging loop | audit <-> deps until per-node revisit budget (3) -> abort | 1 |

## Bug the e2e caught (and fixed)
The blocked-halt (D1, shipped in PR #27) was SILENTLY BROKEN: the status-read passed a `str` to
`parse_readiness`, which expects a `Path` (`path.read_text`), raising an `AttributeError` that
`2>/dev/null || true` swallowed. So `NODE_STATUS` was always empty and the halt never fired — a
blocked audit flowed straight through to deps/docs, the exact silent-ship the fix was meant to stop.
The fix passed CI because the readiness VALIDATION worked and the halt path had no test exercising a
genuinely blocked outcome. Fixed: pass `Path(...)`, stop masking the error, and added an end-to-end
regression test (`test_blocked_node_halts_campaign`). Also fixed a cosmetic bug: the completion line
printed "dry-run complete" on real runs because `${DRY_RUN:+...}` is truthy for the string "0".

## Lesson
A fix that isn't exercised the way production runs it can be silently inert. Only an end-to-end run
with a real blocked outcome revealed that the security gate, validated and CI-green, did nothing.
