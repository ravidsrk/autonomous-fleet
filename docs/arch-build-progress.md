# arch-build-progress (adversarial-review-and-fix dogfood, 2026-06-21)

PHASE: DONE
MISSION: adversarial-review-and-fix   REPO: autonomous-fleet   BASE: ravidsrk/dogfood-adversarial (off main@f19a971)
REVIEW_DOC: docs/arch-build-review.md (frozen; 9 confirmed findings)
COORDINATOR: this Claude Code session

## TARGET
This week's NEW code (PRs #21-25): run-sandboxed.sh blast_radius classifier, coupling-graph.py,
render-dashboard.py, fleet_outcome.py new validators. Freshest code = most likely to carry real bugs.

## REVIEW (workflow: 4 finders reproduce by execution -> each finding 2 refuters -> confirmed only)
11 raised, 9 CONFIRMED (both refuters reproduced each). Frozen in docs/arch-build-review.md.
| severity | finding | file |
|----------|---------|------|
| P1 | command-prefix-bypasses-classifier | run-sandboxed.sh |
| P1 | bash-c-embedded-string-not-classified | run-sandboxed.sh |
| P1 | reset-hard-bare-remote-not-denied | run-sandboxed.sh |
| P1 | relative-imports-silently-dropped | coupling-graph.py |
| P2 | echo-commit-regex-false-positives | run-sandboxed.sh |
| P2 | yaml-error-crashes-whole-dashboard | render-dashboard.py |
| P2 | cost-estimate-accepts-nan-inf | fleet_outcome.py |
| P2 | mission-metrics-accept-nan-inf | fleet_outcome.py |
| P2 | eval-edge-nan-bypasses-routing-gate | fleet_outcome.py |

## PLAN / DAG GATE + COUPLING
4 fix units (one per file). run-sandboxed.sh (4 findings) and fleet_outcome.py (3) are HOT FILES ->
their findings serialize within-file. coupling-graph.py flagged fleet_outcome.py as the in_degree-4
hub. Width 4, no cycles. PASS.

## FIX + CROSS-VENDOR REVIEW (claude builds, codex reviews — the discipline that bit HARDEST here)
All 9 fixed. The codex adversarial review of the run-sandboxed.sh fix drove SEVEN rounds, each
finding a real FALSE NEGATIVE (a dangerous command reaching exec) the prior fix missed:
- R1: /bin/rm (no basename), env -u X rm / nice -n 5 git push / nohup sudo -u root rm (wrapper opts).
- R2: timeout/flock/doas/chrt/taskset wrappers; redirection in bash -c; data-consumer FP (env echo).
- R3: THE BIG ONE — `run-sandboxed.sh bash -c 'rm -rf /etc'` actually REACHED EXEC. classify joined
  $* then re-tokenized, destroying the -c quoting. My single-string tests had MASKED it (they did
  not invoke the way the real argv path does). Fixed: classify argv verbatim; tests now shlex.split.
- R4: bundled shell -c (bash -ec) + env -S/--split-string run their string arg as a command.
- R5: single `&` background operator not split in the string path.
- R6: positional-param construction `bash -c 'rm "$@"' _ -rf x` -> fail safe to ASK (unanalyzable).
- R7: backslash-newline line continuation split rm from -rf -> join continuations before splitting.
CONVERGED after R7: every statically-detectable evasion is closed. Residual class (command
substitution $(), eval, base64, non-sh interpreters) is provably out of reach for a token classifier;
documented in the header as fail-safe-where-detectable, with container-use's OS sandbox as the boundary.
reviewed_sha (final) = ad9c80b.

## DISCIPLINES
RESEARCH (finders reproduce, not hypothesize) · PLAN/DAG gate · COUPLING (hub identified) ·
CROSS-VENDOR adversarial review (7 rounds, found a real RCE-class FN) · SHA-PIN re-review each round ·
SIGNAL RECONCILIATION (real-exec-path proof: victim dir survives) · SAFETY classifier (the subject) ·
DASHBOARD.
