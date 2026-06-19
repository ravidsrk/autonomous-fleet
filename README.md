# autonomous-fleet

A portable framework for running fully-autonomous multi-agent engineering jobs — **across
orchestration tools, not just one.** A tool-agnostic **core** holds all the method; thin
**mission** skills describe specific jobs; per-tool **adapters** map the method to each runtime's
real commands.

This repository follows the [Agent Skills](https://agentskills.io/) format end to end: every
component is a skill directory with a `SKILL.md` file, optional `references/`, and spec-compliant
frontmatter (`name` matches directory name).

Write the mission once. Run it on any supported tool. Fix the method once; every mission and every
tool inherits the fix.

**Repository:** https://github.com/ravidsrk/autonomous-fleet

---

## Layout (Agent Skills format)

```
autonomous-fleet/
├── skills/
│   ├── autonomous-fleet-core/          # tool-agnostic engine
│   │   ├── SKILL.md
│   │   └── references/engine.md        # full engine spec (progressive disclosure)
│   ├── autonomous-fleet-adapter-orca/
│   ├── autonomous-fleet-adapter-claude-code/
│   ├── autonomous-fleet-adapter-grok/
│   ├── autonomous-fleet-adapter-template/
│   ├── doc-sync/                       # Tier 1 missions
│   ├── test-coverage/
│   ├── dependency-update/
│   ├── cleanup/
│   ├── bug-batch/                      # Tier 2 missions
│   ├── adversarial-review-and-fix/
│   ├── targeted-migration/
│   ├── design-integration/
│   ├── landing-page-convergence/
│   ├── legacy-rebuild/                 # Tier 3 missions
│   └── take-product-to-completion/
├── scripts/
│   ├── validate-skills.sh              # agentskills.io convention checks
│   └── install-skills.sh               # symlink skills into your agent
└── README.md
```

**Core + Mission + Adapter = a run.** The core calls primitives (spawn worker, dispatch, wait,
inspect, place work, open/merge PR, sync state); the active adapter resolves each primitive to its
tool's real commands. Missions declare which skills to activate; they never hard-code a runtime.

---

## Supported runtimes

| Skill | Runtime | Concurrency model |
|-------|---------|-------------------|
| `autonomous-fleet-adapter-orca` | [Orca](https://www.onorca.dev) | Daemon + worktrees + terminals; `check --wait` |
| `autonomous-fleet-adapter-claude-code` | Claude Code | Coordinator session + Task subagents; file ledger |
| `autonomous-fleet-adapter-grok` | Grok Build | Coordinator session + Task subagents; file ledger |
| `autonomous-fleet-adapter-template` | any | Copy and implement primitives for a new tool |

---

## Risk tiers

| Tier | Meaning | Missions | Approx. merge rate |
|------|---------|----------|--------------------|
| **1** | Safe unattended | doc-sync, test-coverage, dependency-update, cleanup | 0.84–0.92 |
| **2** | Full review gate | bug-batch, adversarial-review-and-fix, targeted-migration, design-integration, landing-page-convergence | 0.80–0.82 |
| **3** | High blast radius | legacy-rebuild, take-product-to-completion | ~0.80 |

Start with **doc-sync** or **test-coverage** (Tier 1).

---

## Install

### Validate (local)

```bash
./scripts/validate-skills.sh
```

### Grok Build (default)

```bash
./scripts/install-skills.sh
# symlinks skills/* -> ~/.grok/skills/*
```

### Manual / other agents

Copy or symlink each directory under `skills/` into your agent's skills path. Each installed skill
must keep the structure `<skill-name>/SKILL.md` with `name:` in frontmatter matching the directory.

Minimum to run on Orca:

```
<skills-dir>/autonomous-fleet-core/SKILL.md
<skills-dir>/autonomous-fleet-adapter-orca/SKILL.md
<skills-dir>/doc-sync/SKILL.md
```

For Claude Code use `autonomous-fleet-adapter-claude-code`; for Grok use
`autonomous-fleet-adapter-grok`.

At run start the core derives `BRANCH_PREFIX` (default `fleet/`) and ensures `docs/` exists for
mission ledgers — both recorded in `DECISIONS.md`.

### Add a new runtime

1. Copy `skills/autonomous-fleet-adapter-template/` to `skills/autonomous-fleet-adapter-<tool>/`
2. Set frontmatter `name: autonomous-fleet-adapter-<tool>` (must match directory)
3. Fill in primitive mappings
4. Run `./scripts/validate-skills.sh`

---

## Use

1. Open the **target repo** you want the fleet to work on (missions discover `REPO_ROOT` from cwd).
2. Install the **core**, one **adapter**, and the **mission** you want.
3. Trigger in plain language — *"sync the docs," "raise test coverage," "fix these bugs,"*
   *"take this product to the finish line."*
4. The mission activates `autonomous-fleet-core` + your adapter and runs autonomously until the
   readiness doc exists and a single final report is sent.

Hard external dependencies (e.g. `design-integration` + `/design-login` for Claude Design MCP) are
the only allowed mid-run user pauses.

---

## What every run guarantees

- Repo and maintainer discovered — no placeholders
- One PR per unit; commits preserved (never squashed); real maintainer authorship
- Conflict-aware merges; checkout cleanup on every merge
- Safety rails: testnet/staging only; merge ≠ deploy
- File ledger survives compaction and session restarts

---

## Spec compliance

- Format: [agentskills.io/specification](https://agentskills.io/specification)
- Progressive disclosure: core engine detail in `skills/autonomous-fleet-core/references/engine.md`
- Optional upstream validator: [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref)