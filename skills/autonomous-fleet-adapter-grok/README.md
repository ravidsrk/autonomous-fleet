<!-- title: autonomous-fleet-adapter-grok | description: The Grok Build runtime adapter for autonomous-fleet-core. | sidebar_order: 10 -->

# autonomous-fleet-adapter-grok

<p align="center">
  <img src="assets/banner.jpg" alt="autonomous-fleet-adapter-grok — autonomous-fleet skill" width="100%">
</p>

> The Grok adapter for autonomous-fleet-core. It maps each engine primitive to Grok Build
> mechanics: subagents via the Task tool, git worktrees for isolation, the Shell tool for git and
> gh, and the file ledger as the durable source of truth. Load it alongside autonomous-fleet-core
> to run a mission in Grok. Grok has no separate orchestration daemon, so the coordinator IS the
> main Grok session and the file ledger is the authority across turns.

🟧 **Tier 2 · Adapter** — the runtime bridge that runs autonomous-fleet on Grok Build.

**On this page:** [When to use it](#when-to-use-it) · [What it produces](#what-it-produces) ·
[What it expects](#what-it-expects-from-your-repo) · [Failure modes](#common-failure-modes) ·
[Quick install](#quick-install) · [Learn more](#learn-more)

## When to use it

- You want to run an autonomous-fleet mission inside Grok Build instead of Claude Code, Codex, or
  Orca.
- Your build and review units are self-contained enough to fan out across Grok subagents (launched
  with the Task tool) running concurrently on non-overlapping files.
- You need worktree-scoped isolation for a unit that owns its own branch and PR, driven by the
  coordinator through the Shell tool.
- You are pairing Grok with a mission that names it, for example the design-integration units that
  prefer `@grok`.

## What it produces

This adapter produces no artifacts of its own. It is a translation layer: the mission and the
engine produce the artifacts, and this adapter is how they land on Grok. A run drives Grok to
write the file ledger at `docs/<mission>-progress.md` (the authority across turns), open one PR
per unit with `gh pr create --base BASE`, merge with `gh pr merge <n> --merge --delete-branch`
(merge commit, never `--squash`), and record decisions in `DECISIONS.md`. The run-archive and
`fleet-outcome.yaml` come from autonomous-fleet-core, not from this skill.

## What it expects from your repo

- A git repo with a resolvable `REPO_ROOT` and `gh auth status` passing (else the adapter falls
  back to local merge-commits into `BASE`).
- git worktree support and a `BASE` branch (created off the default branch at current HEAD if
  absent).
- Grok Build with the Task tool available, plus gitleaks on the host.
- Optional: the container-use MCP (`grok mcp add container-use -- container-use stdio`, needs
  Docker) for sandboxed container placement. The registration is verified on this host, but a full
  live container run is gated by Grok's own auth (headless Grok hits `Auth(AuthorizationRequired)`),
  so exercise it once Grok login is configured.

## Common failure modes

- A subagent returns without writing its ledger result. The adapter re-reads the returned summary
  and relaunches the unit (idempotent: a unit already MERGED is skipped). See
  [Troubleshooting](../../docs/guide/14-troubleshooting.md).
- Passing `-m composer-2.5-fast`. That literal id is rejected as unknown; let the host pick its
  default model unless the mission specifies one the installed grok accepts.
- Headless mode (`grok -p ... --yolo`) is not yet fully validated end-to-end; the interactive chat
  and `/goal` path is the supported flow. See [Safety and secrets](../../docs/guide/12-safety-and-secrets.md).
- Coordinator context pressure with no external daemon to hold state. Write the CONTEXT HANDOFF
  block into the ledger so a fresh session resumes.

## Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet-adapter-grok -y
```

Then load it alongside `autonomous-fleet-core` in your Grok Build session and reference both by
name.

## Learn more

- [Guide 02 — Installation](../../docs/guide/02-installation.md) — per-runtime setup, including Grok
- [Guide 13 — Extending](../../docs/guide/13-extending.md) — the primitive-by-primitive adapter contract
- [SKILL.md](./SKILL.md) — the agent-facing spec that governs this adapter's behavior

---

[📖 Guide Index](README.md)
