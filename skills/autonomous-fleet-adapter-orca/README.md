<!-- title: autonomous-fleet-adapter-orca | description: First-class Orca adapter for autonomous-fleet-core — the reference runtime for supervised fleet missions. | sidebar_order: 11 -->

# autonomous-fleet-adapter-orca

<p align="center">
  <img src="assets/banner.png" alt="autonomous-fleet-adapter-orca, autonomous-fleet skill" width="100%">
</p>

> **Reference runtime adapter** for autonomous-fleet-core on [Orca](https://www.onorca.dev). Maps
> engine primitives to Orca orchestration CLI commands and routes fleet missions vs platform
> handoffs. Load alongside `autonomous-fleet-core` and one mission when running on Orca.

🟦 **Tier 2 · Adapter** — Orca is the primary distribution path for autonomous-fleet: structural
build-blind review, native multi-terminal orchestration, and the production topology this framework
was distilled from.

**On this page:** [When to use it](#when-to-use-it) · [Routing](#routing) · [What it produces](#what-it-produces) ·
[What it expects](#what-it-expects-from-your-repo) · [Common failure modes](#common-failure-modes) ·
[Quick install](#quick-install) · [Learn more](#learn-more)

## When to use it

- You are running a **fleet mission** on Orca (`doc-sync`, `adversarial-review-and-fix`,
  `fleet-program`, …) and want each worker in its own worktree and terminal.
- You need **structural build-blind review**: `@codex` or `@grok` builds in one terminal, a fresh
  `@claude` reviews in another — isolation is mechanical, not instructed.
- You want parallel, independent PRs: `independent` work in a fresh worktree off BASE,
  `dependent` work in the active worktree on a fresh terminal.
- You are supervising workers — waiting for `worker_done`, coordinating a DAG, syncing task state.

**Not this adapter:** one-shot ownership handoffs ("give this to Codex and stop watching") → use
**`orca-cli`** instead. See [Routing](#routing) and [SKILL.md](./SKILL.md).

## Routing

| Intent | Path |
|--------|------|
| Fleet mission or campaign | **This adapter** — `task-create` + `dispatch --inject` + `check --wait` |
| Full handoff without supervision | **`orca-cli`** — no orchestration lifecycle |
| Terminal / worktree / embedded browser ops | **`orca-cli`** |
| Desktop UI outside Orca | **Computer Use** |

Full routing table: [references/orca-platform.md](./references/orca-platform.md).

## What it produces

- Orca worktrees and terminals per worker, with `orchestration` tasks via `task-create` and
  `dispatch --inject`.
- Interactive builder CLIs (`codex`, `grok`, `claude` in terminals) — **not** `codex exec` for
  supervised Orca runs.
- A file ledger kept aligned with Orca task state via `task-update` on every lifecycle change.
- One merge-commit PR per unit (`gh pr merge --merge --delete-branch`, never `--squash`).
- Runtime-goal bookkeeping in the ledger (`check --wait` loop; Orca has no `/goal` API).

## What it expects from your repo

- Orca orchestration CLI, `git`, and `gh` installed. Experimental orchestration enabled;
  `orca status --json` must report a running runtime.
- `gh auth status` for PR workflows (else local merge-commits into BASE).
- A BASE branch (created off default branch at HEAD if absent).
- `gitleaks` for core precondition checks.
- On Orca, companion skills **`orchestration`** and **`orca-cli`** for non-fleet platform cases.

## Common failure modes

- Dispatching before `tui-idle`: inject on a non-idle terminal is lost. Wait first.
- Worker looks done but sent no `worker_done`: use `dispatch-show`, re-send via `terminal send` —
  never kill a live worker.
- Treating Orca's 3-consecutive-failure circuit break as a stop: it is a reassign signal.
- Using `task-create` / `dispatch --inject` for a full handoff the user did not ask to supervise.
- Addressing lifecycle messages to broadcast handles (`@all`, `@idle`): target the concrete
  coordinator handle.

> Headless campaign mode (`run-campaign.sh`) accepts only `grok`, `claude`, and `codex` CLIs.
> Interactive Orca orchestration is the supported path for Orca missions.

## Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet-adapter-orca -y
```

Or use the repo starter set: `./scripts/install-skills.sh` (defaults to Orca adapter).

Then load `autonomous-fleet-core` + one mission and run on Orca.

## Learn more

- [SKILL.md](./SKILL.md) — agent-facing spec (primitives, WAIT types, review-only `worker_done`)
- [references/orca-platform.md](./references/orca-platform.md) — routing vs `orca-cli` / Computer Use
- [Guide 02, Installation](../../docs/guide/02-installation.md)
- [Guide 13, Extending](../../docs/guide/13-extending.md)

← [Guide Index](../../docs/guide/README.md)