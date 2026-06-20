# Adversarial audit (workflow), 2026-06-20

Source of truth for the multi-agent adversarial review and research run on the autonomous-fleet
repo. Produced by two Claude Code Workflow runs, each fanning out finder dimensions then
adversarially verifying every finding by its matching method (code findings by reachability and
live reproduction, claim findings by independent web sources). A finding is listed here only if it
survived a verifier whose default bias was to refute it.

Provenance:

- Review workflow run: `wf_4f214988-351` (task `wb823qgzl`). 10 finder dimensions, 55 raw findings,
  52 survived verification, deduped to 17 confirmed.
- Research workflow run: `wf_34abe8aa-2f3` (task `weze6bvzv`). 4 claim dimensions, 20 raw probes,
  12 confirmed defects, 8 cleared as true, 0 left uncertain.
- Repo state at audit: branch `ravidsrk/new-research` at `1460f47`.

This doc is the workflow audit. It is separate from, and not an input to, any `/orchestration`
fresh-run review (which writes `docs/adversarial-review-fresh.md`). Keep both; do not merge them.

## Part 1: adversarial code and contract review (17 confirmed)

```
#   Sev  Area         Finding                                                          Location
1   P0   security     RCE: mission/campaign value interpolated into python -c          run-campaign.sh:145; run-mission-headless.sh:95-96
2   P1   code         [[ -d .git ]] guard rejects git worktrees/submodules             run-campaign.sh:97; run-mission-headless.sh:81
3   P1   runtime      claude branch uses nonexistent --cwd; drops --max-turns          run-mission-headless.sh:117
4   P1   runtime      codex branch never runs non-interactively (needs codex exec)     run-mission-headless.sh:119-127
5   P2   code         eval_edge TypeError on string/float metric vs numeric op         fleet_outcome.py:108-128
6   P2   contract     validate_outcome does no type/enum checks; typo mission = skip   fleet_outcome.py:57-79
7   P2   code         status fast-path skips quote-strip; missing metric == and != F   fleet_outcome.py:96-127
8   P2   code         validate-all aborts on missing skill-creator; venv pkg race      validate-all.sh; validate-skills.sh
9   P2   code         goal-condition ledger parser swallows unknown keys, false OK     validate-goal-condition.sh:84-90
10  P2   code         validate_fleet_outcome double-validates arch-build doc           validate_fleet_outcome.py:24-27
11  P2   security     --yolo auto-approve default, no trust/threat-model docs           run-mission-headless.sh:20; run-campaign.sh:20
12  P3   code         VISITED tracked but never consulted; only STEP>20 cycle backstop run-campaign.sh:135,186
13  P3   code         --dry-run depth is data-dependent on pre-existing readiness files run-campaign.sh:151-184
14  P3   code         missing 'start'/'mission' YAML dumps raw Python KeyError trace    run-campaign.sh:108-116
15  P3   code         split_frontmatter fails on leading blank line / BOM               fleet_outcome.py:32-40
16  P3   code         deferred_missions regex truncates ids; ignores bare-string items  fleet_outcome.py:100-106
17  P3   ci           venv pip installs pyyaml/pytest unpinned, no hashes, 5 sites      run-campaign.sh:105 + 4 more
```

### 1. P0 RCE via mission/campaign value interpolated into `python -c`

Both drivers build Python one-liners by raw string-interpolation into a single-quoted literal, for
example `print(readiness_path('$MISSION'))` at `run-campaign.sh:145` and the analogous
`progress_path`/`readiness_path` at `run-mission-headless.sh:95-96`. The mission comes from
campaign-YAML node values (`yaml.safe_load` preserves quotes; the `awk -F'\t'` parse at
`run-campaign.sh:122` only splits on tab, so a one-line payload survives). A single quote closes the
literal and the rest executes as Python on the operator host.

Reproduced live: the unmodified `./scripts/run-campaign.sh grok --campaign /tmp/.../evil.yaml --repo
/tmp/... --dry-run` with a node mission of
`x'));__import__('os').system('echo PWNED > proof.txt');print(('` wrote `proof.txt`. The vulnerable
line fires before the dry-run guard, so even `--dry-run` executes injected code with no agent
involved. `--campaign PATH` and the headless mission arg are documented primary inputs (README:70
points at externally-sourced `docs/external-dogfood/*.yaml` run against a third-party `--repo`), so
the kill chain is: receive or clone a campaign YAML, run the driver, get RCE.

