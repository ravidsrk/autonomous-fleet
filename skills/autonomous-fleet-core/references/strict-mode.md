# Strict mode — runtime enforcement of EVID, WT_CLEAN, and e2e_verified

This reference defines **strict mode**: an opt-in install that wires the
autonomous-fleet stop-verify Stop hook into a Claude Code worker session,
making the engine's three discipline flags (`EVID`, `WT_CLEAN`,
`e2e_verified`) ENFORCEABLE at runtime instead of self-attested in prose.

## Why this exists

The engine.md disciplines are aspirational by default. A worker that
declares `status: done` in a readiness doc is trusted on its word that
`e2e_verified: true` actually corresponds to a production-grade
end-to-end run. In practice, the second most common failure mode in
fleet runs (after reviewer hallucination, addressed by Commit 1's
schema-verified findings) is **self-attested completion** — the worker
claims done because it INTENDS to be done, not because verifiable
evidence exists.

Strict mode closes that loop. Before any Claude Code worker can end its
session, a Stop hook fires and scans the repo for evidence:

- **EVID=true** in a progress ledger touched in the last 30min
- **WT_CLEAN=true** in a progress ledger touched in the last 30min
- **e2e_verified: true** in a readiness doc touched in the last 30min
- **status: done** in a readiness doc touched in the last 30min
- **A passing verify-summary** from `scripts/verify_findings.py` (Commit 1)
- **Test-runner artifacts** (`.pytest_cache`, `coverage/`, junit XMLs)
  touched in the last 30min
- **End-to-end artifacts** (Playwright PNGs, trace screenshots) touched
  in the last 30min

If none are present, the hook returns `{decision: "block", reason: "..."}`
and Claude Code refuses to end the session. The worker MUST address the
reason before stopping.

## Lineage

The two upstream patterns:

1. **claude-code-orchestra** ships `.claude/hooks/stop-verify.sh` — an
   mtime-window scan for pytest/Playwright artifacts. Returns exit 1 on
   no evidence, exit 0 on found. We borrowed the mtime-window technique
   and the test-artifact list.
2. **multi-llm-plugin-cc** ships `stop-review-gate-hook.mjs` — a fresh
   LLM call that returns `ALLOW: <reason>` or `BLOCK: <reason>` on the
   first stdout line, with the contract bridged into Claude Code's
   `{decision: "block", reason: "..."}` Stop-hook JSON. We borrowed the
   decision-JSON contract and the BLOCK message format.

Composed for autonomous-fleet's specific disciplines because we have a
ledger format (progress.md + readiness.md frontmatter) the upstream
patterns don't have. See
`/workspace/audit-work/borrowable-patterns-report.md` #2 for the audit.

## Install

Strict mode is per-repo, per-worker. You install it once in any repo a
fleet worker will run inside.

### One-time setup

Set `AUTONOMOUS_FLEET_HOME` in the worker's environment to the
autonomous-fleet checkout root:

```bash
export AUTONOMOUS_FLEET_HOME=/path/to/autonomous-fleet
```

This is so the wrapper script can find `scripts/stop_verify.py`. Without
it, the wrapper walks up from its own location (which works when the
wrapper is symlinked).

### Per-repo install

In any repo a worker will run in:

```bash
mkdir -p .claude/hooks
cp "$AUTONOMOUS_FLEET_HOME/skills/autonomous-fleet-core/assets/hooks/stop-verify.sh" \
   .claude/hooks/stop-verify.sh

# Register the hook in .claude/settings.json. If settings.json doesn't
# exist yet, copy the template wholesale:
cp "$AUTONOMOUS_FLEET_HOME/skills/autonomous-fleet-core/assets/hooks/hooks.json" \
   .claude/settings.json

# If settings.json already exists, merge the `hooks.Stop` array. The
# template ships a single Stop entry calling stop-verify.sh.
```

That's it. The next Claude Code session in this repo will run the gate.

## Configuration

The gate is configured via env vars (kept as env, not JSON, so the
config surface survives subprocessing and `.claude/settings.json` schema
drift across CC versions):

