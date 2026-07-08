---
title: "FAQ"
description: "Short answers to the ~30 questions people actually ask about autonomous-fleet: installation, choosing a mission, campaigns, safety, model support, cost, commercial use, and how it compares to other frameworks."
sidebar:
  order: 19
---

# FAQ

**On this page:** [Installation](#installation) · [Choosing a mission](#choosing-a-mission) ·
[Resume and recovery](#resume-and-recovery) · [Campaigns](#campaigns) · [Safety](#safety) ·
[Models and runtimes](#models-and-runtimes) · [Cost](#cost) · [Commercial use](#commercial-use) ·
[Comparison](#comparison) · [Limitations today](#limitations-today)

This is the skim-for-an-answer chapter. Each question is one or two paragraphs, with a link to the
chapter that covers it in depth. If a question here contradicts a chapter, the chapter wins: the
chapters are written against the code, this page is a fast index.

Nothing here depends on anything else in the guide. Read it out of order, search it, bookmark it.
## Real-world use cases

### Example — why no live bench numbers yet

`adversarial-bench-2026-06.md` Results section: all targets ⬜ pending — honest PENDING operator
status, not fabricated metrics.

### Invocation — can I run without grok login?

Yes for mechanical paths: `validate-headless.sh`, campaign `--dry-run`, `emit_representative_trace.py`.

### Worked example — marketplace submit still human

`docs/marketplace-submission/README.md`: Console form at platform.claude.com — packet refreshed,
submission PENDING human action (gap G-market).

---

## Installation

### Do I need to install a coding agent separately?

Yes. autonomous-fleet drives _your_ coding agent, it does not ship one. You bring a supported agent
(Claude Code, Codex, Grok, or Orca), installed and authenticated, and the skills route work through
it. Think of the framework as the protocol, your agent as the runtime. See
[Installation](/02-installation/).

### What are the hard prerequisites?

Node.js >= 18 (for the `npx skills` installer), `git`, and an authenticated `gh` (every task ships
as a GitHub PR), plus one supported agent. That is the whole list for the interactive path. See the
prerequisite matrix in [Installation](/02-installation/).

### How do I install just enough to try it?

One `npx skills add` command with five targeted skills (`setup-autonomous-fleet`, `autonomous-fleet`,
`autonomous-fleet-core`, the Claude Code adapter, and `doc-sync`). That is the
[Quickstart](/01-quickstart/). You do not need the full set to ship your first PR.

### How do I install everything?

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet --skill '*' -y
```

The `--skill '*'` glob grabs every skill in the repo. Most people do not need all of them. Install
the missions you will actually run plus the one adapter for your runtime.

### Does installing change my git history?

No. `npx skills add` writes to `.agents/skills/`, which is gitignored, so your `git status` stays
clean. The only tracked file the installer touches is `skills-lock.json`, the lockfile. See "Where
things live" in [Installation](/02-installation/).

### Which adapter do I install?

Exactly one, matching your runtime: `autonomous-fleet-adapter-claude-code`, `-codex`, `-grok`, or
`-orca`. Do not mix adapters in one repo. If you are adding a brand-new runtime, copy
`autonomous-fleet-adapter-template` and fill in the primitives.

### How do I configure it after install?

Run `/setup-autonomous-fleet` in your agent's chat. In Claude Code and Codex it is a slash command;
in Grok and Orca you paste the skill name as a natural-language instruction. It asks which agent you
are on and which branch prefix to use, then writes the config to your repo.

---

## Choosing a mission

### Which mission should I start with?

`doc-sync`. It has the highest merge-success rate of any AI-agent PR category in the AIDev dataset
(per arXiv:2601.15195, Ehsani et al., MSR 2026), which makes it the lowest-risk way to see a real
run end to end. Say "the docs are out of date, fix them" and read the PR it opens. See
[Your first mission](/03-your-first-mission/).

### What missions actually ship today?

Three, proven end to end with run-archives: `doc-sync`, `test-coverage`, and
`adversarial-review-and-fix`. Everything else under `docs/exploratory/missions/` is documented but
exploratory: it lacks the progress + readiness + external-archive triple required to ship. Do not
treat an exploratory mission as production-ready because it has a SKILL.md.

### Why are there exploratory missions if I cannot run them?

They are distilled designs awaiting promotion. The active roster includes `agents-layer`,
`browser-qa-fix`, `bug-batch`, `cleanup`, `contract-first-build`, `dependency-update`,
`design-integration`, `incident-investigate`, `inference-cost`, `scaffold-align`,
`take-product-to-completion`, and `targeted-migration`. Parked designs live under
`docs/exploratory/missions/archive/`. The promotion criteria (the three-artifact rule) live in
`docs/exploratory/missions/README.md`. Documenting a design before it ships is deliberate, not an
oversight.

### Can I run two missions on the same repo at once?

No. One mission is active at a time per repo. Same-repo parallel runs are not supported because they
would race on the file ledger and on branch state. Cross-repo parallel is fine: use a separate
session per repo.

### Do I have to phrase the request exactly right?

No. The umbrella `autonomous-fleet` skill routes a vague request ("fix our README", "raise coverage
on payments") to the right mission. You describe the work; it picks the mission. If you already know
which mission you want, invoke it directly.

### What does a successful run leave behind?

One PR per unit of work (never one giant blob), each with a readiness doc explaining what was done
and how it was verified, plus a `.fleet/runs/<run_id>/` archive if archiving was enabled. The
machine-readable summary is the `fleet-outcome` YAML block. See [Your first mission](/03-your-first-mission/).

---

## Resume and recovery

### A run died halfway. Can I just resume it?

Yes, and resume is the point of the file ledger: a fresh coordinator with zero prior context can pick
a run back up from `.fleet/runs/<run_id>/` alone, because the ledger is authoritative and the
coordinator's memory is not. On resume the coordinator does not blindly continue. It runs the recovery
scanner first to find out which tasks are actually still alive. See [The engine](/06-the-engine/).

### How does recovery decide what to do with each task?

`recovery_scan.py` cross-references three live signals per task row: the markdown progress ledger, the
`git worktree list` output, and the `gh pr list` state. From those it classifies each row as `live`,
`dead`, `partial`, or `orphan`, and attaches one advisory action: `CONTINUE`, `CLEANUP_WORKTREE`,
`RE_DRIVE`, `ESCALATE_TO_DECISIONS`, or `ARCHIVE_ORPHAN`. The word advisory is load-bearing: the
scanner never executes anything and never touches the repo. The coordinator reads the classification
and decides. A row that says merged on the SCM but not in the ledger (or the reverse) is flagged
`partial` and escalated, not silently continued.

### How many times will it retry a stuck task?

Three. A `live` row can be re-attached with `CONTINUE_WORKER` (the optional 14th primitive) instead
of a fresh spawn, but the resume budget is bounded: once a row's `RESUME_COUNT` reaches
`MAX_RESUME_ATTEMPTS` (3), the recovery scanner stops recommending another continue and recommends
`ESCALATE_TO_DECISIONS` instead, so a task that cannot make progress lands in `DECISIONS.md` for a
human rather than looping forever. Adapters whose runtime has no session-restore command alias
`CONTINUE_WORKER` to `SPAWN_WORKER`, so resume still works, it just relaunches instead of re-attaching.

### What happens to a leftover worktree from a dead run?

The recovery scan sweeps for `orphan` worktrees: a worktree on a fleet-prefixed branch with no ledger
row. It only recommends `ARCHIVE_ORPHAN` when the SCM proves the branch merged and the worktree has no
uncommitted changes; otherwise it recommends `ESCALATE_TO_DECISIONS`. It will not clean up a worktree
that still holds unmerged work. See [The engine](/06-the-engine/).

---

## Campaigns

### What is a campaign versus a mission?

A mission is one discrete job. A campaign chains several missions into a DAG with a verification gate
between nodes: if a gate fails, the campaign stops and tells you why. Use `fleet-program` to chain
rather than orchestrating by hand. See [Missions vs campaigns](/05-missions-vs-campaigns/).

### Which campaign presets are shipped?

Three are active: `repo-health` (doc-sync then test-coverage), `ship-with-proof` (review-fix then
test-coverage then doc-sync), and `quality-gate` (review-fix then test-coverage). Run them like:

```bash
./scripts/run-campaign.sh claude --preset repo-health
```

The `secure-ship`, `align-then-ship`, and `handoff-to-product` preset files also exist under
`scripts/campaigns/` but are archived pending promotion of the missions they reference. See
[Missions vs campaigns](/05-missions-vs-campaigns/).

### How do I preview a campaign without running it?

Add `--dry-run`:

```bash
./scripts/run-campaign.sh claude --preset repo-health --dry-run
```

It prints the plan (the node order and gates) without spawning any workers.

### Can I write my own campaign?

Yes, point `run-campaign.sh` at a YAML file with `--campaign PATH` instead of `--preset NAME`. The
gate and conditional-branch schema is covered in the campaigns how-to. Adding a new _preset_ to the
repo itself is a contributor task, not an operator one.

---

## Safety

### Will it run destructive commands on my machine?

By default, no: shell commands go through `scripts/run-sandboxed.sh`, which scrubs credential-shaped
env vars and applies blast-radius limits. The exception is `--yolo`, which auto-approves commands.
Never use `--yolo` on a repo or host you care about. See [Safety and secrets](/12-safety-and-secrets/).

### Does merge mean deploy?

No. Merge is not deploy. Runs target testnet or staging only; shipping a PR to your base branch does
not push anything to production. That separation is a deliberate discipline, not a side effect.

### Can I isolate each worker?

Yes, optionally. With `container-use` placement, each independent worker gets its own Linux
container instead of sharing the host. It is opt-in and adds setup; see the container-use section of
[Safety and secrets](/12-safety-and-secrets/).

### How are secrets handled?

Env vars only, set at runtime, in memory, never written to disk. Workers do not hardcode secrets, and
the sandbox wrapper scrubs credential-shaped variables before running a command. If you ever find a
committed secret, treat it as compromised and rotate it.

### Can I turn off a gate that is blocking me?

Most gates, yes, with a deliberate env var, but think before you do. Escape-hatch knobs
(`FLEET_DISABLE_VERIFY_FINDINGS`, `FLEET_DISABLE_STOP_VERIFY`, `FLEET_DISABLE_BLIND_FIX`,
`FLEET_DISABLE_RUN_ARCHIVE`, `FLEET_DISABLE_ROUND_BUDGET`, and the nudge/stacked-pr/hook-signal
verifiers) exit 0 with a `DISABLED` notice when set truthy. Security/integrity knobs
(`FLEET_DISABLE_SHA_PIN`, `FLEET_DISABLE_REVIEWER_SANDBOX`, `FLEET_DISABLE_NAMESPACING`,
`FLEET_DISABLE_REGISTRY_LINT`) **fail closed**: a bare truthy value is refused unless you also set
`FLEET_SECURITY_OVERRIDE_ACK=1` and record the decision. The mutation gate has no knob on purpose.
See [The substrate](/07-the-substrate/) and [Troubleshooting](/14-troubleshooting/).

### How do I report a vulnerability?

`SECURITY.md` exists in the repo root. Follow its disclosure process: email ravidsrk@gmail.com,
report privately rather than opening a public GitHub issue, and use the 90-day disclosure window.

### What does the framework NOT defend against?

A malicious `--yolo` operator, a compromised upstream agent CLI, and supply-chain attacks on the npm
packages it installs. The sandbox reduces accidental blast radius; it is not a defense against a host
you have already lost control of. See the threat model in [Safety and secrets](/12-safety-and-secrets/).

---

## Models and runtimes

### Does it support GPT-5?

Yes, through the Codex runtime. The default builder staffing is `@codex` (OpenAI Codex / GPT-5). The
framework is model-agnostic: it specifies roles and a protocol, and each adapter maps that protocol
to one runtime's real commands. See [Roles and blindness](/08-roles-and-blindness/).

### Which runtimes are supported?

Four: Claude Code, Codex, Grok, and Orca. Claude Code is the most-supported (it is the only runtime
with the strict-mode stop-verify hook today). Pick exactly one adapter per repo.

### Do I need more than one model family?

No, but you lose something without it. The default topology uses different model families for builder,
reviewer, and integrator so review is not self-marking. If you only have one family, the framework
still enforces terminal separation (the reviewer gets a fresh session with no context inheritance),
but it loses cross-vendor blind-spot diversity. Every run records which mode it ran in via
`fleet-outcome`. See [Roles and blindness](/08-roles-and-blindness/).

### Why is the reviewer "build-blind"?

Because a model that can see its own session will rationalize its own work. The reviewer is spawned
in a separate terminal with no access to the builder's session, scratchpads, or prior context, so it
can only judge the artifact (the diff plus `EVID`), not the intent. This came out of the Aula run and
became a structural rule. See [Roles and blindness](/08-roles-and-blindness/).

### Can I add a runtime that is not in the list?

Yes. Copy `autonomous-fleet-adapter-template` and implement the primitives (`PLACE`, `SPAWN_WORKER`,
`DISPATCH`, `WAIT`, `INSPECT`, `SYNC_TASK_STATE`). The engine stays the same; the adapter is the only
runtime-specific piece. See [Extending](/13-extending/).

---

## Cost

### How much does a run cost?

It depends on scope, but every run reports a `cost_estimate` (USD) in its `fleet-outcome` block, so
the spend is never silent. A small `doc-sync` run is cents; a multi-PR `test-coverage` pass on a
large module is more. The number is an estimate of the underlying model spend, billed by your agent
provider, not by this framework.

### Does autonomous-fleet itself cost anything?

No. The framework is MIT-licensed skills you install for free. Your only spend is the model usage of
whichever agent you run it through, billed by that provider (Anthropic, OpenAI, xAI, etc.).

### How do I keep cost predictable on a headless run?

Cap turns. The headless scripts take `--max-turns`, for example
`./scripts/run-mission-headless.sh grok doc-sync --max-turns 50`, which bounds how long a worker can
run before it stops. Combine that with `--dry-run` on campaigns to see the plan before paying for it.

---

## Commercial use

### Can I use this at work / on a commercial product?

Yes. The repo is MIT-licensed (Copyright 2026 ravidsrk). You can use, modify, and ship it in
commercial projects. Keep the license and copyright notice as MIT requires.

### Can I fork it and change it?

Yes, MIT allows it. If you add a runtime adapter or a mission worth sharing, the contribution path is
in `CONTRIBUTING.md`. Per-skill SKILL.md files are the agent-facing spec; do not duplicate that spec
into a README when you fork.

### Is my code sent anywhere by the framework?

The framework runs locally and talks to GitHub via `gh` and to whichever model provider your agent
uses. autonomous-fleet does not add a telemetry endpoint of its own. Your data goes wherever your
chosen agent provider's terms say it goes, which is between you and that provider.

---

## Comparison

### How is this different from running one coding agent?

A single agent marks its own homework. autonomous-fleet splits each task into builder, reviewer, and
integrator roles in separate terminals (usually separate model families), so a fresh build-blind
agent reviews the diff before you ever see the PR. The other structural differences: one PR per unit,
a frozen scope per run, a file-based ledger that survives restarts, and a four-layer verification
substrate. See [Mental model](/04-mental-model/).

### How is this different from an agent swarm?

The workers are not a homogeneous swarm. They move through a fixed role topology with a frozen plan
and verification gates, not a free-for-all. The framework is the protocol; the agents are
interchangeable parts that plug into it. That is the point of the adapter split.

### Why one PR per unit instead of one PR per run?

So you can review and merge work in small, conflict-aware pieces, the way a senior engineer would,
instead of being handed one giant blob to approve or reject. Original commits are preserved (never
squashed), and worktrees are cleaned up after every merge. See [Mental model](/04-mental-model/).

### Why mutation testing instead of line coverage?

Because a green test suite that does not actually fail when the code breaks is not verification. The
substrate's mutation gate pins known bugs and asserts the tests catch them, which is a stronger
signal than a coverage percentage. The shipped manifest holds 50 mutations today. See the substrate
chapter when it lands.

---

## Limitations today

These are the honest current limits, re-derived against `main`. Read them before you trust the
framework with something that matters.

### Is the trace stream fully wired?

Not yet. The trace schema covers 11 primitives, but in production code today exactly one event is
emitted: `T-FINAL`, from `fleet_run.write_manifest` (correctly emitted before the manifest write, per
the trace-first doctrine). The stream is intentionally sparse while per-transition emission rolls out
across the coordinator and adapters. If you are building a dashboard, design against the full schema
but expect a sparse stream today. See [Trace schema](/16-trace-schema/) when it lands.

### Is headless campaign mode production-ready?

Not fully. The campaign scripts (`run-campaign.sh`) drive each runtime's CLI in headless mode, which
requires that CLI to be authenticated on the host and is not yet fully validated end to end with
live agent sessions in CI. Mechanical paths are gated: `validate-headless.sh`, fake-runtime pytest
(`tests/test_headless_trace.py`, `tests/test_run_campaign.py`), and archive emission under `--repo`.

**Orca is interactive-only** — use the Orca app with `autonomous-fleet-adapter-orca` and `/goal`;
`run-campaign.sh` does not accept `orca` as a runtime.

The supported path today for production work is interactive: drive missions from your agent's chat
/ `/goal`. If a headless run cannot authenticate, fall back to the interactive flow. See
[Safety and secrets](/12-safety-and-secrets/).

---

← [CLI reference](/18-cli-reference/) ·
[📖 Guide Index](/) ·
[Glossary](/20-glossary/) →