Fix: stop generating Python source by interpolation. Pass mission and ROOT as argv
(`python -c '... print(readiness_path(sys.argv[2]))' "$ROOT" "$MISSION"`) or add a
`python -m lib.mission_registry readiness <mission>` subcommand, and validate `$MISSION` against the
known `MISSION_DOCS` keyset before use. Same fix at `run-mission-headless.sh:95-96`. Then make
`--yolo` opt-in (see finding 11).

### 2. P1 `.git` guard rejects worktrees and submodules

Both drivers gate on `[[ ! -d "$REPO_ROOT/.git" ]]`. In a worktree or submodule, `.git` is a file,
not a directory, so the guard wrongly aborts with "is not a git repository". This checkout is a
worktree, so the README step-3 quick-start fails out of the box. Fix: replace with
`! git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1`.

### 3. P1 claude branch uses nonexistent `--cwd`, drops `--max-turns`

`run-mission-headless.sh:117` runs `claude -p "$PROMPT" --cwd "$REPO_ROOT"`. `--cwd` is not a Claude
Code flag (reproduced: `error: unknown option '--cwd'`); Claude Code uses `--add-dir`, and has no
`--max-turns`, so the documented turn budget is silently dropped for claude while grok honors it.
Note: the `/goal` content in the prompt is valid (see Part 2 verified-true RD-1); only the `--cwd`
flag and the missing turn-budget mapping are wrong. Fix: drop `--cwd`, `cd` first or use `--add-dir`;
remove or remap the `--max-turns` claim for claude.

### 4. P1 codex branch never runs non-interactively

`run-mission-headless.sh:122` runs `codex -p "$PROMPT" 2>/dev/null || codex "$PROMPT"`. Top-level
`-p` maps to `--profile`, and both forms are interactive. On the non-TTY the script targets, both
fail with `stdin is not a terminal`; `2>/dev/null` hides it and `set -euo pipefail` then aborts. The
real non-interactive entrypoint, `codex exec`, appears nowhere. Fix: `codex exec "$PROMPT"` (with
`--cd "$REPO_ROOT"` if needed).

### 5. P2 `eval_edge` TypeError on string/float metric vs numeric operator

`fleet_outcome.py` coerces only the right side to int (and only when `raw.isdigit()`); the left side
is the raw YAML value. A string or float metric compared with `>`/`<`/`>=`/`<=` raises an uncaught
`TypeError` that aborts the driver under `set -euo pipefail`. Reproduced:
`eval_edge('coverage > 79.5', {'metrics': {'coverage': 79.5}})` raises. Bools do not crash but
compare as 0/1, silently wrong. Reachable from the shipped `composition-e2e-campaign.yaml` edge
`code_bug_findings > 0` if a doc emits that metric as a quoted string. Fix: coerce defensively for
ordering operators (try `float()` both sides, return False or a structured error on TypeError) or
validate metric types up front.

### 6. P2 `validate_outcome` does no type or enum validation

`validate_outcome` checks key presence only. `status: banana`, `prs_merged: not-a-number`, and
string-valued metrics all pass and print OK. A misspelled mission (`doc-snyc`) skips the entire
metric-presence block silently because validation is gated on `mission in MISSION_METRICS`. The docs
present this validator as the completion gate, so it gives false confidence against its own contract.
Fix: add type/enum checks (`prs_merged` int, `status` in {done,partial,blocked}, metric values
numeric/bool) and warn when a non-empty mission is not in `MISSION_METRICS`.

### 7. P2 `eval_edge` status fast-path and missing-metric semantics

Three inconsistencies in one function. The `status ==` fast-path does not strip quotes, so
`status == "done"` returns False even when status is done. Only `status ==` hits the fast-path; other
operators fall through to `_metric_value`, so a metric named `status` shadows the top-level field. A
missing metric returns False for both `==` and `!=` (a logically impossible pair, fail-closed with no
signal). Fix: route all status comparisons through the generic dispatch with quote-stripping; raise
or warn when an edge references a metric absent from both sources.

