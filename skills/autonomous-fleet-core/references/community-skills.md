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
   `autoplan`, `fleet-program`) in the same coordinator session.

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

```bash
./scripts/install-community.sh gstack-browser --dry-run
./scripts/install-community.sh gstack-security --execute --host grok
./scripts/install-skills.sh --all --with-community gstack-browser --execute
```

Record installs in `docs/agents/fleet-config.md` (see `setup-autonomous-fleet` Section D).

---

## Community bundles (gstack subsets)

| Bundle id | gstack skill ids | Fleet missions / presets |
|-----------|------------------|--------------------------|
| `gstack-browser` | `browse`, `qa`, `qa-only`, `health` | `browser-qa-fix`; post-gate on `ship-with-proof` *(exploratory)* |
| `gstack-security` | `cso`, `investigate` | `incident-investigate` *(exploratory)* |
| `gstack` | full clone + `./setup` | All active bundles above; parked designs may still name older bundles in archive |

Gstack-derived exploratory missions declare machine-readable recommends:

```yaml community-recommends
bundle: gstack-browser
skills:
  - browse
  - qa
mode: warn
```

`scripts/preflight-community.sh` prints install hints when skills are absent (warn tier);
missions still complete via TASK fallbacks. See [composition.md](composition.md) dependency tiers.

### Pre-gate table (gstack-derived active missions)

| Mission | Pre-gate (user-invoked) | gstack `benefits-from` analogue |
|---------|-------------------------|----------------------------------|
| `browser-qa-fix` | — | — *(exploratory)* |
| `incident-investigate` | — | `investigate` optional *(exploratory)* |

---

## Starter bundles

| Bundle | Fleet entry | Community install |
|--------|-------------|-------------------|
| Fix my repo | `fleet-program` preset `repo-health` (now `doc-sync → test-coverage`; `cleanup` exploratory) | None required |
| Ship safely | preset `ship-with-proof` | gstack (`ship`, `qa`) optional |
| Finish product | preset `align-then-ship` (ARCHIVED until `take-product-to-completion` is promoted) | mattpocock `grill-with-docs` or gstack `office-hours` |
| Production readiness | preset `quality-gate` | gstack `qa-only`, `health` optional |
| Greenfield feature | Human `/spec` + `/plan`, then one mission | agent-skills plugin |

Archived in-place: `gstack-quality` references demoted or parked missions and is intentionally
empty until those missions are promoted. Do not route it as a live starter bundle.

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
| `office-hours` | gstack | Product framing before `take-product-to-completion` (exploratory until promoted) |
| `autoplan` | gstack | Plan review gauntlet only — save plan, defer implement to fleet mission |

Invoke explicitly; record output path in `docs/fleet-program-progress.md` **Handoff notes**.

### Optional (coordinator, during mission)

| Skill | Source | Mission(s) | Trigger |
|-------|--------|------------|---------|
| `office-hours` | gstack | `take-product-to-completion` (exploratory) | T3 boundary ambiguous |
| `cso` | gstack | `adversarial-review-and-fix` | Security-heavy audit |
| `health` | gstack | `doc-sync`, `quality-gate` tail | User wants composite score |

### Worker (DISPATCH preamble)

| Skill | Source | Mission(s) | Role |
|-------|--------|------------|------|
| `test-driven-development` | agent-skills | `test-coverage` (and `bug-batch` once promoted) | @builder |
| `incremental-implementation` | agent-skills | build-heavy missions | @builder |
| `security-and-hardening` | agent-skills | `adversarial-review-and-fix` | @reviewer |
| `frontend-ui-engineering` | agent-skills | `design-integration` (exploratory; attach when promoted) | @builder |
| `domain-modeling` | mattpocock | `doc-sync` (and `take-product-to-completion` once promoted) | @planner |
| `qa` | gstack | UI missions (exploratory until promoted) | @builder (fix loop) |
| `qa-only` | gstack | UI missions (exploratory until promoted) | @reviewer (report only) |

Copy chosen rows into the mission `## Worker skills` table when authoring; the coordinator
pastes them into the engine WORKER SKILLS block on DISPATCH.

