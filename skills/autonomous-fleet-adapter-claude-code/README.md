<!-- title: Adapter, Claude Code | description: Maps autonomous-fleet engine primitives to Claude Code mechanics (Task-tool subagents, git worktrees, gh CLI, TodoWrite). | sidebar_order: 8 -->

# autonomous-fleet-adapter-claude-code

**On this page:** [When to use it](#when-to-use-it) · [What it produces](#what-it-produces) ·
[What it expects](#what-it-expects-from-your-repo) · [Common failure modes](#common-failure-modes) ·
[Quick install](#quick-install) · [Learn more](#learn-more)

<p align="center">
  <img src="assets/banner.jpg" alt="autonomous-fleet-adapter-claude-code, autonomous-fleet skill" width="100%">
</p>

> The Claude Code adapter for autonomous-fleet-core. It maps each engine primitive to Claude Code's
> native mechanics: subagents via the Task tool, git worktrees for isolation, the Bash tool for git
> and gh, and TodoWrite as the live task mirror. Load it alongside autonomous-fleet-core when you
> run a mission in Claude Code instead of Orca. Because Claude Code has no separate orchestration
> runtime, the coordinator IS the main Claude Code session, workers are subagents or
> worktree-scoped sub-sessions, and the file ledger is the durable source of truth.

🟧 **Tier 2 · Adapter**, resolves the engine's portable primitives to one specific runtime.

## When to use it

- You run autonomous-fleet missions from a Claude Code session, so the coordinator is that session.
- You want parallel workers as Task-tool subagents instead of a separate orchestration daemon.
- You need isolated checkouts per unit via `git worktree`, or an isolated container via the
  optional `container-use` MCP for sandboxed worker placement.
- You want the optional Stop-hook strict mode that refuses to end a worker session without
  verifiable on-disk evidence.

## What it produces

This adapter is loaded by a mission, not invoked on its own. A run that uses it produces:

- One git worktree per `PLACE(independent)` unit at `../<repo>-<slug>` on branch
  `<BRANCH_PREFIX><slug>` (default prefix `fleet/`).
- One PR per unit via `gh pr create --base BASE`, merged with `gh pr merge <n> --merge
--delete-branch` (merge commit, commits preserved, never `--squash`).
- The file ledger at `docs/<mission>-progress.md`, the durable source of truth across turns, with
  TodoWrite mirroring it for live visibility.
- `DECISIONS.md` entries for the detected capability tier and any worker choices taken from the
  mission DECISION DEFAULTS.

## What it expects from your repo

- A git repo with a resolvable `REPO_ROOT`, and `git worktree` support.
- `gh auth status` passing via the Bash tool. Without it the adapter falls back to local
  merge-commits into BASE.
- A `BASE` branch. If it is absent, the adapter creates it off the default branch at current HEAD.
- gitleaks availability is checked at start.
- Optional: the `container-use` MCP (`claude mcp add container-use -- container-use stdio`, needs
  Docker) if you want `PLACE(independent)` to use an isolated container instead of a host worktree.

## Common failure modes

- `gh auth status` not authenticated: the adapter degrades to local merge-commits and no PR opens.
  See the troubleshooting chapter (install/auth).
- A subagent returns without writing its ledger result: relaunch the unit. It is idempotent
  against the ledger, so an already-MERGED unit is skipped. Never lose a merged unit. See the
  troubleshooting chapter (runtime spawn).
- Two subagents editing the same hot file: one in-flight unit per hot file still holds. Parallelize
  subagents across non-overlapping files only.
- Coordinator context pressure: the coordinator is itself a session with a context limit and no
  external daemon holds state. Write the CONTEXT HANDOFF block into the ledger so a fresh session
  resumes. See the troubleshooting chapter (ledger).
- `/goal` unavailable: it needs Claude Code v2.1.139+ and the trust dialog, and is off under
  `disableAllHooks`.

## Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet-adapter-claude-code -y
```

Then load it alongside `autonomous-fleet-core` and run a mission in Claude Code.

## Learn more

- [Guide 02, Installation](../../docs/guide/02-installation.md), per-runtime setup for Claude Code
- [Guide 13, Extending](../../docs/guide/13-extending.md), primitive-by-primitive adapter mapping
- [SKILL.md](./SKILL.md), the agent-facing spec

---

← Prev: none · [Guide Index](../../docs/guide/README.md) · Next: none →