### 8. P2 validate-all aborts on missing skill-creator; venv package race

`validate-all.sh` runs `validate-skills.sh` first, which hard-exits when the gitignored
`.agents/skills/skill-creator/scripts/quick_validate.py` is absent, so a fresh checkout never reaches
fleet-outcome/goal/pytest validation. Separately, every venv bootstrap guards on the binary not the
packages, and `validate-skills.sh` installs pyyaml only, so a later pytest step can crash with "No
module named pytest". CI masks both by pre-building the venv and installing skill-creator first. Fix:
make the skill-creator check a soft skip; make bootstraps verify imports
(`python -c 'import yaml, pytest'`); install pytest in validate-skills too; reuse one bootstrap helper.

### 9. P2 goal-condition ledger parser swallows unknown keys

`validate-goal-condition.sh:84-90` terminates capture only on a hardcoded key allow-list
(SCOPE/HOST/SET_AT/LAST_UPDATE/CONDITION) and only when `line.endswith(':') is False`. Any other
unindented `KEY: value` after CONDITION is appended into the extracted condition, and a colon-
terminated bare key is never treated as a terminator. A swallowed line containing a `docs/...` token
can inject the `docs/` reference `check_condition` requires, flipping a should-FAIL lint to a false
OK. Fix: terminate on any unindented line matching `^[A-Z_]+:`.

### 10. P2 `validate_fleet_outcome.py` double-validates arch-build doc

With no files passed, the CLI globs `docs/*-readiness.md` then unconditionally appends
`docs/arch-build-readiness.md` if it exists, but the glob already matches it, so the file is
validated and printed twice and an invalid doc reports "2 readiness doc(s) failed" for one file.
Latent until mission adversarial-review-and-fix runs. Fix: drop the append, or
`paths = sorted(set(paths))`.

### 11. P2 `--yolo` auto-approve default with no trust language

Both drivers default `YOLO=1`, so grok is invoked with `--yolo`, auto-approving every tool call
unattended; the agent cwd is an operator-supplied `--repo`. README has zero security/trust/sandbox
language. Compounds the P0: no second line of defense. Fix: make auto-approve opt-in (or warn loudly
when active) and document the threat model (untrusted `--repo`/`--campaign` + auto-approve = full RCE
surface).

### 12-17. P3 robustness and hygiene

- 12: `VISITED` accumulates node ids but is never consulted; only `STEP>20` catches cycles, so a
  self-loop campaign dispatches up to ~20 real mission runs first. Fix: check membership before
  dispatch.
- 13: `--dry-run` only advances when the current node's readiness file already exists in the target,
  so a clean repo shows only one node; the printed "plan" is data-dependent. Fix: traverse edges
  statically for dry-run, or document the behavior.
- 14: a campaign YAML missing `start` (or a node missing `mission`) dumps a raw Python KeyError
  traceback. Fix: validate required keys in the heredoc and emit a friendly error.
- 15: `split_frontmatter` requires `text.startswith('---')`, so a leading blank line or BOM yields
  "missing YAML frontmatter". Fix: normalize line endings and lstrip before the check.
- 16: `deferred_missions contains` captures the target with `([\w-]+)`, truncating dotted/slashed
  ids, and only matches dict items with `id`, ignoring bare-string items. Fix: match to end-of-string
  and accept both item shapes.
- 17: every venv bootstrap runs `pip install pyyaml pytest` unpinned, no `--require-hashes`, no
  lockfile, across 5 sites plus CI. Fix: pinned `requirements.txt` with hashes.

## Part 2: adversarial research, claims and evidence (12 confirmed)

Headline: the empirical backbone of the "safe to run unattended" tier system is real-paper,
wrong-numbers. The citation is genuine (MSR 2026, arXiv 2601.15195, the AIDev dataset of 33,596
agent-authored PRs), but every merge-rate figure in the repo is OpenAI Codex's single best-agent
column relabeled as the dataset-wide rate "across 33k real agent PRs". The true cross-agent rates are
materially lower, and that gap is the difference between "safe unattended" and "needs review".

