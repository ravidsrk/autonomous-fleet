# Adversarial review — this week's new code (FROZEN, 2026-06-21)

Fresh adversarial review of code shipped in PRs #21-25. 11 raised, 9 confirmed (each reproduced by 2 independent refuters). Refuted/unconfirmed dropped.

## coupling-graph.py
### [P1] relative-imports-silently-dropped  (coupling-graph.py:96-112)
_py_imports() only records imports when node.level == 0. For ast.ImportFrom nodes with level > 0 (every relative import: `from . import x`, `from .mod import y`, `from ..pkg import z`), the elif branch at line 110 still requires node.level == 0, so the relative case falls through and nothing is recorded. Relative imports are the dominant way packages reference their own modules, so intra-repo coupling is massively under-detected. This directly defeats the tool's stated purpose (docstring: cluster tightly-coupled files into ONE task, mark hub files serialize-always): two files that are tightly 
REPRO:
```
Created /tmp/cg_final with app/__init__.py, app/utils.py (z=1), and app/main.py containing `from . import utils` and `from .utils import thing`.

Command:
/Users/ravindra/orca/workspaces/autonomous-fleet/new-research/.venv/bin/python /Users/ravindra/orca/workspaces/autonomous-fleet/new-research/scripts/coupling-graph.py /tmp/cg_final --json

Observed: edges = []  clusters = [] 
```
FIX: Handle node.level > 0 in _py_imports by reconstructing the absolute dotted name from the importer's package path, then resolve via the existing py_index. Compute the importer's containing package parts: rel = path.relative_to(root); parts = rel.with_suffix('').parts; if last part is '__init__' the package is parts[:-1] else parts[:-1]. For a relative ImportFrom, drop (level-1) trailing components 

## fleet_outcome.py
### [P2] cost-estimate-accepts-nan-inf  (fleet_outcome.py:131-136)
validate_outcome guards cost_estimate with `isinstance(cval, bool) or not isinstance(cval, (int, float)) or cval < 0`. NaN fails all three checks because every NaN comparison is False (`nan < 0` is False), and `inf < 0` is also False. So `cost_estimate: .nan` and `cost_estimate: .inf` both validate clean. pyyaml.safe_load parses YAML 1.1 floats `.nan`/`.inf` into Python nan/inf, so this is reachable through ordinary readiness-doc frontmatter, not just direct Python calls. A NaN/inf cost telemetry value then poisons cost-routing/budget logic and renders as literal 'nan' in the dashboard cost co
REPRO:
```
$ cat > /tmp/test-readiness.md <<'EOF'
---
fleet-outcome:
  mission: cleanup
  status: done
  repo: testrepo
  base_branch: main
  prs_merged: 1
  cost_estimate: .nan
  metrics:
    cleanup_items_open: 0
---
EOF
$ .venv/bin/python scripts/validate_fleet_outcome.py /tmp/test-readiness.md; echo EXIT=$?
OK   test-readiness.md mission=cleanup
All readiness docs passed fleet-outcome
```
FIX: Add a finiteness check. `import math` and change the guard at line 133 to: `if isinstance(cval, bool) or not isinstance(cval, (int, float)) or not math.isfinite(cval) or cval < 0:`. Verified: this accepts 1.5/0, rejects nan/inf/-inf/-1/True/'5'.

