# autonomous-fleet

A portable framework for running fully-autonomous multi-agent engineering jobs — **across
orchestration tools, not just one.** A tool-agnostic **core** holds all the method; thin
**mission** skills describe specific jobs; per-tool **adapters** map the method to each runtime's
real commands.

Write the mission once. Run it on any supported tool. Fix the method once; every mission and every
tool inherits the fix.

---

## The idea

Most "autonomous coding" setups bolt the *method* (how you decompose, gate, review, merge) directly
onto one tool's *mechanics* (its dispatch commands, its worktree model). Change tools and you
rewrite everything. `autonomous-fleet` separates them:

```
autonomous-fleet/
├── core/
│   ├── autonomous-fleet-core.SKILL.md        ← THE METHOD (tool-agnostic). Speaks in PRIMITIVES.
│   └── missions/                             ← 11 jobs. Each loads the core + an adapter.
│       ├── doc-sync.SKILL.md                       Tier 1
│       ├── test-coverage.SKILL.md                  Tier 1
│       ├── dependency-update.SKILL.md              Tier 1
│       ├── cleanup.SKILL.md                        Tier 1
│       ├── bug-batch.SKILL.md                      Tier 2  (reproduce-first gate)
│       ├── adversarial-review-and-fix.SKILL.md     Tier 2  (two-phase workhorse)
│       ├── targeted-migration.SKILL.md             Tier 2
│       ├── design-integration.SKILL.md             Tier 2
│       ├── landing-page-convergence.SKILL.md       Tier 2
│       ├── legacy-rebuild.SKILL.md                 Tier 3
│       └── take-product-to-completion.SKILL.md     Tier 3
└── adapters/
    ├── orca/autonomous-fleet-adapter-orca.SKILL.md            ← Orca binding (full)
    ├── claude-code/autonomous-fleet-adapter-claude-code.SKILL.md ← Claude Code binding
    ├── grok/autonomous-fleet-adapter-grok.SKILL.md            ← Grok Build binding
    └── autonomous-fleet-adapter-TEMPLATE.SKILL.md             ← write a new tool's binding
```

**Core + Mission + Adapter = a run.** The core calls primitives (spawn worker, dispatch, wait,
inspect, place work, open/merge PR, sync state); the active adapter resolves each primitive to its
tool's real commands. The missions never mention a tool.

---

## Supported runtimes

