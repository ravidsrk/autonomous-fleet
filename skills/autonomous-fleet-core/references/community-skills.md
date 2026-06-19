# Community skills catalog

How to install and attach third-party skills to autonomous-fleet runs without overwhelming the
coordinator. Read with [composition.md](composition.md).

**Research:** `docs/research-community-skills.md`

---

## Rules

1. **Fleet orchestrates; community executes tactics.** Use `fleet-program` for mission order;
   attach community skills only as Optional (coordinator) or Worker (DISPATCH).
2. **Coordinator budget:** core + adapter + one mission + **at most 2 optional** community skills.
3. **Pre-gates** (alignment) are **user-invoked** when possible — run once before the campaign
   starts, not auto-loaded from catalog noise.
4. **Post-gates** (ship, QA report) run after the last mission node; they do not replace
   `fleet-outcome` validation.
5. **Never** activate two mission skills or multiple meta-routers (`using-agent-skills`,
   `gstack-autoplan`, `fleet-program`) in the same coordinator session.

---

## Install

```bash
# gstack (multi-host; Claude Code example)
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup

# agent-skills (Claude Code plugin)
/plugin marketplace add https://github.com/addyosmani/agent-skills.git
/plugin install agent-skills@addy-agent-skills

# mattpocock/skills
npx skills@latest add mattpocock/skills
# Then run /setup-matt-pocock-skills in the agent
```

Install **per bundle** — not all three repos unless you need them.

---

## Starter bundles

| Bundle | Fleet entry | Community install |
|--------|-------------|-------------------|
| Fix my repo | `fleet-program` preset `repo-health` | None required |
| Ship safely | preset `ship-with-proof` | gstack (`ship`, `qa`) optional |
| Finish product | preset `align-then-ship` | mattpocock `grill-with-docs` or gstack `office-hours` |
| Production readiness | preset `quality-gate` | gstack `qa-only`, `health` optional |
| Greenfield feature | Human `/spec` + `/plan`, then one mission | agent-skills plugin |

Headless:

```bash
./scripts/run-campaign.sh grok --preset ship-with-proof --dry-run
```

---

## Mix-and-match by fleet slot

### Pre-gates (before first mission node)

| Skill | Source | When |
|-------|--------|------|
| `grill-with-docs` / `grill-me` | mattpocock | Tier 3 mission; boundary or intent unclear |
| `gstack-office-hours` | gstack | Product framing before `take-product-to-completion` |
| `gstack-autoplan` | gstack | Plan review gauntlet only — save plan, defer implement to fleet mission |

Invoke explicitly; record output path in `docs/fleet-program-progress.md` **Handoff notes**.

### Optional (coordinator, during mission)

| Skill | Source | Mission(s) | Trigger |
|-------|--------|------------|---------|
| `gstack-office-hours` | gstack | `take-product-to-completion` | T3 boundary ambiguous |
| `gstack-cso` | gstack | `adversarial-review-and-fix` | Security-heavy audit |
| `gstack-health` | gstack | `doc-sync`, `quality-gate` tail | User wants composite score |

### Worker (DISPATCH preamble)

| Skill | Source | Mission(s) | Role |
|-------|--------|------------|------|
| `test-driven-development` | agent-skills | `bug-batch`, `test-coverage` | @builder |
| `incremental-implementation` | agent-skills | build-heavy missions | @builder |
| `security-and-hardening` | agent-skills | `adversarial-review-and-fix` | @reviewer |
| `frontend-ui-engineering` | agent-skills | `design-integration`, `landing-page-convergence` | @builder |
| `domain-modeling` | mattpocock | `doc-sync`, `take-product-to-completion` | @planner |
| `gstack-qa` | gstack | UI missions | @builder (fix loop) |
| `gstack-qa-only` | gstack | UI missions | @reviewer (report only) |

Copy the chosen rows into the mission `## Worker skills` table when authoring; coordinator
pastes into engine WORKER SKILLS block on DISPATCH.

### Post-gates (after campaign `PHASE: DONE`)

| Skill | Source | Campaign preset | When |
|-------|--------|-----------------|------|
| `gstack-ship` | gstack | `ship-with-proof` | User asked to open PR |
| `gstack-qa` | gstack | `ship-with-proof` | Staging URL available |
| `gstack-qa-only` | gstack | `quality-gate` | Report-only acceptance |
| `gstack-health` | gstack | `quality-gate` | Optional scorecard |

Post-gates are optional human steps — fleet campaign is DONE when all **mission nodes** complete
and `validate-fleet-outcome.sh` passes.

---

## Campaign presets using community skills

| Preset | Mission nodes | Pre-gate | Post-gate |
|--------|---------------|----------|-----------|
| `ship-with-proof` | audit → tests → docs | — | `gstack-ship`, `gstack-qa` |
| `align-then-ship` | `take-product-to-completion` | `grill-with-docs` or `office-hours` | `gstack-qa` if URL |
| `quality-gate` | audit → tests | — | `gstack-qa-only`, `gstack-health` |

YAML: `scripts/campaigns/<preset>.yaml` and
`skills/fleet-program/references/campaigns.md`.

---

## Skill id naming

Installed skill ids vary by host and installer prefix:

| Upstream | Typical installed id |
|----------|---------------------|
| gstack | `gstack-qa`, `gstack-ship`, `gstack-office-hours` (via `./setup --host`) |
| agent-skills | `planning-and-task-breakdown`, `test-driven-development`, … |
| mattpocock | `domain-modeling`, `grill-with-docs`, `grill-me` |

Use the id your `npx skills list` or plugin manifest shows in mission Optional/Worker tables.

---

## Anti-patterns

| Do not | Do instead |
|--------|------------|
| Load gstack + agent-skills meta-skills on coordinator | Pick fleet-program preset |
| Chain 6 slash commands manually | One `fleet-program` campaign |
| Auto-invoke grill/office-hours every run | Pre-gate only when Tier 3 or ambiguous |
| Skip `fleet-outcome` because QA passed | File ledger remains authoritative |
| `gstack-ship` mid-mission | Post-gate after docs node in `ship-with-proof` |