---
title: "Troubleshooting"
description: "A bestiary of known autonomous-fleet failure modes with exact error signatures and exact fixes."
sidebar:
  order: 14
---

# Troubleshooting

Your run just failed. This chapter is the bestiary: known failure modes, the **exact** error
signature each one prints, what is actually wrong, how to fix it, and how to stop it recurring.
It is organised by the layer where the failure surfaces, roughly the order a run hits them:

```
install / auth ─► runtime spawn ─► ledger + locks ─► verification ─► PR open ─► archive ─► gates
```

If your error is not here, it is probably an engineering bug, not an operator mistake. Those go to
[a GitHub issue](#when-to-file-an-issue), not this page.

> Every signature below is quoted from the scripts and libraries on `main`. If the text you see
> differs, you are on a different version. Run `git -C <fleet-clone> rev-parse HEAD` and compare.

**On this page:** [How to read an entry](#how-to-read-an-entry) ·
[Install and auth](#install-and-auth) · [Runtime spawn](#runtime-spawn) ·
[Ledger and locks](#ledger-and-locks) · [Verification failures](#verification-failures) ·
[PR-open failures](#pr-open-failures) · [Archive validation](#archive-validation) ·
[Mutation gate](#mutation-gate) · [CI and the full gate](#ci-and-the-full-gate) ·
[Two honest caveats](#two-honest-caveats) · [When to file an issue](#when-to-file-an-issue)

## How to read an entry

Every entry has the same four-part shape so you can scan to the part you need:

```
What you see   the literal stderr / stdout line, copy-pasteable to grep against
What's wrong   the root cause, in one or two sentences
How to fix     the exact command or edit
How to prevent the habit or check that stops it coming back
```

The signatures are grouped by category. Use your browser's find (`/` on GitHub) for the exact
string from your terminal. Most of them are unique enough to land on one entry.

## Install and auth

The fleet is a set of skills installed by the `npx skills` CLI plus a Python venv that the shell
scripts bootstrap on demand. Both can be missing or stale.

### `error: skill-creator validator not found`

What you see:

```
error: skill-creator validator not found at <clone>/.agents/skills/skill-creator/scripts/quick_validate.py
  Install: npx skills add https://github.com/anthropics/skills --skill skill-creator -y -p
  Or set VALIDATE_SKILLS_OPTIONAL=1 to skip skill validation.
```

What's wrong: `validate-skills.sh` validates every skill against the agentskills.io spec using
skill-creator's `quick_validate.py`. That validator is a separate skill and is not installed.

How to fix: run the install line the error already gave you:

```bash
npx skills add https://github.com/anthropics/skills --skill skill-creator -y -p
```

Or, if you only want to skip skill validation for this run (CI on a machine that will never author
a skill, say), set the documented escape hatch:

```bash
VALIDATE_SKILLS_OPTIONAL=1 ./scripts/validate-skills.sh
```

That prints a `WARN ... skipping skill validation` line and exits 0 instead of 1.

How to prevent: install skill-creator as part of your dev-machine setup, alongside the fleet
skills. It is the only validator dependency that is not vendored in `scripts/lib/`.

### `ModuleNotFoundError: No module named 'yaml'` (or `pytest`)

What you see: a raw Python traceback ending in `ModuleNotFoundError`, usually when you invoke a
`scripts/*.py` file directly with the system Python instead of going through a wrapper script.

What's wrong: the fleet pins its Python deps in `requirements.txt`:

```
pyyaml==6.0.2
pytest==8.3.4
coverage>=7.0
```

The wrapper scripts source `scripts/lib/venv-bootstrap.sh`, which creates `.venv/`, then
**re-checks** `import yaml, pytest, coverage` and reinstalls from `requirements.txt` if any are missing.
A stale venv (the binary exists but `pyyaml` was never installed) self-heals through that path. You
hit the traceback when you bypass it and call `python3 scripts/foo.py` yourself.

How to fix: run through the wrapper, or set up the venv the same way the bootstrap does:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/validate_run_archive.py
```

Every fleet `*.sh` entrypoint exports `VENV_PYTHON` after bootstrap, so prefer
`"$VENV_PYTHON" scripts/foo.py` over a bare `python3` in your own scripts.

How to prevent: never call the Python validators with the system interpreter. Use the `*.sh`
wrappers (`validate-all.sh` and friends) or the exported `$VENV_PYTHON`.

### Headless runtime CLI is not authenticated

What you see: nothing from the fleet itself. The runtime CLI errors out, for example Grok printing
an auth prompt, or `claude -p` returning a login error, when `run-mission-headless.sh` shells out
to it.

What's wrong: headless mode drives the runtime's own CLI (`grok -p`, `claude -p`, `codex exec`).
Each must already be authenticated on the host. The fleet does not manage their credentials.

How to fix: authenticate the CLI you are targeting before you run headless, then retry. See the
[headless caveat](#two-honest-caveats) below, because this path is not yet fully validated
end-to-end. The supported flow is the interactive one: open the agent, activate the skill, and
drive it with chat plus `/goal`.

How to prevent: treat the runtime CLI auth as a prerequisite, not part of the fleet. Verify the CLI
works on its own (`grok -p "hello"`, etc.) before wiring it into a campaign.

## Runtime spawn

`run-mission-headless.sh` and `run-campaign.sh` both validate their arguments before they spawn
anything. These are the early refusals.

### `error: unsupported runtime '<x>'`

What you see:

```
error: unsupported runtime 'gpt' (use grok, claude, or codex)
```

(or the `run-campaign.sh` variant: `error: unsupported runtime 'gpt' (expected grok|claude|codex)`)

What's wrong: the first positional argument must name a supported runtime. Both headless scripts
accept exactly `grok`, `claude`, or `codex`. Anything else is rejected before the venv even
bootstraps.

How to fix: use one of the three. The argument order is runtime first, then mission:

```bash
./scripts/run-mission-headless.sh claude doc-sync --max-turns 50
```

How to prevent: the runtime is the first arg, not the mission. A frequent mistake is
`run-mission-headless.sh doc-sync claude`, which fails this check on the word `doc-sync`.

### `error: unknown mission '<x>' (not in mission registry)`

What you see:

```
error: unknown mission 'doc-synced' (not in mission registry)
```

What's wrong: the mission name is looked up in `lib.mission_registry.MISSION_DOCS`. If it is not a
registered mission, the run aborts before spawning. Registered missions correspond to the shipped
mission skills: `doc-sync`, `test-coverage`, `adversarial-review-and-fix`, plus `fleet-program`
for campaigns.

How to fix: spell the mission exactly as the skill directory under `skills/` is named. List them:

```bash
ls skills/ | grep -vE 'adapter|^autonomous-fleet$|^autonomous-fleet-core$|^setup'
```

How to prevent: copy the mission slug from the mission catalog (Guide chapter 09), do not type it
from memory. A trailing `s` or a `-and-fix` typo is the usual cause.

### `error: --repo '<path>' is not a git repository`

What you see:

```
error: --repo '/tmp/scratch' is not a git repository
```

What's wrong: the script resolves `--repo` to an absolute path and runs
`git -C "$REPO_ROOT" rev-parse --is-inside-work-tree`. If that fails, the path is not inside a git
work tree. Common causes: a typo'd path, a directory that was never `git init`-ed, or a path that
exists but is not a checkout.

How to fix: point `--repo` at the root of an actual git checkout. When you omit `--repo`, the
target defaults to the fleet clone itself.

How to prevent: `git -C <path> status` before you pass a path as `--repo`. The fleet runs from its
own clone, but the agent's working directory is the `--repo` target.

### `error: --yolo against an external --repo auto-approves every tool call`

What you see:

```
error: --yolo against an external --repo auto-approves every tool call — a full RCE surface.
       Run under scripts/run-sandboxed.sh, or pass --yolo-untrusted-acknowledged to accept the risk.
```

What's wrong: `--yolo` auto-approves every agent tool call. Against an external `--repo` (any path
other than the fleet clone) that is a full remote-code-execution surface, so the script refuses
with exit 2 unless you explicitly acknowledge the risk.

How to fix: pick one, deliberately:

```bash
# Option A: run inside the safety wrapper (recommended)
./scripts/run-sandboxed.sh ./scripts/run-mission-headless.sh grok doc-sync --repo /path --yolo

# Option B: accept the RCE risk explicitly (only on a repo you fully trust)
./scripts/run-mission-headless.sh grok doc-sync --repo /path --yolo --yolo-untrusted-acknowledged
```

`run-campaign.sh` propagates the acknowledgement down to the per-node `run-mission-headless.sh`
calls, so you set the flag once at the campaign level.

How to prevent: keep `--yolo` off. It only auto-approves for Grok and exists for unattended runs on
trusted repos. The default is no auto-approve, and that is the right default. See Guide chapter 12
for the full threat model.

### A `--yolo`-related command was refused by the sandbox

What you see (running under `run-sandboxed.sh`):

```
run-sandboxed: REFUSED (DENY): irreversible command, <the command line>
```

or:

```
run-sandboxed: REFUSED (ASK): outward / destructive-but-recoverable command, <the command line>
```

What's wrong: `run-sandboxed.sh` classifies the wrapped command line by blast radius before it
execs anything. `DENY` (exit 2) is irreversible: a force-push, `rm -rf` of a critical path, a
`git reset --hard` to a remote ref, `gh pr merge`, `gh repo delete`, or infra
`apply`/`deploy`/`destroy`/`delete`. `ASK` (exit 3) is outward but recoverable: an ordinary
`git push`, a `gh release`, an `rm -rf` of a scoped path. The wrapper is non-interactive, so an
`ASK` has no human to prompt and it refuses too.

How to fix: there is no flag to override the verdict. The wrapper is a net against accidental and
obvious damage. If the command is genuinely intended, review it and re-run it **by hand**, outside
the wrapper. To see a verdict without running anything:

```bash
./scripts/run-sandboxed.sh --classify git push --force origin main   # prints DENY
./scripts/run-sandboxed.sh --classify rm -rf ./build                 # prints ASK
```

How to prevent: this is the wrapper doing its job. If a mission keeps tripping it on a legitimate
command, that command should not be inside an unattended run in the first place. Note the wrapper is
**not** an OS sandbox: it does not confine filesystem, network, or syscalls, and a command
constructed at shell runtime (`$(...)`, `eval` of a built string, base64 payloads) can evade the
static classifier. Pair it with real OS-level isolation (`container-use`) for genuinely untrusted
targets. See Guide chapter 12.

### Credentials still visible inside a sandboxed run

What you see: the wrapped command reads a token you expected to be scrubbed, for example an agent
that still finds `GH_TOKEN`.

What's wrong: `run-sandboxed.sh` execs the command via `env -i` with only an allowlist of names
(`PATH HOME USER LOGNAME SHELL LANG TERM TMPDIR PWD` plus all `LC_*`). It then explicitly drops any
preserved name matching `AWS_*`, `*_TOKEN`, `*_KEY`, `*_SECRET`, `*_PASSWORD`, `GH_TOKEN`,
`GITHUB_TOKEN`, `XAI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. A credential survives only if
it lives somewhere the scrub cannot reach: a file on disk the agent reads, or a name that does not
match those shapes.

How to fix: confirm what the scrubbed environment actually contains:

```bash
./scripts/run-sandboxed.sh env
```

If a secret you care about is there, it is named in a shape the scrub does not match. Rename it to a
matched shape, or do not put it in the ambient environment. Credentials in files (`~/.aws/`,
`~/.config/gh/`) are out of scope for env scrubbing entirely; use OS-level isolation for those.

How to prevent: never let production credentials reach this script's ambient environment in the
first place. The scrub is defense in depth, not the boundary.

## Ledger and locks

The ledger is a directory of files under `.fleet/runs/<run_id>/`, not a database. Locks live under
`.fleet/runs/<run_id>/locks/` as JSON files. Failures here are mechanical and the error text names
the file.

```
.fleet/runs/<run_id>/
├── locks/
│   ├── construction-<task_id>.lock   # long-held: from BUILD start to COMMIT/ABORT
│   └── request-<request_id>.lock     # short-held: around one external write-API call
├── manifest.json
├── trace.jsonl
└── ... (findings, blind-fix, verify-summary, readiness)
```

### `LockTimeoutError: acquire timed out after <N>s`

What you see (a Python traceback raised from `scripts/lib/locks.py`):

```
LockTimeoutError: acquire timed out after 30.0s: .fleet/runs/<run_id>/locks/construction-<task_id>.lock
```

What's wrong: another worker holds the lock and did not release it within the timeout. The lock is
acquired with an atomic no-clobber `os.link`, with exponential backoff up to one second per poll.
A `ConstructionLock` defaults to a 30-second timeout; a `RequestLock` to 5 seconds (it should be
uncontested most of the time). The lock body is `{"owner", "acquired_at", "pid"}`.

How to fix: inspect the lock and find out who holds it:

```bash
cat .fleet/runs/<run_id>/locks/construction-<task_id>.lock
```

If the `pid` in that file is a live process, the holder is genuinely still working: wait, or
investigate why it is stuck. If the `pid` is dead, the lock is stale and can be stolen (see below).

How to prevent: this is contention, not corruption. Two workers wanting the same construction slot
at once is a coordinator scheduling question, not a lock bug. One mission per repo at a time is the
rule (Guide chapter 05) precisely to keep construction locks uncontested.

### `LockStealError: holder pid <N> still alive`

What you see:

```
LockStealError: holder pid 4812 still alive: .fleet/runs/<run_id>/locks/construction-<task_id>.lock
```

or, raised at the second check just before the atomic replace:

```
LockStealError: holder pid 4812 revived before steal: .fleet/runs/<run_id>/locks/...
```

What's wrong: someone tried to steal a lock whose holder pid still resolves to a live local
process. Stealing is the explicit recovery path for a **dead** holder only. The steal does two
liveness checks: one when it reads the lock, and a second one immediately before the atomic
`os.replace`, to close the window where the holder revives mid-steal. Lock age never authorizes
stealing a live holder: `max_stale_s` is retained for API compatibility but does nothing.

How to fix: do not steal a live holder's lock. If the holder is genuinely stuck, kill that process
first, confirm the pid is gone, then steal. The steal is gated on the dead-worker detection
discipline; the module exposes the mechanism, the caller enforces the precondition.

How to prevent: only steal after the signal-reconciliation dead-worker detection has confirmed the
holder is gone (Guide chapter 06). A single poll is not a death certificate.

### `LockOwnershipError: lock owner mismatch`

What you see:

```
LockOwnershipError: lock owner mismatch: expected 'pid-1234', got 'pid-5678' (.fleet/runs/<run_id>/locks/...)
```

or:

```
LockOwnershipError: lock file unparseable: .fleet/runs/<run_id>/locks/... (...)
```

What's wrong: a worker tried to release a lock it does not own, or the lock file is no longer valid
JSON. Release is owner-checked: it reads the file, parses it, and refuses unless the recorded
`owner` matches. A mismatch means the lock was stolen out from under this worker (its construction
was abandoned) or two workers were misconfigured to share an owner string.

How to fix: a mismatch on release is usually a symptom, not a cause. It means this worker's slot was
reclaimed. Check whether a steal happened (look for a `stolen_from` field in the current lock body)
and treat that worker's output as abandoned. An unparseable lock is recoverable corruption: an
empty lock file can be replaced by a steal because it cannot identify a live holder.

How to prevent: do not share owner strings across workers. The default owner is `pid-<getpid>`,
which is already unique per process. Only override it if you know why.

### Lock directory missing

What you see: an `OSError` about a missing path under `locks/`, or a release raising
`LockOwnershipError: cannot read lock file (gone?)`.

What's wrong: `acquire()` creates `locks/` with `mkdir(parents=True, exist_ok=True)` before it
writes, so a missing directory at acquire time is not the failure. A lock file that vanished between
acquire and release means something deleted the run archive out from under the run (a stray
`rm -rf .fleet/`, a cleanup script, a sandbox tearing down the tree).

How to fix: do not delete `.fleet/runs/<run_id>/` while a run is live. If you did, the run is
unrecoverable; start a fresh run.

How to prevent: treat the run archive as append-only for the life of the run. The integrity gates
(below) assume nothing in it is mutated after the producer wrote it.

## Verification failures

The substrate is four layers (Guide chapter 07). These are the failures the verifiers raise. A
verification failure is the framework working, not breaking: it caught bad work before it merged.

### Layer 3 blind-fix: anti-anchoring violation

What you see (from `validate-all.sh`, the `verify-blind-fix (Layer 3)` block, or
`scripts/verify_blind_fix.py <run_dir>` directly):

```
verify-blind-fix: at least one archive failed Layer 3
```

with the per-archive detail naming a findings file that has no valid blind-fix file. The manifest
ordering invariant raises the precise form:

```
<archive>: ANTI-ANCHORING violation: blind_fix '<path>' (producer='<p>') mtime <t1> is not strictly
before findings '<path>' mtime <t2>
```

What's wrong: Layer 3 enforces that the mechanical blind-fix was written **before** the reviewer's
findings, per producer, so the fix cannot have anchored on the finding. A blind-fix whose mtime is
at or after the findings mtime breaks that ordering. The scan covers every
`.fleet/runs/<run_id>/` that contains a `p0-review-findings.json`.

How to fix: this is a real ordering violation. Re-run the blind-fix step so it genuinely precedes
findings, or correct the manifest if the mtimes were recorded wrong. Do not paper over it by
editing the timestamp: the on-disk sha256 check will catch a hand-edited file.

How to prevent: produce artifacts in the doctrine order: blind-fix first, then findings, then the
verify-summary, then readiness last. See [archive validation](#archive-validation).

### sha-pin: REVIEWED is OUTDATED

What you see (from `validate-all.sh`, the `verify-sha-pin` block, or
`scripts/verify_sha_pin.py <run_dir>` directly):

```
FAIL  <branch> moved <reviewed_sha>..<head>: REVIEWED is OUTDATED, force re-review
```

or, when the branch HEAD cannot be resolved and there is no merged marker:

```
FAIL  <branch>: HEAD unknown for reviewed <reviewed_sha> and no merged marker; cannot enforce SHA-pin
```

What's wrong: a reviewer PASS is pinned to the exact SHA it inspected. The reviewer wrote
`.fleet/runs/<run_id>/sha-pin.json` with `{reviewed_sha, branch, verdict}`, and the branch HEAD has
since moved off `reviewed_sha`. The approval no longer covers what is on the branch, so the verifier
flips the verdict from REVIEWED to OUTDATED. Only `approve`/`PASS` records are enforced; a
`request_changes` record is schema-valid but skipped. A deleted branch is N/A (not a failure) only
when a merged marker is present, in the record or in a sibling readiness / fleet-outcome doc.

How to fix: re-review the branch at its new HEAD and write a fresh `sha-pin.json` whose `reviewed_sha`
equals the current HEAD. Do not hand-edit the old SHA forward: the point of the pin is that the
approval names the exact commit a human (or the next gate) can reproduce. If the branch legitimately
merged, record the merged marker so the check reads N/A.

How to prevent: never push to a branch after it is reviewed-and-approved without re-reviewing. If you
must rebase or amend, treat the prior PASS as void. To silence the check for a run (understand what
you are turning off first), set `FLEET_DISABLE_SHA_PIN=1`, which exits 0 with a `DISABLED` notice.

### round-budget: a task merged after exhausting its review rounds

What you see (from `validate-all.sh`, the `verify-round-budget` block, or
`scripts/verify_round_budget.py <run_dir>` directly):

```
verify-round-budget: <N> tasks checked; <M> violations
  - <task_id> ran <rounds> review rounds then MERGED without BLOCKED
```

or, when the task ran over budget but never reached a terminal state:

```
  - <task_id> ran <rounds> review rounds without terminal BLOCKED
```

What's wrong: the trace stream is the source of truth for review-round exhaustion. The verifier counts
failed reviewer events (`role: REVIEWER`, `status: failed`) per task in `trace.jsonl`. Once a task
crosses `MAX_ROUNDS` (3) failed rounds, it MUST finish as `GOAL_BLOCKED` / `blocked` and must NOT have
shipped through a successful `MERGE`. A task that merged anyway, or that ran over budget with no
terminal BLOCKED, is the circuit breaker firing: review never converged and the task should have been
escalated, not forced through.

How to fix: this is a real doctrine violation in the run, not a verifier bug. The task should have
been blocked after its third failed review and sent to `DECISIONS.md`. Re-drive it: either the
builder's fix genuinely closes the findings (in which case the failed rounds were a flapping reviewer,
worth investigating) or the task is stuck and belongs blocked.

How to prevent: stop a review loop at three failed rounds. To silence the check for a run, set
`FLEET_DISABLE_ROUND_BUDGET=1`.

### registry-lint: the catalog has drifted from the registry

What you see (from `validate-all.sh`, the `registry-lint` block, or `scripts/registry_lint.py .`):

```
registry-lint: <mission>: shipped:true points to missing skills/<dir>/SKILL.md
registry-lint: skills/<dir>/SKILL.md is a mission skill but has no shipped:true registry row
registry-lint: README.md: missing shipped mission <mission>
registry-lint: skills-lock.json: missing shipped skill dirs: <dirs>
registry-lint: skills-lock.json: stale skill dirs not on disk: <dirs>
```

What's wrong: `scripts/lib/fleet_registry.py`'s `MISSIONS` dict is the single source for the
mission/adapter catalog, and the lint asserts three things stayed in sync with it: every `shipped:true`
row has its on-disk `skills/<skill_dir>/SKILL.md` (and every on-disk mission skill has a `shipped:true`
row), every shipped mission is named in `README.md` and the umbrella `autonomous-fleet/SKILL.md`
catalog, and the local-source dirs in `skills-lock.json` match the skill dirs on disk. Any of those
drifting (you shipped a skill but forgot the registry row, renamed a dir, or added a mission to the
README but not the registry) trips the lint.

How to fix: read the specific line. A `missing skills/<dir>/SKILL.md` means the registry row points at
a dir that does not exist (fix the `skill_dir`, or add the skill). A mission skill with no
`shipped:true` row means you added a mission skill without registering it. A `README.md: missing
shipped mission` means the catalog prose is stale. A `skills-lock.json` mismatch means the lockfile is
out of date: re-run the installer so the lock matches disk.

How to prevent: when you ship or rename a mission, edit `MISSIONS` in the same change, then run
`./scripts/validate-all.sh` (or `scripts/registry_lint.py .`) before you push. To silence it for a
run, set `FLEET_DISABLE_REGISTRY_LINT=1`.

### reviewer-sandbox: a reviewer was attributed a write on the candidate

What you see (from `validate-all.sh`, the `verify-reviewer-sandbox` block, or
`scripts/verify_reviewer_sandbox.py <run_dir>` directly):

```
FAIL  <manifest>.files[<i>]: reviewer producer '<slug>' is attributed 'diff' on candidate branch '<branch>'
```

or, for any other non-review artifact kind:

```
FAIL  <manifest>.files[<i>]: reviewer producer '<slug>' emitted forbidden kind '<kind>'; allowed reviewer kinds are ['blind_fix', 'findings', 'verify_summary']
```

What's wrong: the reviewer is read-only. In a run-archive manifest, a producer slug detected as a
reviewer (or named with `--reviewer-producer`) may only emit `blind_fix`, `findings`, and
`verify_summary` entries. A reviewer producer attributed a `diff` or `commit` on the candidate branch
is a hard failure: it means the agent that graded the work also wrote some of it, which breaks
build-blindness. Live enforcement is `scripts/run-sandboxed.sh --role reviewer` (read-only candidate
tree, only `.fleet/runs/<run_id>/` writable); this verifier is the audit-side companion that catches a
violation after the fact in the manifest.

How to fix: this is a topology violation, not a cosmetic one. The reviewer must run in its own
terminal with no edit rights to the candidate. Re-run the review under
`run-sandboxed.sh --role reviewer` so the placement is enforced, and make sure the builder, not the
reviewer, is the producer on any `diff`/`commit` entry. If the manifest mislabeled a builder artifact
as a reviewer producer, fix the producer attribution.

How to prevent: place the reviewer with `run-sandboxed.sh --role reviewer`. On macOS it uses
`sandbox-exec`, on Linux `bwrap`, and where neither exists it falls back to a post-exec tracked-file
hash assertion that exits 4 if the reviewer touched any tracked file outside the run dir. To silence
the audit check for a run, set `FLEET_DISABLE_REVIEWER_SANDBOX=1`.

### namespacing: a recorded branch/worktree is not run-namespaced

What you see (from `validate-all.sh`, the `validate-namespacing` block, or
`scripts/validate_namespacing.py <run_dir>` directly):

```
FAIL .fleet/runs/<run_id>
  - <ledger>: TASK <task_id> branch '<branch>' must end with '-<run_short>'
  - <ledger>: TASK <task_id> worktree '<wt_path>' must end with '-<run_short>'
```

What's wrong: every isolated branch and worktree must carry the run's `-<run_short>` suffix (the 6-hex
tail of the `run_id`, from `namespace.derive_run_short`), so two concurrent runs or two checkouts of
the same slug never collide on a branch name or worktree path. The validator reads each archive
manifest, follows its `progress`-kind ledgers, and fails any task row whose recorded branch or
worktree does not end with the suffix. A malformed `run_id` (no 6-hex tail) fails too, because the
suffix cannot be derived.

How to fix: namespace the placement. Branches should be `<prefix><slug>-<run_short>` and worktrees
`../<repo>-<slug>-<run_short>` (what `namespaced_branch` and `namespaced_worktree` produce). If the
ledger recorded a bare, un-suffixed branch, the placement step did not namespace it: fix the adapter's
`PLACE`/`SPAWN_WORKER` to emit the suffix, then re-record. Do not hand-append the suffix to the ledger
without renaming the actual branch and worktree, or the next git operation will miss them.

How to prevent: use the `namespace.py` helpers (or the adapter's namespaced placement) for every
isolated branch and worktree. All four adapters and the template already do. To silence the check for
a run, set `FLEET_DISABLE_NAMESPACING=1`.

### Trace stream fails schema validation

What you see (from `validate-all.sh`, the `validate-trace` block, or
`scripts/emit_trace.py validate <trace_file>`):

```
validate-trace: at least one archive failed schema validation
```

with per-line detail like:

```
emit-trace: <path>:<lineno>: primitive must be one of ['SPAWN_WORKER', 'DISPATCH', 'WAIT',
'INSPECT', 'SYNC', 'MERGE', 'FREEZE', 'T-FINAL', 'GOAL_BLOCKED', 'COMMIT', 'ABORT'], got '<x>'
```

What's wrong: a line in `trace.jsonl` does not match the schema. `validate_event` checks the
required fields, the `primitive` against the 11-value tuple, the `role` against
`COORDINATOR/BUILDER/REVIEWER/INTEGRATOR/FIXER/OTHER`, and the `status` against
`started/succeeded/failed/blocked/skipped`. Unparseable JSON on a line is reported as
`invalid JSON` and counted as bad too.

How to fix: read the line and field the error names. If you hand-wrote a trace line, match the
enums exactly (case-sensitive, hyphenated `T-FINAL`). If the line was emitted by the framework and
still fails, that is a bug worth an issue.

How to prevent: emit through `TraceEmitter.emit(...)`, which builds the event with the correct
schema version and required fields. Do not append raw lines to `trace.jsonl` by hand.

### `ValueError` raised from `emit()`: secret or host-path in `details`

What you see (a `ValueError` from `scripts/lib/emit_trace.py`, raised at emit time):

```
ValueError: details['key'] looks like a secret; reference by evidence_hash
```

or:

```
ValueError: details['key'] leaks a host-absolute path; use a repo-relative path
```

What's wrong: the `details` free-form payload is scanned at **emit** time (and again by
`validate_event`). If a value matches a secret shape (`sk-...`, `AKIA...`, `ghp_...`, `xai-...`, a
`PRIVATE KEY` block) or a host-absolute path (`/home/...`, `/Users/...`, `/root/...`, or a
`/.ssh/`, `/.aws/`, `/.gnupg/` segment), `emit()` raises rather than write the line. This is not a
prose rule any more: it is enforced by the validator and by the emitter together.

How to fix: do not put the raw secret or host path in `details`. Reference a secret by its
`evidence_hash` (the 64-hex content hash), and use a repo-relative path instead of a host-absolute
one.

How to prevent: keep `details` to small, structured, non-sensitive metadata. The
`trace-emit-atomicity-off` mutation guards that the line is written-and-flushed in one call, so a
partial line never reaches disk; the redaction guard keeps a sensitive line from reaching disk at
all.

## PR-open failures

The fleet opens PRs through the runtime's own tools (`gh`, the agent's git integration). Most
PR-open failures are upstream of the fleet: a missing `gh` auth, a protected branch, a dirty tree.

### `gh` is not authenticated

What you see: the agent's PR step fails with a `gh` auth error (`gh: To get started with GitHub
CLI, please run: gh auth login`), surfaced through the agent transcript.

What's wrong: opening a PR needs an authenticated `gh` (or equivalent) on the host. The fleet does
not manage `gh` credentials; the env scrub in `run-sandboxed.sh` deliberately strips `GH_TOKEN` and
`GITHUB_TOKEN`, so a sandboxed run cannot open a PR using an ambient token.

How to fix: authenticate `gh` outside the sandbox (`gh auth login`), then run the PR-opening step
outside `run-sandboxed.sh`. The wrapper is for the work, not for the outward write.

How to prevent: treat PR opening as the outward boundary. The sandbox classifies `gh pr merge` as
`DENY` and `gh release` as `ASK` on purpose; opening a PR is a human-adjacent step, not part of an
unattended scrubbed run.

### A `git push` was refused

What you see (under the sandbox):

```
run-sandboxed: REFUSED (ASK): outward / destructive-but-recoverable command, git push ...
```

or, for a force-push:

```
run-sandboxed: REFUSED (DENY): irreversible command, git push --force ...
```

What's wrong: an ordinary `git push` is `ASK`; a force-push (`--force`, `-f`, a `+refspec`, or
`--mirror`) and a remote-branch delete (`--delete`, `--prune`, `-d`, a `:refspec`) are `DENY`. The
wrapper will not run either.

How to fix: push by hand, outside the wrapper, once you have eyeballed the command. Never let an
unattended run force-push.

How to prevent: a mission that needs to force-push is doing something it should not. Squash or
rebase locally, then push a fresh branch.

## Archive validation

The run-archive is the proof the run produced what it claims. `validate_run_archive.py` checks
schema shape, the mtime-ordering invariants, and (by default) on-disk sha256 and size. Three
ordering invariants and a checksum check fail loudly.

### `FAIL <archive> (manifest.json missing)` or invalid manifest JSON

What you see:

```
FAIL .fleet/runs/<run_id> (manifest.json missing)
```

or:

```
FAIL .fleet/runs/<run_id> (invalid manifest JSON: <exc>)
```

What's wrong: the archive directory has no `manifest.json`, or the file is not valid JSON. The
manifest is the index of every file in the archive; without it there is nothing to validate
against.

How to fix: a missing manifest means the run never reached `write_manifest`, so the archive is
incomplete. Re-run. Do not hand-write a manifest: the validator cross-checks `run_id`, `mission`,
and a per-file sha256 against disk.

How to prevent: let the run finish. The doctrine is trace first, ledger second: `write_manifest`
emits the `T-FINAL` event **before** it writes `manifest.json`, so a crash leaves a trace event
explaining the absence of a manifest rather than a manifest with no externally visible cause.

### `ANTI-ANCHORING`, `stale-audit`, or `readiness-not-latest` violation

What you see (one of three, from `validate_run_archive.py` or `validate-all.sh`):

```
<archive>: ANTI-ANCHORING violation: blind_fix '<p>' ... mtime <t1> is not strictly before findings '<p>' mtime <t2>
<archive>: stale-audit violation: verify_summary '<p>' ... mtime <t1> is not strictly after findings '<p>' mtime <t2>
<archive>: readiness-not-latest violation: <kind> file '<p>' mtime <t1> is after the latest readiness mtime <t2>
```

What's wrong: the three cross-cutting mtime-ordering invariants, per producer:

```
Invariant 1  blind_fix mtime  <  findings mtime        (the fix can't anchor on the finding)
Invariant 2  verify_summary mtime  >  findings mtime    (the audit can't be stale)
Invariant 3  readiness mtime  =  max(all file mtimes)   (readiness is written last)
```

A schema-clean manifest that violates any of these is still doctrine-broken. These are the Commit
1-3 disciplines made auditable.

How to fix: produce the files in the right order. If the run already ran correctly and only the
recorded mtimes are wrong, the producer recorded them wrong: fix the producer, not the manifest. A
hand-edited mtime will desync from the file's real mtime and the sha256 check will fail.

How to prevent: write in doctrine order, end with readiness:

```
blind_fix ─► findings ─► verify_summary ─► readiness (last, latest mtime)
```

### `sha256`/size mismatch or `path escapes archive directory`

What you see (shape and on-disk detail, prefixed with the archive location):

```
<archive>.files[<i>]: sha256 must be 64 hex chars
<archive>.files[<i>]: path '<p>' escapes archive directory
<archive>.files[<i>]: bytes must be a non-negative int
```

plus on-disk mismatches when a file's recorded size or sha256 does not match what is on disk.

What's wrong: a file in the archive was modified after the manifest recorded its hash, or a manifest
entry is malformed. The validator resolves each path under the archive root and rejects any path
that starts with `/` or contains `..` (it must not escape the directory). Size is checked first as a
cheap fail-fast, then sha256.

How to fix: do not edit archive files after the manifest is written. If a file legitimately
changed, the producer must rewrite the manifest entry (new sha256, new size, new mtime), not just
the file. To check shape and ordering without the on-disk checksum pass (useful when debugging a
manifest in isolation):

```bash
"$VENV_PYTHON" scripts/validate_run_archive.py --no-checksums .fleet/runs/<run_id>
```

How to prevent: treat the archive as immutable once written. The evidence-hash is the whole point:
it proves the file the manifest describes is the file on disk.

## Mutation gate

The mutation gate (Layer 4) asserts every mutation in `tests/mutations.yaml` is caught by its guard
tests. There are 50 mutations today.

### A mutation survived

What you see: `scripts/mutation-check.sh` (which execs `scripts/mutation_check.py`) reports a
surviving mutation, naming the mutation `id` and the guard tests that failed to catch it.

What's wrong: a mutation is a deliberate one-line break (for example
`lock-steal-second-liveness-check-off`, `blocked-halt-disabled`, `rm-catastrophic-downgraded`).
Each mutation pins a behavior and lists its `guards`. A surviving mutation means the guard tests
passed even with the behavior broken, so the test no longer protects that behavior.

How to fix: this is a test-coverage regression, not an operator error. The guard test for that
mutation is now too weak. Strengthen the test until it fails under the mutation, then confirm the
gate goes green:

```bash
./scripts/mutation-check.sh
```

How to prevent: when you change guarded code, run the mutation gate before you commit. The gate is
the standing assertion that the substrate's own tests still bite. Mutation testing catches
regressions that line coverage cannot: a test can execute a line and still not assert on its
behavior.

### `error: mutation manifest entry references a missing file/find`

What you see: `mutation_check.py` failing because a mutation's `find` string no longer appears in
its target `file` (the code moved or was rewritten and the manifest was not updated).

What's wrong: the mutation manifest pins an exact `find`/`replace` against a real file. If you
refactored the guarded code, the `find` anchor no longer matches.

How to fix: update the mutation entry's `find` to the new anchor text (and `replace` to the
corresponding break), keeping the `guards` list pointed at the tests that catch it. See Guide
chapter 13 for adding and editing mutation entries.

How to prevent: when you touch code that a mutation pins, grep `tests/mutations.yaml` for the file
path and update the affected entries in the same change.

## CI and the full gate

`validate-all.sh` is the whole gate in order. CI runs it; you should run it before you push.

```
validate-skills ─► validate-fleet-outcome ─► validate-goal-condition ─►
validate-run-archive ─► verify-blind-fix (L3) ─► verify-sha-pin ─► verify-round-budget ─►
registry-lint ─► verify-reviewer-sandbox ─► validate-namespacing ─► validate-trace ─►
pytest + coverage (100%)
```

### `coverage report --fail-under=100` fails

What you see (the final `pytest + coverage (100% gate)` block):

```
... TOTAL ... <100%
... did not meet the 100% coverage requirement
```

What's wrong: the gate runs `coverage run --source=scripts -m pytest tests/`, then
`coverage report --fail-under=100`. Any line in `scripts/` not executed by the test suite drops it
below 100% and fails.

How to fix: cover the new line with a test, or mark a genuinely unreachable line with a documented
`# pragma: no cover` (as `main()`'s `__main__` guard already is). Do not lower the threshold; 100%
is the gate.

How to prevent: write the test in the same change as the code. The coverage gate is paired with the
mutation gate on purpose: coverage proves a line ran, mutation proves the test that ran it actually
asserts on its behavior. You need both.

### One sub-validator fails and the rest never run

What you see: `validate-all.sh` exiting at the first failing block (the script is `set -euo
pipefail`), so a `validate-skills` failure stops everything before `pytest` runs.

What's wrong: the gate is fail-fast by design. An early failure short-circuits the later checks.
That is correct: there is no point running coverage if the skills do not even validate.

How to fix: read the **first** failure, fix it, re-run. Do not assume later blocks are also broken;
they simply did not run.

How to prevent: run the cheap validators first while iterating
(`./scripts/validate-skills.sh`, `./scripts/mutation-check.sh`) so you are not waiting on the full
suite to surface an early failure.

## Two honest caveats

Two things are genuinely limited today. They are not bugs you can fix from the operator side; they
are the current state of the framework, stated plainly.

### The trace stream is sparse in production

Exactly one trace event is wired into production code today: `T-FINAL`, emitted from
`fleet_run.write_manifest` (correctly, before the manifest write). The schema covers 11 primitives,
and the validators accept a full stream, but the stream is intentionally sparse while per-transition
emission rolls out across the coordinator and the adapters. So if you go looking for `DISPATCH`,
`SPAWN_WORKER`, `MERGE`, and the rest in a real run's `trace.jsonl` and find only `T-FINAL`, that is
expected, not a failure. The contract is real; the full emission is in progress. See the trace
schema reference (Guide chapter 16) for the field-by-field contract and the roadmap.

### Headless campaign mode is not yet fully validated

`run-campaign.sh` drives each runtime's CLI in headless mode, which requires that CLI to be
authenticated on the host. This path is **not yet fully validated end-to-end**. If a headless
campaign behaves unexpectedly, that is the reason: it is early. The supported flow today is the
interactive one: open the agent, activate the mission or `fleet-program` skill, and drive it with
chat plus `/goal`. Treat `run-campaign.sh` and `--preset` as a preview, and validate each node's
`fleet-outcome` by hand. See Guide chapter 12 for the headless caveat in the safety context.

## When to file an issue

This page covers operator-fixable failures. File a GitHub issue when:

- a framework-emitted artifact fails its own validator (a trace line the framework wrote fails
  `validate_event`, an archive the framework produced fails the ordering invariants)
- a mutation survives that you did not weaken
- a script prints a Python traceback that is not one of the named errors above
- the behavior contradicts what this guide says is true on `main`

Include the failing command, the exact stderr, and `git rev-parse HEAD` of the fleet clone. Do not
file an issue for a missing dependency, a wrong argument order, or an unauthenticated CLI: those are
covered here.
## Real-world use cases

### Example — headless auth failure

Ship-with-proof evidence: `grok -p` failed `Auth(AuthorizationRequired)`; run completed interactively.
Reproduce dry wiring without auth:

```bash
./scripts/validate-headless.sh
```

### Invocation — coverage subprocess trap

`docs/test-coverage-progress.md` SIGNAL RECONCILIATION: subprocess CLI tests on
`scripts/eval-campaign-edge.py` did not move coverage numbers — rewrite to in-process `main()`
invocation.

### Real run on fixture validators

When archive validation fails, start from committed good shape:

```bash
python scripts/validate_run_archive.py .fleet/runs/example-fixture
```

---

← [Extending](13-extending.md) · [Guide Index](README.md) · [Run-archive anatomy](15-run-archive.md) →