| Adapter | Runtime | Concurrency model |
|---------|---------|-------------------|
| **orca** | [Orca](https://www.onorca.dev) orchestration | Persistent orchestration daemon; worktrees + terminals; `check --wait` supervision |
| **claude-code** | Claude Code | Coordinator is the main session; workers are subagents (Task tool) + worktree sub-sessions; file ledger is the authority, TodoWrite mirrors it |
| **grok** | Grok Build | Coordinator is the main session; workers are subagents (Task tool) + worktree sub-sessions; file ledger is the authority |
| **TEMPLATE** | any (codex, gemini-cli, raw CLIs, …) | copy the template, implement the primitives |

To add a tool: copy `adapters/autonomous-fleet-adapter-TEMPLATE.SKILL.md`, fill in how that runtime
implements each primitive. The core and all 11 missions stay untouched.

---

## Risk tiers (why they're labelled)

From the MSR 2026 study of ~33,000 real agent-authored pull requests — merge rate by task type. The
library encodes that so you know where to trust autonomy. Every serious source agrees: **start on
low-risk, high-volume work and expand as confidence grows.**

| Tier | Meaning | Missions | Approx. merge rate |
|------|---------|----------|--------------------|
| **1** | High autonomous success — run unattended | doc-sync, test-coverage, dependency-update, cleanup | 0.84–0.92 |
| **2** | Moderate — full review gate, glance at the control artifact | bug-batch, adversarial-review-and-fix, targeted-migration, design-integration, landing-page-convergence | 0.80–0.82 |
| **3** | High blast radius — review the frozen scope/architecture artifact, expect rework | legacy-rebuild, take-product-to-completion | ~0.80 |

Baked-in consequences of the data:
- **doc-sync** and **test-coverage** are the highest-success categories — the safest starting points.
- **bug-batch** is Tier 2, not Tier 1, because bug-fixes need *exact* (not approximate) changes —
  so it **requires a failing test that reproduces the bug before any fix.**
- **No standalone performance mission** — performance is the worst category (~0.68); keep it
  human-gated.

---

## Install

These are skills in the format `<name>/SKILL.md` (or as shipped, `<name>.SKILL.md` so they can
share one folder). Install the **core**, the **missions**, and the **adapter(s) for the tools you
use**, each as its own `SKILL.md` under wherever your tool reads skills from.

Minimum to run on Orca:
```
<skills-dir>/autonomous-fleet-core/SKILL.md
<skills-dir>/autonomous-fleet-adapter-orca/SKILL.md
<skills-dir>/doc-sync/SKILL.md        (and any other missions you want)
```
For Claude Code, install `autonomous-fleet-adapter-claude-code` instead of (or alongside) the Orca
adapter. For Grok Build, install `autonomous-fleet-adapter-grok`.

At run start the core derives `BRANCH_PREFIX` (default `fleet/`, or slugified from the maintainer's
git user.name) and ensures `docs/` exists for mission ledgers — both recorded in `DECISIONS.md`.

If you downloaded the bundle with prefixed filenames, rename each to `SKILL.md` inside its own
directory (e.g. `mv doc-sync.SKILL.md doc-sync/SKILL.md`), or recreate the directory layout shown in
"The idea" above.

---

## Use

1. Open the repo you want to work on (skills resolve the target from your current directory — no
   paths to fill in).
2. Make sure the **core** and the **adapter for your current tool** are installed, plus the mission
   you want.
3. Trigger the mission in plain language — *"sync the docs," "raise test coverage on payments,"
   "adversarial review and fix this app," "take this product to the finish line."* The mission's
   `description` triggers on those phrasings.
4. The mission loads `autonomous-fleet-core` + your tool's adapter and runs fully autonomously:
   resolves the repo and maintainer, plans, spawns workers, runs the PR-per-task pipeline (build →
   review → conflict-aware merge → checkout cleanup), and reports once at the end.

You are asked to step in only for the single final report — or, for the few missions with a **hard
external dependency** (e.g. `design-integration` using the `claude_design` MCP connector, which may
need `/design-login`), that one authorization an agent cannot self-grant.

---

## What every run guarantees (tool-independent)

- **No placeholders** — repo and maintainer discovered, not filled in.
- **One PR per unit**, commits preserved (never squashed), authored by the real maintainer, no
  agent/tool trailers.
- **Conflict-aware merges** — rebase onto BASE, resolve, re-test green, re-review if logic changed,
  then merge. Never a forced merge over conflicts or a red suite.
- **Checkout cleanup** on every merge.
- **Safety rails** — nothing touches real funds/keys/prod; merging is not deploying; infra is merged
  as code, applied by humans as ops.
- **A readiness doc** at the end, plus a single completion report.
- **Survives compaction** — the file ledger is the durable source of truth; a fresh coordinator
  resumes from it.

---

## Notes

- **Adapter parity:** the Orca adapter is the most battle-tested (it encodes a long sequence of
  hard-won fixes — worker placement, conflict resolution, version-tolerant completion, the
  file-ledger gates). The Claude Code adapter follows the same contract but its concurrency model
  differs (subagents + ledger-polling instead of a daemon); validate it on a Tier-1 mission before
  trusting it on Tier-3 work.
- **Referencing vs self-contained:** missions are written to *reference* the core and an adapter.
  Confirm your runtime actually loads referenced skills when a mission fires. If it does not chain
  skills, inline the core + adapter bodies into each mission (identical content; only packaging
  changes). Test on one Tier-1 mission first.
- **Origin:** this is the distillation of a long session hardening one orchestration prompt across
  many real jobs. The method (self-orientation, file-ledger boolean gates, frozen-artifact-then-
  execute, conflict-aware PR-per-task, the worker-placement logic) was each learned the hard way;
  the tiers and the bug-batch reproduce-first gate are grounded in the MSR 2026 study rather than
  intuition. Separating method from mechanics is what makes it portable across tools.
