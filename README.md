# autonomous-fleet

A portable framework for running multi-agent engineering jobs designed for autonomous runs
(headless path not yet end-to-end validated) — **across
orchestration tools, not just one.** A tool-agnostic **core** holds all the method; thin
**mission** skills describe specific jobs; per-tool **adapters** map the method to each runtime's
real commands.

Published as [Agent Skills](https://agentskills.io/) packages — install with [`npx skills`](https://skills.sh/).

**Repository:** https://github.com/ravidsrk/autonomous-fleet

CI runs `./scripts/validate-all.sh` on every push/PR to `main` (skills, fleet-outcome, goal
conditions, pytest).

---

## Quick start

### 1. Install skill-creator (for authoring / validation)

```bash
npx skills add https://github.com/anthropics/skills --skill skill-creator -y -p
```

### 2. Install autonomous-fleet skills

**Starter set** (umbrella + program + core + Grok adapter + doc-sync):

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet \
  --skill fleet-program \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-grok \
  --skill doc-sync \
  -y
```

Then run **`/setup-autonomous-fleet`** once in your agent (adapter, branch prefix, default campaign bundle).

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
./scripts/validate-all.sh             # skills + fleet-outcome + goals + pytest (recommended)
./scripts/validate-goal-condition.sh --scan-docs
./scripts/run-campaign.sh grok --preset repo-health --dry-run
./scripts/run-campaign.sh grok --preset ship-with-proof --dry-run
./scripts/run-campaign.sh grok --campaign docs/external-dogfood/ship-with-proof-campaign.yaml --repo /path/to/target --dry-run
./scripts/run-mission-headless.sh grok doc-sync --max-turns 50
# Headless grok requires CLI auth; use interactive agent + /goal when unavailable
# or individually:
./scripts/validate-skills.sh          # SKILL.md packages (agentskills.io)
./scripts/validate-fleet-outcome.sh   # readiness doc fleet-outcome YAML
pytest tests/test_fleet_campaign.py   # campaign edge evaluator
```

Skill validation uses [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)'s
`quick_validate.py`. After a mission run, readiness docs must lead with `fleet-outcome` YAML — see
`skills/autonomous-fleet-core/references/fleet-outcome.md`.

Evaluate a campaign branch manually:

```bash
./scripts/eval-campaign-edge.sh \
  --readiness docs/doc-sync-readiness.md \
  --campaign docs/composition-e2e-campaign.yaml \
  --current-node docs
```

### 4. Run a mission

Trigger the umbrella skill (`autonomous-fleet`) to route an vague request, or name a mission
directly. Open the **target repo** and use plain language:

- _"sync the docs"_ → `doc-sync`
- _"raise test coverage on payments"_ → `test-coverage`
- _"fix these bugs"_ → `bug-batch`
- _"take this product to the finish line"_ → `take-product-to-completion`

Each mission activates `autonomous-fleet-core` + your runtime adapter automatically.

For **mission chains and conditional campaigns** (e.g. docs → tests → cleanup; audit branches on
`fleet-outcome`), use `fleet-program` — one mission at a time per repo. Workers compose domain
skills via each mission's `## Worker skills` table (injected on dispatch).

---

## Layout

```
autonomous-fleet/
├── skills/                              # publishable skills (npx skills discovers these)
│   ├── autonomous-fleet/                # umbrella entry-point (routes to mission + core + adapter)
│   ├── fleet-program/                   # sequential + conditional campaign DAGs
│   ├── setup-autonomous-fleet/          # per-repo config (adapter, prefix, bundle)
│   ├── autonomous-fleet-core/
│   │   ├── SKILL.md                     # entry point
│   │   └── references/
│   │       ├── engine.md                # full engine spec
│   │       ├── composition.md           # skill loading rules
│   │       ├── community-skills.md      # gstack / agent-skills / mattpocock hooks
│   │       ├── fleet-outcome.md         # machine-readable readiness YAML
│   │       └── runtime-goals.md         # /goal + ledger binding
│   ├── autonomous-fleet-adapter-{orca,claude-code,grok,codex,template}/
│   ├── doc-sync/                        # Tier 1 missions
│   ├── test-coverage/
│   ├── dependency-update/
│   ├── cleanup/
│   ├── scaffold-align/
│   ├── bug-batch/                       # Tier 2 missions
│   ├── adversarial-review-and-fix/
│   ├── targeted-migration/
│   ├── design-integration/
│   ├── landing-page-convergence/
│   ├── inference-cost/
│   ├── legacy-rebuild/                  # Tier 3 missions
│   ├── take-product-to-completion/
│   ├── contract-first-build/
│   └── agents-layer/
├── docs/
│   ├── external-dogfood/                # gemoji repo-health + ship-with-proof evidence
│   ├── research-community-skills.md
│   └── doc-sync-audit.md                # latest drift index
├── .agents/skills/                      # installed skill copies (gitignored; from npx skills add)
├── scripts/
│   ├── validate-all.sh
│   ├── validate-skills.sh
│   ├── validate-fleet-outcome.sh
│   ├── validate-goal-condition.sh
│   ├── eval-campaign-edge.sh
│   ├── eval-campaign-edge.py
│   ├── coupling-graph.py                # import/symbol graph for coupling-aware decomposition
│   ├── render-dashboard.py              # ledger -> attention-zone HTML dashboard
│   ├── run-campaign.sh
│   ├── run-mission-headless.sh
│   ├── run-sandboxed.sh                 # command-safety classifier + env scrub
│   ├── campaigns/                       # repo-health, ship-with-proof, align-then-ship, quality-gate
│   ├── lib/fleet_outcome.py
│   └── install-skills.sh
├── tests/
│   └── test_fleet_campaign.py
└── skills-lock.json                     # lockfile for npx skills
```

**Core + Mission + Adapter = a single-mission run.** **Core + fleet-program + Adapter** = linear
or conditional campaign (one mission at a time per repo). Missions declare Required / Optional /
Worker / Deferred sections; readiness docs lead with `fleet-outcome` YAML.

---

## Available skills

| Skill                                  | Type             | Notes                                                                                                                                                                     |
| -------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `autonomous-fleet`                     | Umbrella         | Entry point — routes to mission or program + core + adapter                                                                                                               |
| `fleet-program`                        | Program          | Mission chains + conditional campaign DAGs                                                                                                                                |
| `setup-autonomous-fleet`               | Setup            | First run on a repo — adapter, prefix, default bundle                                                                                                                     |
| `autonomous-fleet-core`                | Engine           | Required for every run                                                                                                                                                    |
| `autonomous-fleet-adapter-orca`        | Adapter          | Orca orchestration                                                                                                                                                        |
| `autonomous-fleet-adapter-claude-code` | Adapter          | Claude Code                                                                                                                                                               |
| `autonomous-fleet-adapter-grok`        | Adapter          | Grok Build (`/goal`, `update_goal`)                                                                                                                                       |
| `autonomous-fleet-adapter-codex`       | Adapter          | OpenAI Codex (`/goal`)                                                                                                                                                    |
| `autonomous-fleet-adapter-template`    | Guide            | Copy to author a new adapter                                                                                                                                              |
| `doc-sync`                             | Mission · Tier 1 | Documentation, CI, and build-update tasks show the highest merge-success rate among AI-agent PRs (arXiv 2601.15195 — Ehsani et al., MSR 2026, AIDev dataset of ~33k PRs). |
| `test-coverage`                        | Mission · Tier 1 |                                                                                                                                                                           |
| `dependency-update`                    | Mission · Tier 1 |                                                                                                                                                                           |
| `cleanup`                              | Mission · Tier 1 |                                                                                                                                                                           |
| `scaffold-align`                       | Mission · Tier 1 | Verify scaffold + freeze the build plan                                                                                                                                   |
| `bug-batch`                            | Mission · Tier 2 | Reproduce-first gate                                                                                                                                                      |
| `adversarial-review-and-fix`           | Mission · Tier 2 | Two-phase workhorse                                                                                                                                                       |
| `targeted-migration`                   | Mission · Tier 2 |                                                                                                                                                                           |
| `design-integration`                   | Mission · Tier 2 |                                                                                                                                                                           |
| `landing-page-convergence`             | Mission · Tier 2 |                                                                                                                                                                           |
| `inference-cost`                       | Mission · Tier 2 | Measurement-first cost reduction; sanctioned levers only                                                                                                                  |
| `legacy-rebuild`                       | Mission · Tier 3 |                                                                                                                                                                           |
| `take-product-to-completion`           | Mission · Tier 3 |                                                                                                                                                                           |
| `contract-first-build`                 | Mission · Tier 3 | Greenfield authed build on a frozen plan                                                                                                                                  |
| `agents-layer`                         | Mission · Tier 3 | One-axis stub->live agent-seam cutover                                                                                                                                    |

**24 skills** under `skills/`. List all: `npx skills add https://github.com/ravidsrk/autonomous-fleet --list`

### Campaign presets (`scripts/campaigns/`)

| Preset            | Nodes                                                 |
| ----------------- | ----------------------------------------------------- |
| `repo-health`     | doc-sync → test-coverage → cleanup                    |
| `ship-with-proof` | adversarial-review-and-fix → test-coverage → doc-sync |
| `align-then-ship` | take-product-to-completion (+ pre-gate)               |
| `quality-gate`    | adversarial-review-and-fix → test-coverage            |

Community skill hooks: `skills/autonomous-fleet-core/references/community-skills.md`.

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
- Runtime goals bind native `/goal` loops to ledger DONE ([runtime-goals.md](skills/autonomous-fleet-core/references/runtime-goals.md))
- Anti-inflation + scope: a green suite is not "done" — completion/rebuild missions gate on `e2e_verified` (verify the real end-to-end result state, not exit codes); a FROZEN SCOPE BOUNDARY caps each run; worktree cleanup is a tracked `WT_CLEAN` gate; editorial/credential decisions route through the surfacing lanes (fix / draft-and-gate / refuse) rather than being fabricated
- Engine disciplines: external facts are monid-verified and logged to `docs/research-notes.md` with an `unverified_assumptions: 0` gate; per-task model/cost routing emits `cost_estimate` in `fleet-outcome`; commands pass through `scripts/run-sandboxed.sh`; optional container-use placement gives each worker an isolated container + git branch
