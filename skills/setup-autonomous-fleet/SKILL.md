---
name: setup-autonomous-fleet
description: >-
  User-invoked setup only — do not auto-activate. Configure a repo for autonomous-fleet:
  runtime adapter, branch prefix, default campaign bundle, optional community installs. Run
  when the user says setup autonomous fleet, configure fleet, or first fleet run on a repo.
license: MIT
compatibility: Requires git; gh CLI recommended for PR workflows
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  fleet-component: "setup"
---

# Setup autonomous-fleet

Scaffold per-repo fleet configuration so coordinators, `fleet-program`, and missions start
with consistent defaults. Prompt-driven — explore, confirm with the user, then write.

## Process

### 1. Explore

Read what already exists; do not assume:

- `git rev-parse --show-toplevel`, `git remote -v`, default branch
- `CLAUDE.md` / `AGENTS.md` — existing agent sections?
- `docs/agents/fleet-config.md` — prior setup output?
- `DECISIONS.md` — recorded `BRANCH_PREFIX` or adapter choice?
- `.agents/skills/` or host skill dirs — which fleet skills are installed?
- `gh auth status` — PR workflow available?

### 2. Present findings — one section at a time

Walk the user through **three decisions** sequentially. Each section: short explainer, choices,
default.

**Section A — Runtime adapter.**

> Which host will run fleet coordinators? This picks the adapter skill that maps engine
> primitives to real commands.

| Choice | Adapter skill |
|--------|---------------|
| Grok Build | `autonomous-fleet-adapter-grok` |
| Claude Code | `autonomous-fleet-adapter-claude-code` |
| OpenAI Codex | `autonomous-fleet-adapter-codex` |
| Orca | `autonomous-fleet-adapter-orca` |

Default: Grok Build if unclear.

**Section B — Branch prefix.**

> Fleet missions branch as `<prefix><task-slug>`. Default derives from git `user.name`
> (slugified) or `fleet/`.

Confirm override or accept default (`fleet/` or slugified maintainer name).

**Section C — Default bundle.**

> When intent is vague, which `fleet-program` preset should the umbrella suggest?

| Bundle | Preset | When |
|--------|--------|------|
| Fix my repo | `repo-health` | Docs/tests/cleanup pass |
| Ship safely | `ship-with-proof` | Pre-merge hardening |
| Finish product | `align-then-ship` | Tier 3 — explicit only |
| Production check | `quality-gate` | Readiness without full doc-sync |
| Single mission | `none` | User always names a mission |

Default: `repo-health`.

**Section D — Community skills (optional).**

> Third-party skills attach as Optional/Worker only — see `community-skills.md`. Install per
> bundle, not the full catalog.

Ask which bundles need community installs (gstack, agent-skills, mattpocock). Record choices;
do not install without user consent.

### 3. Confirm draft

Show draft of:

- `docs/agents/fleet-config.md` (see [references/fleet-config-template.md](references/fleet-config-template.md))
- `## Autonomous fleet` block for `CLAUDE.md` or `AGENTS.md`

Let the user edit before writing.

### 4. Write

**Pick host doc:** edit `CLAUDE.md` if present, else `AGENTS.md`, else ask which to create.

Update `## Autonomous fleet` in-place if it exists — no duplicate blocks.

Write `docs/agents/fleet-config.md`.

Append a one-line setup record to `DECISIONS.md` with adapter, prefix, bundle, date.

### 5. Install skills (if missing)

First **detect install mode** — the helper scripts only exist in a framework clone, not in a
skills-installed repo (`npx skills` copies only `skills/` into `.agents/skills/`, never
`scripts/`):

```bash
if [ -f ./scripts/install-skills.sh ]; then echo clone; else echo skills-install; fi
```

**Skills-install mode (no `./scripts/`)** — the common case. Print `npx skills` commands; do
not reference `./scripts/*`, which is not shipped here:

```bash
npx skills@1.5.12 add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill fleet-program \
  --skill autonomous-fleet-adapter-<chosen> \
  --skill doc-sync \
  -y
# or every skill: --skill '*'
```

**Clone mode (`./scripts/install-skills.sh` present)** — contributor path:

```bash
./scripts/install-skills.sh --all
# or minimal:
./scripts/install-skills.sh autonomous-fleet fleet-program autonomous-fleet-core \
  autonomous-fleet-adapter-<chosen> doc-sync
```

For community bundles, print install commands from
`skills/autonomous-fleet-core/references/community-skills.md`.

### 6. Verify

**Skills-install mode (no `./scripts/`)** — there is no `./scripts/run-campaign.sh` to call.
Confirm the install instead: the listed skills now resolve under `.agents/skills/`, and the
chosen adapter is among them. Drive the first run interactively from the agent's chat
(`/setup-autonomous-fleet` is done; invoke a mission or `fleet-program` next).

**Clone mode** — suggest a headless dry-run:

```bash
./scripts/run-campaign.sh <adapter-runtime> --preset <bundle> --dry-run
```

## After setup

Coordinators read `docs/agents/fleet-config.md` during SELF-ORIENTATION (override defaults
there over engine defaults when present). Re-run this skill when changing adapter, prefix, or
default bundle.