### [P2] mission-metrics-accept-nan-inf  (fleet_outcome.py:108-113)
The per-mission metrics loop only checks `isinstance(mval, (int, float, bool))`. A metric set to NaN or inf passes validation. These metrics are exactly the values that campaign routing edges gate on (e.g. doc-sync's `drift_open`, `code_bug_findings`). A NaN metric validates, then silently bypasses every ordering gate in eval_edge (see related finding), with no error anywhere.
REPRO:
```
$ .venv/bin/python -c "import sys;sys.path.insert(0,'scripts');from lib.fleet_outcome import validate_outcome,eval_edge;o={'mission':'doc-sync','status':'done','repo':'x','base_branch':'main','prs_merged':1,'metrics':{'drift_open':float('nan'),'code_bug_findings':float('inf')}};print('errors=',validate_outcome(o));print('drift_open>0(nan)=',eval_edge('drift_open > 0',o));print(
```
FIX: In the metric-value loop, reject non-finite floats: `import math` then `if isinstance(mval, bool): pass elif isinstance(mval, (int, float)) and not (isinstance(mval, float) and not math.isfinite(mval)): pass else: errors.append(...)`. Simpler: keep the isinstance check but add `or (isinstance(mval, float) and not math.isfinite(mval))` to the failure branch. Verified accepts 0/3/1.5/True, rejects n

### [P2] eval-edge-nan-bypasses-routing-gate  (fleet_outcome.py:162-211)
_coerce_for_ordering does `float(value)` and never checks finiteness. When a metric is NaN, every ordering comparison (>, <, >=, <=) returns False per IEEE-754, so a budget/remediation gate like `ops_queue_count > 0` or `code_bug_findings > 0` evaluates False and pick_next_node skips that node, falling through to the next edge (often `always` -> done). The campaign routes as if the count were zero, with no exception raised. Real campaigns use these exact gates: handoff-to-product.yaml has `ops_queue_count > 0`, `majors_deferred > 0`, `code_bug_findings > 0`. Because validate_outcome also accep
REPRO:
```
$ .venv/bin/python -c "import sys;sys.path.insert(0,'scripts');from lib.fleet_outcome import pick_next_node;c={'edges':{'start':[{'to':'deps','if':'ops_queue_count > 0'},{'to':'done','if':'always'}]}};print('NaN ->',pick_next_node(c,'start',{'metrics':{'ops_queue_count':float('nan')}}));print('5   ->',pick_next_node(c,'start',{'metrics':{'ops_queue_count':5}}))"
NaN -> done
5  
```
FIX: In _coerce_for_ordering.to_float, after converting, raise on non-finite: `r = float(value); if not math.isfinite(r): raise ValueError('non-finite operand'); return r`. The eval_edge ordering branch already catches ValueError/TypeError and re-raises a clear 'cannot compare metric values numerically' error, so non-finite metrics would surface as an explicit failure instead of silently bypassing the 

## render-dashboard.py
### [P2] yaml-error-not-caught-crashes-whole-dashboard  (render-dashboard.py:153-159)
build_model() loops over docs/*-readiness.md and wraps parse_readiness(path) in `try: ... except ValueError: continue`. parse_readiness calls yaml.safe_load, which on malformed YAML raises yaml.YAMLError (e.g. yaml.parser.ParserError / yaml.scanner.ScannerError). yaml.YAMLError is NOT a subclass of ValueError (verified: issubclass(yaml.YAMLError, ValueError) -> False), so it propagates out of build_model and aborts main() with a full traceback. The intent of the except is clearly to skip a bad readiness doc and keep rendering (it already does this for the ValueError paths inside parse_readines
REPRO:
```
TMP=$(mktemp -d); mkdir -p "$TMP/docs"; printf -- '---\nfleet-outcome:\n  mission: doc-sync\n\tstatus: done\n---\nbody\n' > "$TMP/docs/tab-readiness.md"; printf 'TASK realwork | CODED=t PR_OPEN=t | NOTE=in flight\n' > "$TMP/docs/good-progress.md"; /Users/ravindra/orca/workspaces/autonomous-fleet/new-research/.venv/bin/python /Users/ravindra/orca/workspaces/autonomous-fleet/new-
```
FIX: Broaden the except in build_model from `except ValueError:` to `except (ValueError, yaml.YAMLError):` and add `import yaml` to render-dashboard.py (parse_readiness already depends on pyyaml, so it is a free import). This matches the existing intent of skipping unparseable readiness docs. Verified: with that change the tab-indent / unbalanced-sequence repro renders successfully and includes the val

## run-sandboxed.sh
### [P1] command-prefix-bypasses-classifier  (run-sandboxed.sh:174-224)
_classify_statement_tokens only unwraps two leading forms: shell env assignments (NAME=val) and a single leading `sudo`. It does NOT skip the many other no-op/wrapper prefixes a caller can put in front of a binary. `cmd=${argv[$i]}` therefore resolves to the prefix word (e.g. `command`, `exec`, `env`, `xargs`) instead of the real binary, so the rm/git-push token scanners and the whole DENY path are skipped. The regex tiers in classify() (gh/reset/infra) are anchored to literal `git `/`gh `/`rm `... at a statement boundary and also do not see past the prefix. Result: every catastrophic command 
REPRO:
```
$ ./scripts/run-sandboxed.sh --classify 'command rm -rf /etc'
ALLOW   (expected DENY)
$ ./scripts/run-sandboxed.sh --classify 'command git push --force'
ALLOW   (expected DENY)
$ ./scripts/run-sandboxed.sh --classify 'exec git push --force'
ALLOW   (expected DENY)
$ ./scripts/run-sandboxed.sh --classify 'env git push --force'
ALLOW   (expected DENY)
$ ./scripts/run-sandboxed.sh
```
FIX: After unwrapping env-assignments and sudo, loop to strip a known set of transparent command prefixes before reading the command word. Treat `command`, `builtin`, `exec`, `eval`, `nohup`, `nice`, `time`, `ionice`, `stdbuf`, `setsid`, `xargs`, and `env` (skipping env's NAME=val args and its own options) as wrappers and advance the index past them (recursively, since `sudo command env rm` stacks). Fo

### [P1] bash-c-embedded-string-not-classified  (run-sandboxed.sh:90-97, 134-141)
The file header (lines 90-97) explicitly claims the classifier treats an embedded command string `bash -c "cd repo && rm -rf /etc"` the same as split argv. It does not. classify() splits statements on ; && || | over the joined line ignoring quoting, then the per-statement classifier sees `bash`/`sh` as the command word and never inspects the -c string. So `bash -c "rm -rf /etc"` (no inner separator) is ALLOW. Worse, even when an inner `&&` exists, the unquoted split chops the string mid-quote so the resulting rm target carries a trailing double-quote (`/etc"`), which _rm_target_is_catastrophic
REPRO:
```
$ ./scripts/run-sandboxed.sh --classify 'bash -c "rm -rf /etc"'
ALLOW   (expected DENY)
$ ./scripts/run-sandboxed.sh --classify 'sh -c "rm -rf /"'
ALLOW   (expected DENY)
$ ./scripts/run-sandboxed.sh --classify 'bash -c "cd repo && rm -rf /etc"'
ASK     (header at lines 91-95 claims this is treated like split argv -> should be DENY)
# root cause: trailing quote left on target
$
```
FIX: Either (a) recursively re-classify the argument following `-c` for sh/bash/zsh/dash (and `python -c`, `perl -e` are out of scope but bash/sh are the documented case), or (b) strip surrounding quotes from tokens before the catastrophic-target check and normalize trailing quote chars in _rm_target_is_catastrophic. At minimum, correct the header comment so it does not overstate coverage. Note this in

### [P1] reset-hard-bare-remote-not-denied  (run-sandboxed.sh:304)
_regex_deny matches `reset --hard <ref>` only when the ref contains a slash (pattern ends in `[A-Za-z0-9_./-]+/`). So `git reset --hard origin/main` is DENY but `git reset --hard origin`, `git reset --hard @{upstream}`, and `git reset --hard @{u}` are ALLOW even though they hard-reset the working tree to a remote-tracking ref and irreversibly discard local commits/changes — exactly the case the DENY tier is meant to catch. `git reset --hard refs/remotes/origin/main` happens to be caught only incidentally (it has slashes).
REPRO:
```
$ ./scripts/run-sandboxed.sh --classify 'git reset --hard origin'
ALLOW   (expected DENY/ASK)
$ ./scripts/run-sandboxed.sh --classify 'git reset --hard @{upstream}'
ALLOW   (expected DENY/ASK)
$ ./scripts/run-sandboxed.sh --classify 'git reset --hard origin/main'
DENY    (caught only because of the slash)
```
FIX: Classify `git reset --hard` structurally in _classify_statement_tokens (alongside push) rather than by regex: any `git ... reset --hard <ref>` where ref is not HEAD/HEAD~N/a short SHA/a clearly-local ref is at least ASK, and a remote-tracking ref (matches a configured remote name, or `@{u}`/`@{upstream}`, or `refs/remotes/...`) is DENY. If keeping the regex, drop the mandatory trailing `/` and ins

### [P2] echo-commit-regex-false-positives  (run-sandboxed.sh:308-315)
_regex_ask scans the whole joined line for `(kubectl|helm|terraform|tofu|databricks) ... (apply|deploy|destroy|delete)` with no awareness of quoting or the leading command. So a harmless command that prints or commits text containing those words is refused with ASK (exit 3), blocking legitimate work non-interactively. `echo terraform apply`, `echo "remember to run terraform apply"`, and `git commit -m "fix terraform apply bug"` all classify ASK. These are false positives — the wrapper refuses to run them, and being non-interactive it cannot be overridden in place.
REPRO:
```
$ ./scripts/run-sandboxed.sh --classify 'echo terraform apply'
ASK     (expected ALLOW)
$ ./scripts/run-sandboxed.sh --classify 'git commit -m "fix terraform apply bug"'
ASK     (expected ALLOW)
$ ./scripts/run-sandboxed.sh --classify 'echo "remember to run terraform apply"'
ALLOW   (only ALLOW because quotes happen to break the adjacency the regex needs)
```
FIX: Run the infra-tool check per tokenized statement after the same env/sudo/prefix unwrapping used for rm/git, requiring the infra tool to be the resolved command word (argv[0]) rather than matching anywhere on the joined line. That removes the echo/commit/grep false positives while still catching a real `terraform apply` as the leading command.
