# Adversarial review — REST of the codebase (FROZEN, 2026-06-21)

Sweep of everything PR #26 did not cover: the CLIs + fleet_outcome older code, 8 shell scripts,
engine.md + 4 references, 5 adapters, 17 missions, 6 campaigns. 6 finder partitions, each finding
verified by 2 independent refuters. Run in two passes (a transient API rate-limit wave truncated the
first; the resume completed coverage of all 6 partitions). 16 raised across both passes, 12 confirmed,
all fixed.

| sev | id | file | defect |
|-----|----|------|--------|
| P2 | F1-eval | scripts/lib/fleet_outcome.py | eval_edge equality silently misrouted on a trailing-token operand (`status == blocked now` -> False, wrong branch) instead of raising per the do-not-guess contract |
| P2 | E1-orca | adapter-orca | reviewer command `codex --full-auto` is rejected by codex (exit 2); must be `codex exec` |
| P2 | E2-grok | adapter-grok | hardcoded model id `composer-2.5-fast` rejected by grok as unknown |
| P2 | F2 | scripts/lib/fleet_outcome.py | pick_next_node crashed (uncaught ValueError) on a missing-metric edge, stranding a valid `always` fallback |
| P2 | F3 | scripts/validate_fleet_outcome.py | validate CLI only caught ValueError; a malformed-YAML doc aborted the whole batch |
| P2 | F4 | scripts/lib/fleet_outcome.py | pick_next_node returned None for a matched edge missing `to` (read as terminal) instead of failing loud |
| P2 | B2 | scripts/run-campaign.sh | a stale venv (binary present, pyyaml missing) crashed with a raw traceback |
| P2 | C4 | engine.md | the "3-failure circuit-breaker" was referenced 3x but never defined |
| P2 | E-1 | 3 container-use adapters | claimed `container-use merge <env>` merges "into BASE"; it merges into the CURRENT branch and bypasses the PR gate |
| P1 | D1 | run-campaign.sh / runtime-goals.md | a node finishing `status: blocked` fell through to "Campaign complete" (no halt) |
| P1 | E-2 | adapter-codex / runtime-goals.md | headless `codex exec` is single-shot and ignores `/goal`; the headless prompt's `/goal` was inert with no continuation harness |
| P1 | F1-miss | scripts/campaigns/handoff-to-product.yaml + run-campaign.sh | the runner's unconditional cycle abort made the campaign's designed back-edges (deps->audit, bugs->docs) un-runnable |

## Notable clean partitions
Shell-script injection sweep (the original-RCE class): no new injection found in run-campaign.sh /
run-mission-headless.sh / validate-*.sh beyond B2's robustness gap. Missions/campaigns: every shipped
campaign edge gates on a metric registered in its node's mission frozenset (so F2's crash is not hit by
any shipped DAG — it is a hand-authored-typo footgun, fixed defensively).
