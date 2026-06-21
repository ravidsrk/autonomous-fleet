---
fleet-outcome:
  mission: adversarial-review-and-fix
  status: done
  repo: ravidsrk/autonomous-fleet
  base_branch: ravidsrk/dogfood-adversarial
  prs_merged: 0
  metrics:
    p0_open: 0
    p1_open: 0
    findings_open: 0
    ops_queue_count: 0
  deferred_missions: []
  unverified_assumptions: 0
  sources_logged: 0
  cost_estimate: 1.4
  run:
    duration_min: 40
    note: dogfood; cross-vendor review drove 7 hardening rounds on the safety classifier
---

# arch-build-readiness (adversarial-review-and-fix dogfood, 2026-06-21)

Fresh adversarial review + fix of THIS week's new code (PRs #21-25), run to dogfood the disciplines.
9 confirmed findings, all closed; `findings_open: 0`, `p0_open: 0`, `p1_open: 0`, `ops_queue_count: 0`.

## Findings closed
- run-sandboxed.sh (4): command-prefix bypass, bash -c not classified, reset --hard bare-remote,
  echo/infra/gh substring false-positives. Plus 7 cross-vendor-review rounds of additional false
  negatives (see below).
- coupling-graph.py (1): relative imports silently dropped -> reconstructed.
- render-dashboard.py (1): malformed YAML crashed the whole render -> caught + skipped.
- fleet_outcome.py (3): NaN/inf accepted in cost_estimate + metrics, and bypassed eval_edge ordering
  gates -> finiteness checks; eval_edge raises on non-finite.

## What the dogfood proved (and the honest limit)
The cross-vendor adversarial review was the discipline that mattered. Reviewing the run-sandboxed.sh
classifier, codex found a real RCE-class FALSE NEGATIVE in round 3: `run-sandboxed.sh bash -c
'rm -rf /etc'` actually reached exec, because classify() joined `$*` and re-tokenized, destroying the
`-c` quoting. My own regression tests had MASKED it by invoking `--classify "single string"` instead
of the separate-argv form the wrapper actually receives. A same-vendor review would likely have
shared that blind spot. The fix: classify the real argv verbatim, and tests now `shlex.split` (the
real path).

Seven rounds total, each closing a genuine false negative (basename/`/bin/rm`, operand-consuming
wrapper options, command-runner wrappers timeout/flock/doas, redirection, `&` background op, bundled
`bash -ec`, `env -S`, positional-param `rm "$@"` construction, line continuation). Each fix is locked
by a real-exec-path test that proves the `rm` does NOT run (the victim dir survives).

HONEST LIMIT (documented in the script header): a static token classifier CANNOT soundly parse bash.
The residual evasion class — command substitution `$()`, `eval` of a built string, base64, non-sh
interpreters — is out of reach by construction. Where detectable (a `-c` string referencing `$@`/`$1`)
the classifier FAILS SAFE to ASK; otherwise a determined caller can evade it. This is exactly why the
orchestration-landscape research put container-use (an OS-level container) as the real sandbox
boundary: this script is the cheap mechanical net, not the boundary.

## Verification
- pytest 175 passed (61 in the new adversarial-fix regression suite, incl. real-exec-path tests).
- validate-all green.
- Real-exec proof: bash -c / env -S / command / `&` / line-continuation / positional-param forms all
  REFUSED before exec; the /tmp victim dirs survived every time.

## OPS / human boundary
None. All fixes are code-only, verified on local fixtures + harmless /tmp targets. No secrets, no
deploy, no real-target destructive op was ever run.