```
ID        Sev  Status       Finding                                                            Location
PROV-01   P1   FALSE        0.92 doc-sync = Codex single-agent; real cross-agent docs = 84%    doc-sync/SKILL.md:4,64; README:179
PROV-02   P1   FALSE        Tier-1 band 0.84-0.92 overstates; real test rate 61.5% not ~0.84   engine.md:263; missions.md:6
PROV-06   P1   FALSE        All per-skill rates are Codex's column; UI/migration cats invented test-coverage/SKILL.md:56 +4
PROV-04   P1   FALSE        Perf "~0.68" is Codex's; real cross-agent = 55%                    engine.md:268
GEM-001   P1   FALSE        Only "evidence" admits headless failed, run by hand interactively  ship-with-proof-evidence.md:36
GEM-002   P1   FALSE        "22 + 4 runs" not real minitest; cited cmd runs 4 of the tests     ship-with-proof-evidence.md:31
RD-2      P1   UNSUPPORTED  3 research docs cite gemoji "Done/Shipped"; was interactive, fork   research-community-skills.md:183 +2
F1        P1   FALSE        gstack-* gate ids 404 upstream; default install unprefixed=no-op   campaigns.md:123-179
PROV-09   P1   UNSUPPORTED  Orca "(most battle-tested)" superlative, zero per-adapter evidence  missions.md:36
RD-3      P2   UNSUPPORTED  DECISIONS C-01 "proven in dogfood" = one green run, not proven      research-skill-composition.md:350
GEM-003   P3   UNSUPPORTED  "not pushed upstream" hides the public fork ravidsrk/gemoji         ship-with-proof-evidence.md:7
PROV-08   P3   FALSE        gemoji "~2k LOC" wrong: lib 273 lines, all Ruby 779                repo-health-campaign.yaml:2
```

### The merge-rate misattribution (PROV-01, 02, 04, 06)

One root cause. The paper reports a cross-agent aggregate per task type and a per-agent breakdown.
The repo quotes the per-agent Codex row everywhere and attaches the dataset's "33k PRs" provenance to
it. The per-task decimals actually come from a different, smaller paper (Pinna et al., arXiv
2602.08915, 7,156 PRs), so the "33k" provenance on the per-skill numbers is misattributed regardless.
`design-integration`, `landing-page-convergence`, and `targeted-migration` carry `~0.80-0.81` rates
for "UI", "frontend", and "migration" task categories that do not exist in either source.

```
Skill / claim          Repo says    Real cross-agent source      Note
doc-sync               ~0.92        documentation 84%            Codex-only 0.92 vs Copilot 0.61
test-coverage          ~0.84        test 61.5%                   Codex-only 0.84; range 0.37-0.84
dependency-update      ~0.84-0.87   chore 84% / build 74%        0.87 exceeds every aggregate
performance (excluded) ~0.68        performance 55%              Codex-only 0.68; others 0.27-0.46
```

Worst operational case: `test-coverage` is sold as Tier-1 autonomous-safe at ~0.84 while the real
aggregate test-PR merge rate is 61.5%, so the operator is told a 38.5% not-merged rate is safe to
leave unattended. Fix: replace per-task decimals with the real cross-agent aggregates (docs 84%,
build 74%, test ~61.5%, perf 55%), widen the Tier-1 band downward, drop the invented categories, and
cite arXiv 2601.15195 directly. Or keep only the qualitative tier ordering and stop printing decimals
in user-facing descriptions.

### The operational proof is hollow (GEM-001, GEM-002, RD-2)

The repo headlines "fully-autonomous" with `run-mission-headless.sh` as the unattended driver, but
the only "completed evidence" doc states verbatim that headless grok failed with
`Auth(AuthorizationRequired)` and the run "completed interactively in Cursor Grok". The verifier
independently confirmed the auth-failure mechanism is real (grok OAuth login breaks headless without
`XAI_API_KEY`), so the headless path genuinely did not run. The test-pass line "22 + 4 runs, 0
failures" is not minitest output (minitest emits one aggregate line; the real figure is "26 runs, 57
assertions"), and the cited command `ruby -Ilib:test test/*_test.rb` runs only 4 of the tests
because Ruby treats the first glob match as the script and the rest as ARGV. Three research docs then
cite this run as "Done"/"Shipped" proof the campaign machinery works end to end. Fix: re-label as a
partial interactive smoke test (headless not yet validated) across all three research docs,
`README.md:10`, and `repo-health-gemoji.md:1`; correct the test line to "26 runs, 57 assertions";
qualify "fully-autonomous" in `README.md:3` until a real authenticated headless run produces the
artifacts end to end.

