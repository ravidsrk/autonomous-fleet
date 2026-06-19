# autonomous-fleet

A portable framework for running fully-autonomous multi-agent engineering jobs — **across
orchestration tools, not just one.** A tool-agnostic **core** holds all the method; thin
**mission** skills describe specific jobs; per-tool **adapters** map the method to each runtime's
real commands.

Published as [Agent Skills](https://agentskills.io/) packages — install with [`npx skills`](https://skills.sh/).

**Repository:** https://github.com/ravidsrk/autonomous-fleet

---

## Quick start

### 1. Install skill-creator (for authoring / validation)

```bash
npx skills add https://github.com/anthropics/skills --skill skill-creator -y -p
```

### 2. Install autonomous-fleet skills

**Starter set** (core + Grok adapter + doc-sync):

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-grok \
  --skill doc-sync \
  -y
```

**All skills:**

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet --skill '*' -y
```

**From a local clone:**

```bash
git clone https://github.com/ravidsrk/autonomous-fleet
cd autonomous-fleet
./scripts/install-skills.sh          # starter set
./scripts/install-skills.sh --all    # everything
```

Skills install to `.agents/skills/` (universal path for Cursor, Codex, Claude Code, Grok, etc.).
The `.agents/` directory is gitignored — it is created when you run `npx skills add` or
`./scripts/install-skills.sh`.

### 3. Validate

Requires step 1 (`skill-creator` installed to `.agents/skills/skill-creator/`):

```bash
./scripts/validate-skills.sh
```

Uses [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)'s
`quick_validate.py` against the [agentskills.io specification](https://agentskills.io/specification).

### 4. Run a mission

Open the **target repo** and trigger in plain language:

- *"sync the docs"* → `doc-sync`
- *"raise test coverage on payments"* → `test-coverage`
- *"fix these bugs"* → `bug-batch`
- *"take this product to the finish line"* → `take-product-to-completion`

Each mission activates `autonomous-fleet-core` + your runtime adapter automatically.

---

## Layout

```
autonomous-fleet/
├── skills/                              # publishable skills (npx skills discovers these)
│   ├── autonomous-fleet-core/
│   │   ├── SKILL.md                     # entry point
│   │   └── references/engine.md         # full engine spec
│   ├── autonomous-fleet-adapter-{orca,claude-code,grok,template}/
│   ├── doc-sync/                        # Tier 1 missions
│   ├── test-coverage/
│   ├── dependency-update/
│   ├── cleanup/
│   ├── bug-batch/                       # Tier 2 missions
│   ├── adversarial-review-and-fix/
│   ├── targeted-migration/
│   ├── design-integration/
│   ├── landing-page-convergence/
│   ├── legacy-rebuild/                  # Tier 3 missions
│   └── take-product-to-completion/
├── .agents/skills/                      # installed skill copies (gitignored; from npx skills add)
├── scripts/
│   ├── validate-skills.sh
│   └── install-skills.sh
└── skills-lock.json                     # lockfile for npx skills
```

**Core + Mission + Adapter = a run.** Missions declare required skills; the core speaks in
primitives; adapters map primitives to runtime commands.

---

## Available skills

| Skill | Type | Notes |
|-------|------|-------|
| `autonomous-fleet-core` | Engine | Required for every run |
| `autonomous-fleet-adapter-orca` | Adapter | Orca orchestration |
| `autonomous-fleet-adapter-claude-code` | Adapter | Claude Code |
| `autonomous-fleet-adapter-grok` | Adapter | Grok Build |
| `autonomous-fleet-adapter-template` | Guide | Copy to author a new adapter |
| `doc-sync` | Mission · Tier 1 | Highest merge rate (~0.92) |
| `test-coverage` | Mission · Tier 1 | |
| `dependency-update` | Mission · Tier 1 | |
| `cleanup` | Mission · Tier 1 | |
| `bug-batch` | Mission · Tier 2 | Reproduce-first gate |
| `adversarial-review-and-fix` | Mission · Tier 2 | Two-phase workhorse |
| `targeted-migration` | Mission · Tier 2 | |
| `design-integration` | Mission · Tier 2 | |
| `landing-page-convergence` | Mission · Tier 2 | |
| `legacy-rebuild` | Mission · Tier 3 | |
| `take-product-to-completion` | Mission · Tier 3 | |

List all: `npx skills add https://github.com/ravidsrk/autonomous-fleet --list`

---

## Authoring new skills

Install `skill-creator` from Anthropic first (step 1 above — not bundled in this repo). To add a
mission or adapter:

```bash
# scaffold a new skill
npx skills init my-new-mission

# follow skill-creator workflow in .agents/skills/skill-creator/SKILL.md
# validate
./scripts/validate-skills.sh
```

Copy `skills/autonomous-fleet-adapter-template/` when adding a new runtime adapter.

---

## What every run guarantees

- Repo and maintainer discovered — no placeholders
- One PR per unit; commits preserved (never squashed)
- Conflict-aware merges; checkout cleanup on every merge
- Safety rails: testnet/staging only; merge ≠ deploy
- File ledger survives compaction and session restarts