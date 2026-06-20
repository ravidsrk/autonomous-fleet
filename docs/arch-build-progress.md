# arch-build-progress (FIX run ledger)

PHASE: FIXING

REVIEW_DOC: docs/adversarial-audit-2026-06-20.md  (frozen; 17 code/contract findings + 12 research findings, all adversarially verified)
BASE: ravidsrk/adversarial-fresh (off main@1460f47)
REPO_ROOT: /Users/ravindra/orca/workspaces/autonomous-fleet/new-research  (repoId d19bcfee-46e5-4bb7-9706-349035004402)
BASE worktree: /Users/ravindra/orca/workspaces/autonomous-fleet/adversarial-fresh
MAINTAINER: Ravindra Kumar <ravidsrk@gmail.com>
COORDINATOR handle: (this Claude Code session — set on first dispatch)

ROLES: @grok codes (interactive Orca terminal — verified working; `grok -p` headless is auth-broken, do
NOT use it), @codex reviews build-blind (`codex --full-auto`), @claude integrates (opens PR, merges).

Derived (REVIEW_DOC states no explicit wave/hot-file map, so derived here from the findings' files):
the 5 fix tasks below touch DISJOINT file sets, so all run in parallel; the P0 (RCE-01) leads.

## CLOSE-INDEX (by wave)

Wave 1 (all parallel; disjoint files; P0 first):

- RCE-01   P0  OPEN  — RCE via $MISSION/$ROOT interpolated into python -c (run-campaign.sh:145; run-mission-headless.sh:95-96)  [task: drivers]
- GIT-02   P1  OPEN  — [[ -d .git ]] rejects worktrees (run-campaign.sh:97; run-mission-headless.sh:81)  [task: drivers]
- CLAUDE-03 P1 OPEN  — claude --cwd nonexistent flag; --max-turns dropped (run-mission-headless.sh:117)  [task: drivers]
- CODEX-04  P1 OPEN  — codex -p not non-interactive; needs codex exec (run-mission-headless.sh:119-127)  [task: drivers]
- YOLO-11   P2 OPEN  — --yolo auto-approve default, no trust docs (run-mission-headless.sh:20; run-campaign.sh:20)  [task: drivers]
- CYCLE-12  P3 OPEN  — VISITED never consulted for cycle detection (run-campaign.sh:135,186)  [task: drivers]
- DRYRUN-13 P3 OPEN  — dry-run depth data-dependent (run-campaign.sh:151-184)  [task: drivers]
- KEYERR-14 P3 OPEN  — missing start/mission -> raw KeyError (run-campaign.sh:108-116)  [task: drivers]
- PIN-17a   P3 OPEN  — pin venv deps in the two driver scripts (inline)  [task: drivers]
- EVAL-05   P2 OPEN  — eval_edge TypeError string/float vs numeric op (fleet_outcome.py:108-128)  [task: fleet-outcome]
- VALIDATE-06 P2 OPEN — validate_outcome no type/enum checks; typo mission skips metrics (fleet_outcome.py:57-79)  [task: fleet-outcome]
- EVAL-07   P2 OPEN  — status fast-path no quote-strip; missing metric == and != both False (fleet_outcome.py:96-127)  [task: fleet-outcome]
- FM-15     P3 OPEN  — split_frontmatter fails on leading blank/BOM (fleet_outcome.py:32-40)  [task: fleet-outcome]
- DEFER-16  P3 OPEN  — deferred_missions regex truncates ids; ignores bare strings (fleet_outcome.py:100-106)  [task: fleet-outcome]
- VENV-08   P2 OPEN  — validate-all aborts on missing skill-creator; venv pkg race (validate-all.sh; validate-skills.sh)  [task: validators]
- LEDGER-09 P2 OPEN  — goal-condition ledger parser swallows unknown keys (validate-goal-condition.sh:84-90)  [task: validators]
- DUP-10    P2 OPEN  — validate_fleet_outcome double-validates arch-build doc (validate_fleet_outcome.py:24-27)  [task: validators]
- PIN-17b   P3 OPEN  — requirements.txt + pin validator/CI venv bootstraps  [task: validators]
- PROV-01   P1 OPEN  — 0.92 = Codex single-agent mislabeled as dataset rate (84%) (doc-sync/SKILL.md:4,64; README:179; missions.md:6; engine.md:263)  [task: claims-honesty]
- PROV-02   P1 OPEN  — Tier-1 band 0.84-0.92 overstates (engine.md:263; missions.md:6; test-coverage/SKILL.md; dependency-update/SKILL.md)  [task: claims-honesty]
- PROV-04   P1 OPEN  — perf ~0.68 is Codex's; real 55% (engine.md:268)  [task: claims-honesty]
- PROV-06   P1 OPEN  — all per-skill rates are Codex column; UI/migration cats invented (test-coverage/dependency-update/design-integration/targeted-migration/landing-page SKILL.md)  [task: claims-honesty]
- PROV-08   P3 OPEN  — gemoji ~2k LOC wrong (repo-health-campaign.yaml:2)  [task: claims-honesty]
- PROV-09   P1 OPEN  — Orca "(most battle-tested)" unsupported superlative (missions.md:36)  [task: claims-honesty]
- GEM-001   P1 OPEN  — only evidence admits headless failed/ran interactively (ship-with-proof-evidence.md:36; README:3)  [task: claims-honesty]
- GEM-002   P1 OPEN  — "22 + 4 runs" fabricated; cmd runs 4 tests (ship-with-proof-evidence.md:31)  [task: claims-honesty]
- GEM-003   P3 OPEN  — "not pushed upstream" hides public fork (ship-with-proof-evidence.md:7)  [task: claims-honesty]
- RD-2      P1 OPEN  — 3 research docs cite gemoji Done/Shipped (research-community-skills.md:183 + research-skill-composition.md:376 + composition-e2e-reasoning.md:102)  [task: claims-honesty]
- RD-3      P2 OPEN  — DECISIONS C-01 "proven in dogfood" unsupported (research-skill-composition.md:350)  [task: claims-honesty]
- F1        P1 OPEN  — gstack-* gate ids 404 upstream; default unprefixed -> no-op (campaigns.md:123-179; community-skills.md:130)  [task: gstack-gates]

## TASK ROWS

TASK drivers        | WAVE=1 | FILE=run-campaign.sh,run-mission-headless.sh | LANE=CODE | CLOSES=[RCE-01,GIT-02,CLAUDE-03,CODEX-04,YOLO-11,CYCLE-12,DRYRUN-13,KEYERR-14,PIN-17a] | CODED=f PR_OPEN=f REVIEWED=f MERGED=f ACCEPT=f | OPS=none | PR#- | WT=- | WORKER=- | NOTE=has the P0
TASK fleet-outcome  | WAVE=1 | FILE=scripts/lib/fleet_outcome.py | LANE=CODE | CLOSES=[EVAL-05,VALIDATE-06,EVAL-07,FM-15,DEFER-16] | CODED=f PR_OPEN=f REVIEWED=f MERGED=f ACCEPT=f | OPS=none | PR#- | WT=- | WORKER=- | NOTE=tests in tests/test_fleet_campaign.py
TASK validators     | WAVE=1 | FILE=validate-*.sh,validate_fleet_outcome.py,ci.yml,requirements.txt | LANE=CODE | CLOSES=[VENV-08,LEDGER-09,DUP-10,PIN-17b] | CODED=f PR_OPEN=f REVIEWED=f MERGED=f ACCEPT=f | OPS=none | PR#- | WT=- | WORKER=- | NOTE=tests in tests/test_goal_condition.py + new
TASK claims-honesty | WAVE=1 | FILE=README.md,skills/**/SKILL.md,missions.md,engine.md,docs/external-dogfood/*,docs/research-*.md | LANE=CODE | CLOSES=[PROV-01,PROV-02,PROV-04,PROV-06,PROV-08,PROV-09,GEM-001,GEM-002,GEM-003,RD-2,RD-3] | CODED=f PR_OPEN=f REVIEWED=f MERGED=f ACCEPT=f | OPS=none | PR#- | WT=- | WORKER=- | NOTE=prose; real cross-agent aggregates docs84/build74/test61.5/perf55; cite arXiv 2601.15195
TASK gstack-gates   | WAVE=1 | FILE=campaigns.md,community-skills.md | LANE=CODE | CLOSES=[F1] | CODED=f PR_OPEN=f REVIEWED=f MERGED=f ACCEPT=f | OPS=none | PR#- | WT=- | WORKER=- | NOTE=unprefixed ids or document --prefix

## HOT-FILE MAP (derived)

The 5 tasks own disjoint file sets; no cross-task hot file. Within each task, the worker serializes its
own files. run-campaign.sh + run-mission-headless.sh are co-owned by drivers (the P0 spans both).

## OPS / VERIFY-AT-SCALE

(none expected — this is a skills/scripts repo with no money/keys/prod surface; acceptance is local
pytest + shell harness on fixtures.)

## DOWNSTREAM HUMAN GATES (not done by swarm)

- BASE (ravidsrk/adversarial-fresh) -> main promotion: human meta-PR.
- No deploy, no OPS applies.

## CONTEXT (for a fresh coordinator)

orca runtime ready; agent CLIs claude/codex/grok present; gh authed (ravidsrk). Interactive grok VERIFIED
working with tool use; `grok -p` headless is auth-broken (XAI_API_KEY set but rejected) — dispatch grok via
Orca interactive terminal only. Wave 1 = all 5 tasks, parallel, disjoint files. Next: create Orca tasks,
spawn one grok coder worktree per task off BASE, dispatch --inject, then run the check --wait pipeline.