### The gates silently no-op (F1)

Campaigns invoke gate skills as `gstack-ship`, `gstack-qa`, `gstack-health`, etc. Authenticated
`gh api` against `garrytan/gstack` returns 404 for every `gstack-*` path and 200 for the unprefixed
`ship`, `qa`, `health`. The default `./setup` installs unprefixed (the `gstack-` prefix is opt-in via
`--prefix`), so a user who follows the documented install gets ids that never match the campaign
gates: every post-gate and pre-gate silently no-ops, voiding the ship-with-proof and quality-gate
guarantees. `community-skills.md:130` also wrongly attributes the prefix to `./setup --host`. Fix:
switch to the real unprefixed ids, or instruct users to install with `--prefix`, and fix the
attribution.

### Lower-stakes (PROV-09, RD-3, GEM-003, PROV-08)

- PROV-09: drop `(most battle-tested)` from the Orca adapter or back it with a per-adapter run-count
  comparison (none exists; the one run used Grok, not Orca).
- RD-3: soften DECISIONS C-01 "proven in doc-sync dogfood" to "exercised (loads + validators pass)".
- GEM-003: "not pushed upstream" understates verifiability; the work is on the public fork
  `github.com/ravidsrk/gemoji`, branch `fleet/gemoji-ship-with-proof-base`, SHA 1541ce9. Add that
  durable pointer.
- PROV-08: gemoji "~2k LOC" is wrong; `lib/` is 273 lines, all Ruby 779, the 23k-line file is emoji
  JSON data. Re-measure or soften to "small gem".

### Verified true (cleared, not defects)

The research audit cleared 8 of 20 probes, which matters for trusting the 12 that stuck:

- The citation is legitimate. MSR 2026 and the ~33,596-PR AIDev dataset are real and correctly sized;
  the directional ranking (docs/CI/build best, performance/fix worst) matches. The defect is
  misquoted numbers, not an invented source.
- The bug-fix `~0.82` figure is a real source number (Codex fix-category rate), not fabricated.
- The gemoji code fixes (REL-001/002/003) are real and verifiable against upstream `github/gemoji`:
  the two-arg `assert`, the missing `delete_if` in `edit_emoji`, and the `test_helper` class all
  exist upstream.
- `"20 skills under skills/"` is accurate.
- Community-skill scale counts (gstack ~59, agent-skills 24+7, mattpocock ~25) check out against live
  data.
- The `/goal` claim is correct. `runtime-loops-and-goals.md` says `/goal` requires Claude Code
  v2.1.139+ and that `claude -p "/goal ..."` is the non-interactive form; both match Anthropic's live
  docs. This narrows finding 3 above to the `--cwd` flag only.
- The tier-1 token-cost estimate (~50-100 tokens/skill) brackets the agentskills.io spec figure.

## Combined fix order

1. P0 RCE: stop interpolating `$MISSION`/`$ROOT` into `python -c`; pass argv or add a registry
   subcommand; validate `$MISSION` against the keyset. Fires even in `--dry-run`.
2. Make `--yolo` opt-in (or warn) and add a threat-model section.
3. Relabel every merge-rate number to the real cross-agent aggregates; widen the Tier-1 band; drop
   invented categories; cite arXiv 2601.15195. One edit pattern across README, missions.md, engine.md,
   and five SKILL.md files.
4. Re-label the gemoji doc as a partial interactive smoke test; fix the test line; point at the public
   fork + SHA; qualify "fully-autonomous".
5. Fix the runtime adapters: worktree `.git` guard, claude `--cwd`, codex `codex exec`.
6. Switch campaign gate ids to the real unprefixed gstack names (or document `--prefix`); fix the
   `./setup --host` attribution.
7. Harden the engine: wrap `eval_edge` numeric ops, add type/enum/mission validation, fix status
   quote-strip and missing-metric semantics, decouple validate-all from skill-creator, fix the
   double-validate and ledger-parser bugs.
8. Drop or substantiate `(most battle-tested)`, soften "proven" to "exercised", re-measure `~2k LOC`.
