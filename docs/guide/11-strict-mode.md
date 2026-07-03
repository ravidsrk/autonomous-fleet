<!-- title: Strict mode | description: Opt-in disk-level enforcement of EVID, WT_CLEAN, and e2e_verified via the Claude Code stop-verify Stop hook. | sidebar_order: 11 -->

# Strict mode

**On this page:** [What strict mode is](#what-strict-mode-is) ·
[What it enforces today](#what-it-enforces-today) ·
[The three discipline levels](#the-three-discipline-levels) ·
[Opting in](#opting-in) ·
[Verifying you actually enabled it](#verifying-you-actually-enabled-it) ·
[Configuration knobs](#configuration-knobs) ·
[What a worker sees on BLOCK](#what-a-worker-sees-on-block) ·
[Fail-open by design](#fail-open-by-design) ·
[What strict mode does NOT do](#what-strict-mode-does-not-do) ·
[Disabling it for one-off sessions](#disabling-it-for-one-off-sessions) ·
[Opting back out](#opting-back-out)

By default the engine's disciplines are honor-system. A worker that writes
`status: done` in a readiness doc is trusted on its word. Strict mode replaces
that trust with a disk scan: before a Claude Code worker can end its session, a
Stop hook looks for actual evidence and refuses to let the session close if it
finds none.

This is the chapter for the operator who wants enforcement at the filesystem,
not just discipline in a prompt. It is short on purpose: strict mode is one hook,
a handful of env vars, and a clear opt-in and opt-out. Everything here is true of
the Claude Code adapter on `main` today.

> Strict mode is Claude Code only right now. The hook is a Claude Code Stop-hook,
> so other runtime adapters (Codex, Grok, Orca) do not have it yet. Adding strict
> mode to a new adapter is covered in [Extending](13-extending.md), not here.

## What strict mode is

Strict mode is an opt-in install that wires the autonomous-fleet stop-verify Stop
hook into a Claude Code worker session. It makes the engine's three discipline
flags, `EVID`, `WT_CLEAN`, and `e2e_verified`, enforceable at runtime instead of
self-attested in prose.

The failure mode it closes is self-attested completion: a worker declares done
because it INTENDS to be done, not because verifiable evidence exists. Without the
hook, the engine takes the worker's `e2e_verified: true` at face value. With the
hook, the worker has to leave a trace on disk that backs the claim.

When a Claude Code worker reaches a Stop event, here is the flow:

```
  worker declares "done"
          |
          v
  CC fires the Stop hook  ───>  stop-verify.sh  ───>  scripts/stop_verify.py
          |                                                    |
          |                                  scans the repo for evidence in
          |                                  the freshness window (default 30min)
          |                                                    |
          v                                                    v
  evidence found?  ── yes ──>  {decision: allow}  ──>  session ends normally
          |
          no
          |
          v
  {decision: "block", reason: "..."}  ──>  CC refuses to end the session;
                                            worker must address the reason first
```

The hook scans for any of these evidence kinds, all within the freshness window:

```
  evid_flag       EVID=true in a progress ledger touched in the window
  wt_clean_flag   WT_CLEAN=true in a progress ledger touched in the window
  e2e_verified    e2e_verified: true in a readiness doc touched in the window
  status_done     status: done in a readiness doc touched in the window
  verify_summary  a passing summary from <SUBSTRATE>/verify_findings.py
  test_artifact   test-runner output (.pytest_cache, coverage/, junit XMLs)
  e2e_artifact    end-to-end artifacts (Playwright PNGs, trace screenshots)
```

If none are present, the hook blocks. The worker must produce real evidence (run
the test suite, run the EVID reproduction, write the readiness doc) before it can
stop.

## What it enforces today

Strict mode enforces exactly one thing: a Claude Code worker session cannot end
unless at least one fleet-outcome-grade evidence kind appears on disk inside the
freshness window. By default that window is the last 30 minutes and the threshold
is one distinct kind.

That is the whole enforcement surface. It is narrow on purpose. The hook is a
"did the worker leave proof it did the work" gate, not a correctness checker. It
does not read the contents of the proof beyond pattern-matching the flags above.

## The three discipline levels

There are three operating modes, in increasing strictness. You choose one by what
you install and which env vars you set.

```
  +----------------------------------------------------------------------------+
  | 🟢 LOOSE     no hook installed (default)                                   |
  |              Engine disciplines are aspirational. The worker self-attests   |
  |              via the readiness doc. Nothing on disk is checked.             |
  +----------------------------------------------------------------------------+
  | 🟡 STRICT    hooks.json installed, defaults                                 |
  |              At least one evidence kind in the last 30min, or the session   |
  |              refuses to end. The best default for most operators.           |
  +----------------------------------------------------------------------------+
  | 🔴 PARANOID  STOP_VERIFY_STRICT_PROGRESS=1 and STOP_VERIFY_MIN_KINDS=3      |
  |              Requires BOTH progress flags (EVID + WT_CLEAN) AND three        |
  |              distinct evidence kinds. For high-stakes adapters: production   |
  |              deploys, financial workflows, anything where a self-attested    |
  |              completion is a real risk.                                     |
  +----------------------------------------------------------------------------+
```

Most operators want 🟡 strict. Reach for 🔴 paranoid only when a false "done" is
genuinely expensive.

## Opting in

Strict mode is per-repo and per-worker. You install it once in any repo a fleet
worker will run inside. One step: register the hook.

### Per-repo install — skills-install mode (the common case)

No framework clone and no environment variable needed (issue #82): the adapter
ships the wrapper, and the wrapper resolves `stop_verify.py` from the core
skill's bundled substrate (`.agents/skills/autonomous-fleet-core/assets/substrate/`).
In the repo:

```bash
HOOKS=.agents/skills/autonomous-fleet-adapter-claude-code/assets/hooks
mkdir -p .claude
# If .claude/settings.json doesn't exist yet, copy the template wholesale:
cp "$HOOKS/hooks.json" .claude/settings.json
# If it already exists, merge the Stop entry into the existing hooks block:
jq '.hooks.Stop += input.hooks.Stop' .claude/settings.json "$HOOKS/hooks.json" \
   > .claude/settings.json.tmp && mv .claude/settings.json.tmp .claude/settings.json
```

Verify (with explain on, prints a BLOCK/ALLOW verdict line on stderr — BLOCK
also emits JSON on stdout; no "not found" warning either way):

```bash
echo '{"cwd":"."}' | STOP_VERIFY_EXPLAIN=1 bash "$HOOKS/stop-verify.sh"
```

### Per-repo install — framework clone

Identical with the clone's paths
(`skills/autonomous-fleet-adapter-claude-code/assets/hooks/`); optionally set
`AUTONOMOUS_FLEET_HOME=/path/to/autonomous-fleet` so the command and wrapper
resolve the clone explicitly. The wrapper's full resolution order:
`FLEET_SUBSTRATE` → `AUTONOMOUS_FLEET_HOME/scripts/` → walk-up from the
wrapper's own location (clone symlink — before the worker repo's copy so a
stale bundle never shadows the clone) → the worker repo's
`.agents/.../assets/substrate/`. Missing everywhere = fail-open ALLOW.

The template registers a single Stop hook that invokes the wrapper:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh -c 'for p in \"${AUTONOMOUS_FLEET_HOME:-$CLAUDE_PROJECT_DIR}/skills/autonomous-fleet-adapter-claude-code/assets/hooks/stop-verify.sh\" \"$CLAUDE_PROJECT_DIR/.agents/skills/autonomous-fleet-adapter-claude-code/assets/hooks/stop-verify.sh\" \"$CLAUDE_PROJECT_DIR/.claude/hooks/stop-verify.sh\"; do [ -f \"$p\" ] && exec bash \"$p\"; done; echo \"stop-verify: wrapper not found; allowing\" >&2'",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

That `command` line is the entire change to the adapter's hook config. It tries
the framework clone's wrapper first (via `AUTONOMOUS_FLEET_HOME`, falling back to
`CLAUDE_PROJECT_DIR`), then the skills-install copy under `.agents/skills/`, then
a wrapper copied into `.claude/hooks/` — whichever exists runs under `bash` and
delegates to the resolved `stop_verify.py`. The `timeout: 60` caps the gate at 60 seconds so a slow
scan can never wedge a session.

The next Claude Code session in this repo runs the gate.

## Verifying you actually enabled it

Installing a hook and having the hook actually fire are two different things. Run
this check after install. It pipes a minimal CC payload through the wrapper with
`STOP_VERIFY_EXPLAIN=1` (the verdict line only prints when explain is on) and
expects a BLOCK/ALLOW verdict on stderr with no "not found" warning:

```bash
echo '{"cwd":"."}' | STOP_VERIFY_EXPLAIN=1 bash "$HOOKS/stop-verify.sh"   # HOOKS from the install section
```

What you should see:

```
  exit code 0, a verdict line printed to stderr, no Python traceback
```

If you want the full human-readable verdict instead of the terse default, set the
explain knob for the one invocation:

```bash
echo '{}' | STOP_VERIFY_EXPLAIN=1 \
  "$AUTONOMOUS_FLEET_HOME/skills/autonomous-fleet-adapter-claude-code/assets/hooks/stop-verify.sh"
```

A clean run here means the wrapper resolved the checkout, found
`scripts/stop_verify.py`, and the gate executed. Two things to check if it does
not behave:

```
  stop-verify: warning, CLI not found at .../scripts/stop_verify.py
     ->  AUTONOMOUS_FLEET_HOME points at the wrong directory, or the checkout
         is incomplete. Fix the env var and re-run.

  no verdict line at all, but the hook is in .claude/settings.json
     ->  open .claude/settings.json and confirm the Stop entry's `command`
         resolves: echo it and check the path exists and is executable.
```

To prove the gate actually blocks (not just allows), run it from a directory with
no recent evidence and watch for the BLOCK message described below. An ALLOW on an
empty repo with no evidence files in the window means the freshness window has not
been crossed yet, or a kill switch is set. Check
[Configuration knobs](#configuration-knobs).

## Configuration knobs

The gate is configured via env vars, not JSON. They are kept as env (not
`hooks.json` args) so the config surface survives subprocessing and
`.claude/settings.json` schema drift across Claude Code versions.

```
  Env var                        Default   Effect
  -----------------------------  --------  ----------------------------------------
  STOP_VERIFY_WINDOW_MIN         30        Freshness window in minutes. Clamped
                                           to 1..1440.
  STOP_VERIFY_MIN_KINDS          1         Minimum distinct evidence kinds
                                           required to allow.
  STOP_VERIFY_STRICT_PROGRESS    unset     When set (any value), require BOTH
                                           EVID=true AND WT_CLEAN=true in a ledger
                                           file, on top of the base threshold.
  STOP_VERIFY_EXPLAIN            unset     When set, print a human-readable verdict
                                           to stderr (visible in CC's hook log).
  FLEET_DISABLE_STOP_VERIFY      unset     Operator kill switch. Truthy value
                                           (1/true/yes/on, case-insensitive) makes
                                           the hook return ALLOW immediately.
```

The kill switch is checked first, before any scan: if `FLEET_DISABLE_STOP_VERIFY`
is truthy, the gate allows and exits without looking at disk. Use it for adapter
test harnesses that need to drive sessions without artifact requirements. The same
truthy-value convention is shared substrate-wide; see
`references/substrate-disable-knobs.md` for the full set of disable knobs.

To run paranoid mode, set both of these in the worker env before the session:

```bash
export STOP_VERIFY_STRICT_PROGRESS=1
export STOP_VERIFY_MIN_KINDS=3
```

## What a worker sees on BLOCK

When the gate blocks, the CLI emits a structured BLOCK message as JSON on stdout
(the part Claude Code reads to refuse the session) and, with explain on, an
identical human-readable form on stderr. The message looks like this:

```
stop-verify: BLOCKED, no fleet-outcome-grade evidence in the last 30min.
  evidence found: no evidence kinds matched
  required: at least 1 distinct kind(s) from {evid_flag, wt_clean_flag,
    e2e_verified, status_done, verify_summary, test_artifact, e2e_artifact}

To unblock:
  - Run the fix's own EVID reproduction (the exact curl/test/script from
    the finding's Evidence block) and set EVID=true in the ledger.
  - Run the test suite end-to-end (pytest / jest / cargo test / go test).
  - Write the readiness doc with `status: done` (and `e2e_verified: true`
    if the mission requires it).
  - Or, for verified review missions, run <SUBSTRATE>/verify_findings.py
    --summary-out.

If this is a no-edit turn (status/diagnostic only), set
FLEET_DISABLE_STOP_VERIFY=1 in the worker env or remove the Stop hook for
that adapter.
```

The first line names the failure mode. The middle lines enumerate the checks. The
"To unblock" section is a CONCRETE action list, not a vague scold: vague BLOCK
messages cause retry loops, which is the lesson the upstream patterns taught. The
escape hatch is named explicitly so an operator can opt out of an over-aggressive
gate.

## Fail-open by design

The hook NEVER traps a session on internal error. If the CLI crashes, if Python is
missing, if `--repo` is invalid, if stdin is malformed: the gate ALLOWS and logs a
warning to stderr.

```
  broken hook + trapped worker   >   missed gate
```

A broken hook holding a worker mid-session is a worse failure than a single missed
gate. So a misconfigured strict-mode install degrades to loose mode with a
warning, not a deadlock. This is also why the verification step above matters: a
silently-failing-open hook looks identical to no hook until you check.

## What strict mode does NOT do

Strict mode is one layer on top of the existing disciplines, not a replacement for
any of them.

- It does NOT replace the validate-readiness validator. Schema conformance of
  `fleet-outcome` YAML is still that validator's job. The hook only checks that a
  readiness doc with `status: done` appeared in the window. It does not validate
  the YAML inside.
- It does NOT replace Layer 1's verify-findings. Schema-verified reviewer findings
  are still mandatory for review missions. The hook CONSUMES a passing
  verify-summary as one evidence kind, but it is not the verifier.
- It does NOT enforce lane-A merge discipline, branch hygiene, or any other
  engine.md rule. Those stay mission-level responsibilities. The hook enforces the
  three named flags and nothing else.

For where strict mode sits among the four verification layers, see
[The substrate](07-the-substrate.md). Strict mode is the operator-facing opt-in on
top of Layer 2 (the stop-verify hook).

## Disabling it for one-off sessions

Some turns are status-only or diagnostic with no edits, and there is genuinely no
evidence to produce. Two ways to skip the gate for one session, in order of
preference:

1. `FLEET_DISABLE_STOP_VERIFY=1` in the worker env. Explicit, and it leaves an
   audit trail in the environment. This is the right way.
2. Move `.claude/settings.json` aside for the session. Heavy-handed but guarantees
   no hook runs. Put it back afterward.

```bash
# Preferred: skip the gate for exactly this session.
FLEET_DISABLE_STOP_VERIFY=1 <run your one-off Claude Code session>
```

## Opting back out

To remove strict mode entirely, remove the `Stop` entry from
`.claude/settings.json` (or delete the file if the fleet hook was its only
content). Because the wrapper runs from the autonomous-fleet checkout, nothing else
needs cleaning up in the repo: there is no copied script to delete.

Announce the removal so the next operator knows strict mode was dropped. Do not
remove it silently. A repo that looks like it has enforcement but does not is worse
than one that never claimed to.
## Real-world use cases

### Example — validate-all as strict gate

`docs/test-coverage-progress.md` closed when `scripts/` hit 100% coverage — the same gate
`./scripts/validate-all.sh` enforces on every merge.

### Invocation — registry lint on campaigns

`python scripts/registry_lint.py scripts/campaigns/repo-health.yaml` rejects demoted missions in
active YAML — repo-health was aligned to shipped missions only (v0.1.0 changelog).

### Real run on mutation-check

Roadmap verification plan requires `./scripts/mutation-check.sh` alongside validate-all — substrate
mutations must stay caught.

---

← [Campaigns](10-campaigns.md) ·
[📖 Guide Index](README.md) ·
[Safety and secrets](12-safety-and-secrets.md) →
