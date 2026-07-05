<!-- title: Installation | description: Install autonomous-fleet across all four runtimes, wire up auth, and verify the setup. | sidebar_order: 2 -->

# Installation

The [Quickstart](01-quickstart.md) got you a green PR on Claude Code with the minimum number of
commands. This chapter is the real install: every supported runtime, the auth each one needs,
the optional sandboxing layer, and how to confirm the whole thing actually works before you point
it at a repo you care about.

autonomous-fleet does not ship an agent. It is a library of skills you install **into** a coding
agent you already run. So "installing" is two separate things: getting the skill files onto disk
(`npx skills add`, one command, runtime-agnostic) and making sure the runtime that will read them
is authenticated and has the features the adapter needs (`/goal`, worktrees, `gh`). Most install
problems are the second thing, not the first.

**On this page:** [Prerequisite matrix](#prerequisite-matrix) · [Installing the skills](#installing-the-skills) · [Per-runtime setup](#per-runtime-setup) · [Optional: container-use](#optional-container-use-for-sandboxed-workers) · [Headless mode auth](#headless-mode-auth) · [Verifying the install](#verifying-the-install) · [Where things live](#where-things-live)

## Prerequisite matrix

Three things are required no matter which runtime you pick, plus one per-runtime CLI. autonomous
-fleet ships every unit of work as a GitHub PR, so `git` and an authenticated `gh` are not
optional extras: they are how the framework delivers output.

```
                 ┌──────────────────────────────────────────────────────────┐
  Always needed  │  Node.js >= 18   →  runs `npx skills` (the installer)     │
                 │  git             →  worktrees, branches, commits          │
                 │  gh (authed)     →  every task ships as a GitHub PR        │
                 └──────────────────────────────────────────────────────────┘
                 ┌──────────────────────────────────────────────────────────┐
  Pick one host  │  Claude Code  ·  OpenAI Codex  ·  Grok Build  ·  Orca     │
                 └──────────────────────────────────────────────────────────┘
```

Here is the full matrix, per runtime. "Headless CLI auth" is only needed if you plan to drive
campaigns non-interactively (see [Headless mode auth](#headless-mode-auth)); the interactive chat
path needs only the agent itself.

```
Requirement              Claude Code      Codex            Grok Build       Orca
-----------------------  ---------------  ---------------  ---------------  ----------------
Node.js >= 18            required         required         required         required
git (worktree support)   required         required         required         required
gh CLI, authenticated    required         required         required         required
The agent itself         Claude Code      Codex app/CLI    Grok Build       Orca app
Goal feature             /goal (v2.1.139+) features.goals  /goal + goal     none (ledger-only)
Headless CLI auth        claude on PATH   codex exec       grok login       per-vendor CLI
gitleaks (recommended)   checked at start checked at start checked at start checked at start
container-use (optional) MCP + Docker     MCP + Docker     MCP + Docker     n/a
```

A few things worth calling out before you start:

- Node 18 is the floor because `npx skills` (the [agentskills.io](https://agentskills.io/)
  installer) needs it. The skill files themselves are plain markdown; the version gate is the
  installer, not the framework.
- `gh auth status` must pass. Every adapter's PRECONDITIONS block checks it. If `gh` is not
  authenticated, the framework degrades to local merge-commits into your base branch instead of
  opening PRs, which is almost never what you want.
- `gitleaks` is checked at start by every adapter but is not hard-required. If it is missing, the
  run still proceeds; if it is present, secret-scanning runs as part of the discipline.
- Orca is the one runtime with no `/goal` API. Its adapter maps the goal primitives to the file
  ledger only, and the coordinator's `check --wait` loop is the enforcement harness instead. You
  lose nothing structural, the mechanism is just different.

## Installing the skills

This step is identical across all four runtimes. The skill files land in `.agents/skills/`, which
every supported host reads, so you install once and pick the host later.

There are three ways to install, in increasing breadth.

### Targeted install (recommended)

Install exactly the skills you need. This is what the Quickstart ran, with one adapter swapped per
your runtime. Run this **in a terminal, in your project's root directory**:

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-claude-code \
  --skill doc-sync \
  -y
```

Swap the adapter line for your runtime: `autonomous-fleet-adapter-codex`,
`autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-orca`. You always want the four
infrastructure skills (`setup-autonomous-fleet`, `autonomous-fleet`, `autonomous-fleet-core`, plus
one adapter) and at least one mission (`doc-sync` is the gentlest starting mission). Add
`fleet-program` if you intend to chain missions into a campaign.

### Every skill at once

If you want the whole library, including every mission and every adapter, use the `'*'` glob:

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet --skill '*' -y
```

The quotes matter: your shell will try to expand a bare `*` against the current directory. With
quotes, the literal `*` reaches the installer, which expands it against the repo's skill set.

### From a local clone

If you have cloned the repo (because you are developing the framework, or you want to pin a
specific commit), there is a wrapper script that pins the installer version for supply-chain
integrity:

```bash
./scripts/install-skills.sh                       # starter set
./scripts/install-skills.sh --all                 # every fleet skill
./scripts/install-skills.sh doc-sync test-coverage # named skills
```

The starter set is umbrella + `setup-autonomous-fleet` + `fleet-program` + core + the Grok adapter + `doc-sync` (six skills). The script
pins the `skills` CLI to a known version rather than fetching whatever is latest, which an
unpinned `npx skills` would do. Bump that pin deliberately when you want a newer installer.

> The wrapper installs with the `-p` flag (project scope) so the skills land in the repo's
> `.agents/skills/`, not a global location. If you install by hand with `npx skills add` and want
> the same project scoping, add `-p` yourself.

### What gets installed

The library has twelve top-level skills. Four are infrastructure, five are adapters (one per
runtime plus a template), and three are shipped missions:

```
Infrastructure                        Adapters                              Missions
--------------------------------      --------------------------------      -------------------------
autonomous-fleet (umbrella)           autonomous-fleet-adapter-claude-code  doc-sync
autonomous-fleet-core (engine)        autonomous-fleet-adapter-codex        test-coverage
fleet-program (campaigns)             autonomous-fleet-adapter-grok         adversarial-review-and-fix
setup-autonomous-fleet (config)       autonomous-fleet-adapter-orca
                                      autonomous-fleet-adapter-template
```

You never invoke the infrastructure skills directly. The umbrella routes vague requests to a
mission; `autonomous-fleet-core` is the engine every run loads automatically; `fleet-program`
chains missions; `setup-autonomous-fleet` is the one-time config wizard you run next. Pick exactly
one adapter for your runtime. The `template` adapter is only for people adding a new runtime (see
[Extending](13-extending.md)).

## Per-runtime setup

The skill files are now on disk. What differs per runtime is which CLI mechanics the adapter maps
the engine onto, and what each host needs enabled. Read the section for your host; skip the rest.

After the per-runtime steps below, every runtime runs the same one-time config wizard:

```
/setup-autonomous-fleet
```

In Claude Code and Codex that is a slash command. In Grok and Orca, which do not have slash UIs,
paste the skill name as a natural-language instruction and the runtime routes by name. Either way
the wizard walks you through three decisions (runtime adapter, branch prefix, default campaign
bundle) and writes the config to your repo. Full coverage of what the wizard does is in
[Verifying the install](#verifying-the-install) below.

### Claude Code (the most-supported runtime)

Claude Code is the runtime the framework exercises most. The coordinator **is** the main Claude
Code session: there is no separate orchestration daemon, so the file ledger is the durable source
of truth and `TodoWrite` is the live mirror.

Requirements:

- Claude Code installed and authenticated.
- The `Task` tool (subagents), git worktree support, and `gh` on PATH. The adapter checks these at
  start with the `Bash` tool.
- For runtime goals: Claude Code v2.1.139 or later exposes `/goal`, a Stop-hook evaluator that
  runs after each turn. It requires the trust dialog and is unavailable if `disableAllHooks` is
  set.

Claude Code has three capability tiers, detected once at start and recorded in `DECISIONS.md`:

```
TEAMS tier      CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1   native SendMessage, idle notifications,
                                                         shared task list with dependency tracking
SUBAGENT tier   default                                  foreground/background subagents via the
                                                         Task tool; native blocking WAIT
INBOX fallback  teams off AND background tasks disabled  file markers under docs/.inbox/
```

You do not pick the tier; the adapter detects it. The file ledger stays the cross-turn authority
in every tier because the shared task list is per-session and its status can lag. If you want the
richest experience (native blocking message queues between agents), set
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in your environment or `settings.json` before the run.

Claude Code is also the only runtime that ships the optional [strict mode](11-strict-mode.md) Stop
hook, the reference implementation of the engine's runtime enforcement gate. The hook assets live
in the adapter at `assets/hooks/stop-verify.sh` and `assets/hooks/hooks.json`. It is opt-in and
fail-open: a broken gate degrades to loose mode rather than trapping a worker. Installing it is a
separate step covered in chapter 11; you do not need it to run your first mission.

Configure the repo:

```
/setup-autonomous-fleet
```

### OpenAI Codex (app, IDE, or CLI)

Codex works from the app, the IDE extension, or the CLI. As with Claude Code, the coordinator is
the main thread and workers are subagents or shell-driven sessions in git worktrees. The file
ledger survives compaction and is the durable source of truth.

Requirements:

- Codex installed and authenticated (app, IDE, or CLI).
- git worktree support and `gh` on PATH.
- The `goals` feature enabled, which `SET_GOAL` depends on. If `/goal` is missing in your session,
  enable it:

```bash
codex features enable goals
```

Or set `features.goals = true` in `config.toml`.

One important Codex-specific behaviour: `/goal` works in the interactive thread composer (pair it
with `/plan` when scope is ambiguous), but the headless path is different. `codex exec`, the
unattended subcommand the headless runner uses, is single-shot and does **not** interpret slash
commands. A `/goal ...` string in an `exec` prompt is inert text, and `exec` runs exactly one turn
then stops. For headless Codex there is no native goal/continuation harness; you drive continuation
with an external loop that re-invokes `codex exec` until the ledger's done condition holds. This is
why the interactive path is the supported one (more on headless below).

Configure the repo:

```
/setup-autonomous-fleet
```

### Grok Build

Grok Build runs the coordinator as the main session, with workers as subagents (via the `Task`
tool) or shell-driven worktree sessions. No orchestration daemon, so the file ledger is the
authority across turns.

Requirements:

- Grok Build installed and authenticated.
- The `Task` tool, git worktree support, and `gh` on PATH. The adapter checks these with the
  `Shell` tool at start.
- The goal feature enabled. Grok exposes goal mode via `/goal` and the `update_goal` tool.

Grok's setup has one runtime quirk worth knowing before you spawn workers. If you pass an explicit
model with `-m <model>`, use an id the installed `grok` actually accepts. The literal
`composer-2.5-fast` is rejected as unknown by current builds, so do not hard-code it. The safest
default is to let the host pick its default Grok model unless your mission specifies otherwise.

Because Grok has no slash UI everywhere, invoke setup by name rather than as a slash command:

```
setup-autonomous-fleet
```

Paste that as a natural-language instruction. The runtime routes by skill name.

### Orca

[Orca](https://www.onorca.dev) is the one runtime with a real external orchestration daemon, so
its adapter maps the engine primitives onto actual `orca orchestration` CLI commands rather than
in-session subagents.

Requirements:

- Orca installed, with Settings → Experimental enabled (the orchestration experimental flag must
  be on).
- `orca status --json` must show a running runtime.
- `gh` authenticated, git, and `gitleaks` availability checked at start.

Orca differs from the other three in two ways you should know up front:

- There is no `/goal` API. The goal primitives map to the file ledger only: `SET_GOAL` writes a
  `## Runtime goal` block, and the coordinator's `check --wait` loop is the enforcement harness.
- The default cross-vendor role staffing is baked into the adapter: `@codex` builds, a fresh
  build-blind `@claude` reviews, `@claude` integrates, and `@grok` builds design missions. A
  mission's role pipeline can override this.

One subtlety on the build CLI: the headless builder uses `codex exec` (the headless subcommand),
not `codex --full-auto`. The bare `--full-auto` flag is rejected by current Codex as an invalid
top-level flag. The adapter is written to try one CLI syntax and fall back to another rather than
hard-failing on a single form, because Orca's CLI shifts across versions.

Invoke setup by name (Orca has no slash UI):

```
setup-autonomous-fleet
```

## Optional: container-use for sandboxed workers

By default, an independent worker gets its own git worktree on the host: a real checkout on its own
branch. If you want stronger isolation, each worker can instead run inside its own
[container-use](https://github.com/dagger/container-use) environment: an isolated container plus
branch plus sandbox, so the worker's commands run inside a Linux container rather than directly on
your host.

This is opt-in and requires Docker. Register the MCP server for your runtime:

```bash
# Claude Code
claude mcp add container-use -- container-use stdio

# Codex
codex mcp add container-use -- container-use stdio

# Grok
grok mcp add container-use -- container-use stdio
```

Once registered, the `PLACE(independent)` primitive may use a container-use environment instead of
a host `git worktree`. The canonical placement loop (spawn / inspect / open-PR / cleanup / fallback)
lives in `engine-workers.md` under `CONTAINER-USE-PLACEMENT`.

Current verification status, straight from the adapters, because honesty matters more than a clean
table:

```
Runtime       container-use status
------------  --------------------------------------------------------------------------
Claude Code   verified end to end on a live host (container-use v0.4.2 + Docker); commands
              run INSIDE the container (uname reports Linux, not the macOS host)
Codex         verified on a live host: a `codex exec` worker created an isolated `ubuntu`
              container on its own branch container-use/<env>
Grok          registration verified on host; a full live run is gated by Grok's own auth
              (headless Grok hits Auth(AuthorizationRequired)). Exercise once grok login
              is configured. The engine and loop are proven on Claude Code and Codex.
Orca          n/a (Orca uses its own worktree/terminal isolation model)
```

> If you are running on a repo you do not fully trust, container-use placement is the right tool.
> It is also the placement [Safety and secrets](12-safety-and-secrets.md) recommends for any run
> that touches untrusted input. You do not need it for a first run on your own repo.

## Headless mode auth

Everything above assumes you drive the framework interactively: you talk to your agent in its chat
and it spawns workers. That is the supported path today. There is a second path, headless, that you
only need if you want to run campaigns unattended from a script.

The headless campaign scripts (`scripts/run-campaign.sh`, `scripts/run-mission-headless.sh`) drive
each runtime's CLI in headless mode. That requires the CLI to be authenticated on the host
**separately** from your interactive session. Concretely:

```bash
# Grok headless needs the CLI logged in:
grok login

# Claude headless needs `claude` on PATH and authenticated.
# Codex headless uses `codex exec`, which must be authenticated; it is single-shot
# (one turn per invocation), so continuation needs an external loop.
```

The headless invocation looks like this (per runtime, from `run-mission-headless.sh`):

```bash
./scripts/run-mission-headless.sh grok doc-sync --max-turns 50
./scripts/run-mission-headless.sh claude fleet-program
./scripts/run-mission-headless.sh codex test-coverage --max-turns 60
```

Note that `--max-turns` applies to Grok and Codex only; Claude Code has no `--max-turns` flag and
the script accounts for that. The `--yolo` flag (Grok only) auto-approves all tool calls and is a
full RCE surface against the target repo; never use it on untrusted input, and never use it at all
unless you understand exactly what it disables. [Safety and secrets](12-safety-and-secrets.md)
covers `--yolo` in full.

> Honest caveat: headless campaign mode is **not yet fully validated end to end**. The campaign
> scripts work mechanically, but the unattended CLI-auth path has not been proven across a full run
> on every runtime. If a headless run cannot authenticate, drive the same missions interactively
> from your agent's chat (the `/goal` path). The interactive path is the supported flow today. This
> caveat is tracked in [Campaigns](10-campaigns.md) and [Safety and secrets](12-safety-and-secrets.md).

## Verifying the install

Two checks confirm the install: the config wizard ran cleanly, and a dry-run campaign plans
without errors.

### Run the config wizard

```
/setup-autonomous-fleet
```

(In Grok and Orca, paste `setup-autonomous-fleet` as a natural-language instruction.)

The wizard is prompt-driven and walks three decisions one at a time, then writes config. Here is
what it does, in order:

```
1. Explore     reads git toplevel, remote, default branch, existing CLAUDE.md / AGENTS.md,
               docs/agents/fleet-config.md, DECISIONS.md, installed skill dirs, gh auth status
2. Decide      Section A: runtime adapter   (Grok / Claude Code / Codex / Orca)
               Section B: branch prefix      (default derives from git user.name, else fleet/)
               Section C: default bundle      (repo-health / ship-with-proof / align-then-ship /
                                               quality-gate / none)
               Section D: community skills    (optional; install per bundle, with your consent)
3. Confirm     shows you a draft of docs/agents/fleet-config.md and the `## Autonomous fleet`
               block before writing anything
4. Write       writes docs/agents/fleet-config.md, updates the `## Autonomous fleet` block in
               CLAUDE.md (or AGENTS.md), appends a one-line record to DECISIONS.md
5. Install     installs any missing fleet skills (or prints the install commands)
6. Verify      suggests the dry-run below
```

The wizard never installs community skills without your consent, and it never writes config without
showing you the draft first. If you want to understand the wizard's internals (what it reads, the
exact template it writes), that is covered in [Extending](13-extending.md).

After the wizard, you should have these files in your repo:

```
docs/agents/fleet-config.md      per-repo fleet config (coordinators read this at orientation)
DECISIONS.md                     one-line setup record: adapter, prefix, bundle, date
CLAUDE.md or AGENTS.md           a `## Autonomous fleet` block (in-place, no duplicates)
```

Coordinators read `docs/agents/fleet-config.md` during self-orientation and override engine
defaults with whatever it records. Re-run the wizard whenever you change adapter, branch prefix, or
default bundle.

### Dry-run a campaign

A dry-run plans a campaign without invoking any agents, which is the cheapest way to confirm the
whole chain resolves. Use the runtime and bundle the wizard recorded:

```bash
./scripts/run-campaign.sh claude --preset repo-health --dry-run
```

Swap `claude` for `grok`, `codex` per your runtime, and `repo-health` for whichever bundle you
chose. The three shipped presets are `repo-health` (doc-sync then test-coverage),
`ship-with-proof` (review-fix then test-coverage then doc-sync), and `quality-gate` (review-fix
then test-coverage). Other preset files exist under `scripts/campaigns/` but are archived pending
promotion of the missions they reference; [Campaigns](10-campaigns.md) covers which are live.

If the dry-run prints a plan without erroring, your install is sound: skills are on disk, the
adapter resolves, and the campaign graph is valid. To actually run something end to end, head to
[Your first mission](03-your-first-mission.md).

### Validate the framework itself

If you cloned the repo and want to confirm the framework's own test suite and validators pass
(useful if you are hacking on it, not just using it):

```bash
./scripts/validate-all.sh
```

That runs the skill validators, the fleet-outcome check, the goal-condition check, the run-archive
validator, and the full pytest suite. You do not need this to use the framework, only to develop
it.

## Where things live

Knowing what is committed and what is generated keeps your `git status` clean and your repo
reviewable.

```
your-repo/
├── .agents/skills/              installed skill copies      ← GITIGNORED (not committed)
├── skills-lock.json             lockfile for `npx skills`   ← COMMIT THIS
├── docs/agents/fleet-config.md  per-repo fleet config       ← commit (it is real config)
├── DECISIONS.md                 setup + run decision log    ← commit
├── CLAUDE.md  /  AGENTS.md      host doc with fleet block   ← commit
└── .fleet/runs/<run_id>/        run archives (per run)      ← appears after your first run
```

The two that matter most:

- `.agents/skills/` is **gitignored**. The repo's `.gitignore` ignores `.agents/` wholesale, so
  the installed skill copies never show up in `git status`. This is deliberate: the skills are a
  dependency, not your source. You reinstall them, you do not commit them.
- `skills-lock.json` **is committed**. It is the lockfile `npx skills` writes, pinning exactly
  which skills at which versions you installed. Committing it means a teammate (or CI) gets the
  same skill set when they reinstall. Treat it like `package-lock.json`.

The run archives under `.fleet/runs/<run_id>/` appear only after you run a mission. Whether to
commit them is a per-repo call; their full anatomy is in [Run-archive anatomy](15-run-archive.md).

One last sanity check on the gitignore. After installing, your `git status` should show
`skills-lock.json` (and the config files the wizard wrote) as the only fleet-related changes. If
you see `.agents/skills/` showing up as untracked, your `.gitignore` is missing the `.agents/`
entry; add it before committing so you do not accidentally check in a few hundred skill files.
## Real-world use cases

### Example — ship-with-proof external repo

`docs/external-dogfood/ship-with-proof-evidence.md` installed skills on a fork of gemoji
(`ravidsrk/gemoji` @ `1541ce9`) before running the `ship-with-proof` campaign.

### Invocation — per-runtime adapter swap

Doc-sync dogfood used Claude Code coordinator + Codex worker (`docs/doc-sync-progress.md` TASK row:
`WORKER=codex(cross-vendor)`). Swap only the adapter skill; engine + mission stay identical.

### Worked example — bootstrap contributor path

```bash
./scripts/bootstrap.sh   # venv + validate-all gate
./scripts/validate-headless.sh
```

Both exit 0 on a clean checkout — installation is validated mechanically before any agent auth.

---

You now have a runtime authenticated, skills on disk, config written, and a clean dry-run. The next
chapter walks a real `doc-sync` run end to end so you can see what a mission actually does to a
repo before you trust it on yours.

← [Quickstart](01-quickstart.md) · [Guide Index](README.md) · [Your first mission](03-your-first-mission.md) →