| Env var | Default | Effect |
|---------|---------|--------|
| `STOP_VERIFY_WINDOW_MIN` | `30` | Freshness window in minutes. Clamped 1..1440. |
| `STOP_VERIFY_MIN_KINDS` | `1` | Minimum distinct evidence kinds required to allow. |
| `STOP_VERIFY_STRICT_PROGRESS` | unset | When set (any value), require BOTH `EVID=true` AND `WT_CLEAN=true` in a ledger file (in addition to base threshold). |
| `STOP_VERIFY_EXPLAIN` | unset | When set, print human-readable verdict to stderr (visible in CC's hook log). |
| `STOP_VERIFY_DISABLED` | unset | Operator kill switch. When set to `1`/`true`/`yes`, hook returns ALLOW immediately. Use for adapter test harnesses that need to drive sessions without artifact requirements. |

## Discipline levels

Three operating modes, in increasing strictness:

🟢 **Loose mode** (no hook installed) — default. Engine disciplines are
aspirational; worker self-attests via the readiness doc.

🟡 **Strict mode** (`hooks.json` installed, defaults) — at least one
evidence kind in the last 30min, or session refuses to end. Best
default for most operators.

🔴 **Paranoid mode** (`STOP_VERIFY_STRICT_PROGRESS=1`,
`STOP_VERIFY_MIN_KINDS=3`) — both progress flags AND three distinct
evidence kinds required. For high-stakes adapters (production deploys,
financial workflows, anything where a self-attested completion is a
real risk).

## What the worker sees on BLOCK

The CLI emits a structured BLOCK message on stdout (as JSON) and an
identical human-readable form on stderr (with `--explain`). The message:

```
stop-verify: BLOCKED — no fleet-outcome-grade evidence in the last 30min.
  evidence found: no evidence kinds matched
  required: at least 1 distinct kind(s) from {evid_flag, wt_clean_flag,
    e2e_verified, status_done, verify_summary, test_artifact, e2e_artifact}

To unblock:
  - Run the fix's own EVID reproduction (the exact curl/test/script from
    the finding's Evidence block) and set EVID=true in the ledger.
  - Run the test suite end-to-end (pytest / jest / cargo test / go test).
  - Write the readiness doc with `status: done` (and `e2e_verified: true`
    if the mission requires it).
  - Or, for verified review missions, run scripts/verify_findings.py
    --summary-out.

If this is a no-edit turn (status/diagnostic only), set
STOP_VERIFY_DISABLED=1 in the worker env or remove the Stop hook for
that adapter.
```

The first line names the failure mode. The middle lines enumerate the
checks. The "To unblock" section gives the worker a CONCRETE action
list — vague BLOCK messages cause retry loops (the upstream lesson).
The escape hatch is named explicitly so an operator knows how to opt
out of an over-aggressive gate.

## Fail-open by design

The hook NEVER traps a session on internal error. If the CLI crashes,
if Python is missing, if `--repo` is invalid, if stdin is malformed:
the gate ALLOWS and logs a warning to stderr. A broken hook trapping a
worker mid-session is a worse failure than a missed gate.

This means a misconfigured strict-mode install degrades to loose mode
with a warning, not a deadlock.

## What this does NOT do

- **Does not replace** the validate-readiness validator. Schema
  conformance of `fleet-outcome` YAML is still that validator's job.
  The hook only checks "did a readiness doc with `status: done`
  appear in window" — it does NOT validate the YAML inside.
- **Does not replace** Commit 1's verify-findings. Schema-verified
  reviewer findings are still mandatory for review missions. The hook
  CONSUMES a passing verify-summary as evidence, but it doesn't replace
  the verifier itself.
- **Does not enforce** lane-A merge discipline, branch hygiene, or
  any other engine.md rule. Those are still mission-level
  responsibilities; the hook only enforces the three named flags.

The gate is one more layer on top of existing disciplines, not a
replacement for any of them.

## Disabling the hook for one-off sessions

Two ways, in order of preference:

1. `STOP_VERIFY_DISABLED=1` in the worker env — explicit, audit-trail.
2. Move `.claude/settings.json` aside for the session — heavy-handed
   but ensures no hook runs.

Do NOT silently `rm .claude/hooks/stop-verify.sh` — the next operator
won't know strict mode was ever installed.
