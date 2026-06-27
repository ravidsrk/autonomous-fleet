---
title: "Quickstart"
description: "Install autonomous-fleet, run your first mission, and watch the PR land in about 10 minutes on Claude Code."
sidebar:
  order: 1
---

# Quickstart

You describe the work. A team of AI agents ships the PRs. This page gets you from a clean repo to
your first merged-ready pull request in about ten minutes, on a single runtime (Claude Code), with
a single mission (`doc-sync`). No campaigns, no concepts, no internals. Just the shortest path to
seeing the framework do something real on your own repo.

**On this page:** [Prerequisites](#prerequisites) · [Install](#install) · [Configure](#configure) ·
[Run](#run) · [What just happened](#what-just-happened) · [Next steps](#next-steps)

> autonomous-fleet drives _your_ coding agent. It does not ship one. Everything below assumes you
> already have Claude Code installed and authenticated. If you use Codex, Grok, or Orca instead,
> finish this page conceptually then read [Installation](/02-installation/) for the per-runtime
> details. The flow is the same; only the adapter skill and the chat-invoke step differ.

## Prerequisites

Four things, all of which you very likely already have if you write code on GitHub:

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. A supported agent      Claude Code, installed and authenticated  │
│  2. Node.js >= 18          for `npx skills` (the agentskills.io CLI) │
│  3. git                    every run works on git branches           │
│  4. gh, authenticated      every task ships as a GitHub pull request │
└─────────────────────────────────────────────────────────────────────┘
```

Check all four in one go:

```bash
node --version          # want v18 or newer
git --version           # any recent version
gh auth status          # want "Logged in to github.com"
```

If `gh auth status` reports you are not logged in, fix that first. Every mission opens its work as a
GitHub PR, so an unauthenticated `gh` means the run has nowhere to land its output:

```bash
gh auth login
```

One more thing: run all of this from inside a real git repository you do not mind getting a small
documentation PR against. A repo with a slightly stale `README.md` is the ideal first target,
because that is exactly what `doc-sync` is built to fix.

## Install

From the root of your project, install the starter set of skills. This is one command. It pulls the
umbrella router, the engine, the Claude Code adapter, and the `doc-sync` mission:

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-claude-code \
  --skill doc-sync \
  -y
```

This creates a `.agents/skills/` folder in your repo. That folder is gitignored, so your
`git status` stays clean. The format is the universal [agentskills.io](https://agentskills.io/)
standard, which Claude Code, Grok, Codex, and Orca all read from the same place.

> Using a different agent? Swap `autonomous-fleet-adapter-claude-code` for `-grok`, `-codex`, or
> `-orca`. Want every skill at once, including the other missions? Use `--skill '*'` instead of the
> individual `--skill` flags. The full breakdown is in [Installation](/02-installation/).

That is the whole install. There is nothing to compile and no server to start. The skills are just
markdown and a handful of Python helper scripts that your agent reads as context.

## Configure

The skills are on disk, but the framework does not yet know anything about _this_ repo: which
runtime you are on, what branch prefix to use, or which campaign bundle to suggest when your
request is vague. The setup skill captures that, once.

In Claude Code's chat panel, invoke the setup skill as a slash command:

```
/setup-autonomous-fleet
```

> In Claude Code and Codex, `/setup-autonomous-fleet` is a slash command. In Grok and Orca, which
> do not have a slash UI, paste the skill name as a plain natural-language instruction instead. Both
> routes do the same thing: the skill reads your repo's config.

The skill walks you through three decisions, one section at a time, each with a sensible default you
can accept by pressing enter:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  A. Runtime adapter   Which host runs the coordinators?                    │
│                       → Claude Code (you picked this in Install)           │
│                                                                            │
│  B. Branch prefix     Missions branch as <prefix><task-slug>.              │
│                       → default: `fleet/` or your slugified git user.name  │
│                                                                            │
│  C. Default bundle    Which campaign to suggest when intent is vague.      │
│                       → default: `repo-health`                             │
└──────────────────────────────────────────────────────────────────────────┘
```

It shows you a draft before writing anything. When you confirm, it writes
`docs/agents/fleet-config.md`, adds a `## Autonomous fleet` block to your `CLAUDE.md` (or
`AGENTS.md` if you have no `CLAUDE.md`), and appends a one-line record to `DECISIONS.md`. Nothing is
written until you say so. For the quickstart, accept every default. You are configuring Claude Code,
the `fleet/` prefix is fine, and you will not be running a campaign here.

## Run

Now the part you came for. In the same chat, describe the work in plain English:

```
The docs are out of date, fix them
```

That is it. You do not name a mission, pass a flag, or write a config file. The umbrella skill reads
your request, recognises it as a documentation-truth job, and routes it to `doc-sync`. Here is what
you will see, in order:

```
   you: "The docs are out of date, fix them"
        │
        ▼
   ┌────────────────────────────────────────────────────────────┐
   │ 1. A PLAN is written to a file you can read.                │
   │    Read it. If you do not like the scope, abort here.      │
   └────────────────────────────────────────────────────────────┘
        │
        ▼
   ┌────────────────────────────────────────────────────────────┐
   │ 2. WORKER AGENTS are spawned (you see them start up).      │
   │    A builder writes the fix on a fresh worktree, a         │
   │    build-blind reviewer reads only the diff, an            │
   │    integrator merges and cleans up.                        │
   └────────────────────────────────────────────────────────────┘
        │
        ▼
   ┌────────────────────────────────────────────────────────────┐
   │ 3. PULL REQUESTS appear in GitHub as each piece finishes,  │
   │    usually within a few minutes. One PR per stale doc.     │
   └────────────────────────────────────────────────────────────┘
```

Each PR carries a readiness doc explaining what was changed, why, and how it was verified. A
_different_ agent than the one that built it has already signed off on the review before you ever
see the PR. You are the final reviewer; the first reviewer was a fresh, build-blind agent that never
saw the builder's session.

To stop a run mid-flight, close the chat. The workers check in with the file ledger and exit
cleanly. The ledger survives on disk, so you can resume in a new chat instead of starting over.

> This quickstart uses the interactive chat path, which is the supported flow today. There is also a
> headless campaign runner (`run-campaign.sh`) for scripting missions from a terminal, but it is not
> yet fully validated end-to-end and needs your runtime's CLI authenticated on the host. Stick to
> chat for your first run. See [Installation](/02-installation/) for the headless caveat.

## What just happened

You typed one sentence and got real pull requests. Under that sentence, a small team of agents ran
a disciplined engineering loop:

```
   describe work  ──►  freeze a plan  ──►  build on branch  ──►  blind review  ──►  open PR
        (you)            (coordinator)        (builder)          (reviewer)      (integrator)
```

Three things are worth noticing on this first run:

A frozen plan came first. The coordinator wrote the scope to a file before any code changed, so the
run cannot quietly expand past what you approved. That plan file is your abort button.

Review was structural, not polite. The reviewer ran in a separate terminal with no access to the
builder's session, scratchpads, or context. It could only judge the artifact, the diff plus the
evidence, never the builder's intent. That separation is the whole point: an agent cannot mark its
own homework when it has never seen the homework being done.

Every run left a trail. The work landed as one PR per unit, each with a readiness doc, not one giant
unreviewable blob. If your run wrote a `.fleet/runs/<id>/` archive, that directory is the audit
trail for exactly what the fleet did and why.

> One honest caveat about observability today: the framework defines a rich structured trace stream
> (eleven primitives, a full event schema), but in production code only a single terminal event,
> `T-FINAL`, is wired today. Per-transition emission is rolling out. So if you go looking for a
> live, step-by-step event feed of this run, you will find the contract and the final event, not yet
> the full stream. The PRs and the readiness docs are the real-time signal for now.

If a PR did not appear, the usual cause is `gh` not being authenticated, or the repo having no docs
actually out of sync (an empty diff is a valid, honest result, not a failure). Re-check
`gh auth status` and try a repo with a genuinely stale `README.md`.

## Next steps

You have seen _what_ a run feels like. Next, learn _why_ it works the way it does:

- [Mental model](/04-mental-model/): what a "run" actually is. A frozen plan, a worker fleet, and
  an audit trail. This is the chapter that makes the rest of the guide click.

And to go wider before you go deeper:

- [Installation](/02-installation/): set up the other three runtimes (Codex, Grok, Orca), pick the
  right one for real work, and understand the headless-mode auth requirements.
- [Your first mission](/03-your-first-mission/): the same `doc-sync` run, but walked through
  line by line, including every file that appears in the run archive.
## Real-world use cases

### Example — doc-sync on autonomous-fleet README

Real run on `ravidsrk/autonomous-fleet`: `docs/doc-sync-progress.md` records a single serialized
unit touching `README.md` after grep confirmed scripts/ layout drift (`run-sandboxed.sh`,
`coupling-graph.py`, `render-dashboard.py` missing from docs).

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet   --skill doc-sync -y
# then invoke doc-sync in Claude Code against a stale README
```

### Invocation — headless dry-run before first live run

Mechanical preview (no runtime auth) from this repo:

```bash
./scripts/run-mission-headless.sh grok doc-sync --dry-run
```

Stdout contains `would run:` and `grok not invoked` — the wiring check from `validate-headless.sh`.

### Worked example — fixture archive as proof shape

`.fleet/runs/example-fixture/manifest.json` lists nine archived files; `trace.jsonl` has eleven
events (all trace primitives). Same directory layout a live mission produces, with a complete
mechanical trace for validators.

---

← [Prev: README](/) · [Guide Index](/) · [Next: Installation →](/02-installation/)