**Research stack (OPTIONAL, host-conditional — issue #86).** Binding resolves per engine.md's
RESEARCH LOOP (fleet-config `RESEARCH_TOOLS` → probed host tools → native web search fallback);
workers only invoke confirmed-present tools. When installed, these upgrade the stack:

| Skill | Source | Role (when present) |
|-------|--------|------|
| `monid` | monid CLI | `discover → inspect → run` any external source (web/exa, deps, CVE/OSV, repo, API, competitive) |
| `Context7` | MCP | pure current-library-docs lookups go straight here |
| `deep-research` | gstack/global | corroborate high-stakes findings (fan-out + adversarial verification) |

The DISCIPLINE attaches via the engine RESEARCH preamble on EVERY dispatch (not just missions that
list worker skills), so a mission need not re-declare them. Findings log to `docs/research-notes.md`;
T-FINAL records `unverified_assumptions: 0`.

### Post-gates (after campaign `PHASE: DONE`)

| Skill | Source | Campaign preset | When |
|-------|--------|-----------------|------|
| `ship` | gstack | `ship-with-proof` | User asked to open PR |
| `qa` | gstack | `ship-with-proof` | Staging URL available |
| `qa-only` | gstack | `quality-gate` | Report-only acceptance |
| `health` | gstack | `quality-gate` | Optional scorecard |

Post-gates are optional human steps — fleet campaign is DONE when all **mission nodes** complete
and `validate-fleet-outcome.sh` passes.

---

## Campaign presets using community skills

| Preset | Mission nodes | Pre-gate | Post-gate |
|--------|---------------|----------|-----------|
| `ship-with-proof` | audit → tests → docs | — | `ship`, `qa` |
| `align-then-ship` | `take-product-to-completion` | `grill-with-docs`, `office-hours` | `qa` *(exploratory)* |
| `quality-gate` | audit → tests | — | `qa-only`, `health` |

Archived in-place: `gstack-quality` references demoted or parked missions and is intentionally
empty until those missions are promoted; do not list it as a usable community preset.

YAML: `scripts/campaigns/<preset>.yaml` and
`skills/fleet-program/references/campaigns.md`.

---

## Community skill ids

Canonical ids used in campaign YAML and mission Optional/Worker tables:

| Upstream | Ids |
|----------|-----|
| gstack | `ship`, `qa`, `qa-only`, `health`, `office-hours`, `cso`, `design-review`, `browse`, … |
| agent-skills | `planning-and-task-breakdown`, `test-driven-development`, `code-simplification`, … |
| mattpocock | `grill-with-docs`, `grill-me`, `domain-modeling`, … |
| anthropics/skills | `skill-creator` |
| community/optional | `swiftui-liquid-glass` |

Install gstack with `./setup --host <cursor|claude|…>` from a gstack clone. Campaign presets and
mission tables use these ids as-is.

### Mission-referenced ids

Additional ids referenced by mission Optional/Worker tables:

| Id | Source | Description |
|----|--------|-------------|
| `skill-creator` | github.com/anthropics/skills | Anthropic's official skill authoring scaffold; used when missions need to draft or extend a skill. |
| `code-simplification` | agent-skills (community/optional) | Reuse / simplify / efficiency cleanup pass on a diff; pairs with `bug-batch` and `cleanup` missions (both exploratory; reattach on promotion). |
| `swiftui-liquid-glass` | community/optional | SwiftUI "Liquid Glass" design language helper; optional worker for `design-integration` on Apple-platform UI work (`design-integration` exploratory until promoted). |

---

## Anti-patterns

| Do not | Do instead |
|--------|------------|
| Load gstack + agent-skills meta-skills on coordinator | Pick fleet-program preset |
| Chain 6 slash commands manually | One `fleet-program` campaign |
| Auto-invoke grill/office-hours every run | Pre-gate only when Tier 3 or ambiguous |
| Skip `fleet-outcome` because QA passed | File ledger remains authoritative |
| `ship` mid-mission | Post-gate after docs node in `ship-with-proof` |
