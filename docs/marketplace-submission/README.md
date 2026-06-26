# Marketplace Submission Packet

Everything needed to submit both repos to the **Claude Code Community Marketplace** (`anthropics/claude-plugins-community`).

# What submission means

When Anthropic approves a submission, your plugin entry lands in [`claude-plugins-community/.claude-plugin/marketplace.json`](https://github.com/anthropics/claude-plugins-community/blob/main/.claude-plugin/marketplace.json) (2,200+ plugins as of June 2026). Users discover and install via:

```bash
/plugin marketplace add anthropics/claude-plugins-community
/plugin install autonomous-fleet@claude-community
/plugin install agent-skills@claude-community
```

CI automatically bumps the pinned SHA when you push new commits, so future updates flow through without re-submitting.

# Two submission forms (pick ONE per repo)

🟦 **Console form** (use this — works for individual authors):
https://platform.claude.com/plugins/submit

🟪 **claude.ai form** (requires Team/Enterprise org + directory admin):
https://claude.ai/admin-settings/directory/submissions/plugins/new

Both feed the same review pipeline. Use the Console form unless you already have a Team org with directory management access.

# What's new since the last submission

The submission packet was last refreshed at SHA `2a0f7b9664fac8c19f192bac26809ee9f7360fd4`.
Since then (PRs #37, #38, and the `roadmap/post-substrate-impl` branch), the
following substrate work has shipped and is reflected in the updated packet
description:

🟢 **4-layer verification substrate** — schema-checked review findings (Layer 1),
opt-in evidence-gating Stop hook (Layer 2), blind-fix anti-anchoring guard with
mtime-ordering invariant (Layer 3), manifest-audited run archive with
sha256 + mtime ordering (Layer 4). All four layers have Python verifiers,
100%-coverage tests, and substrate-specific mutations in the standing gate
(15+ mutations caught).

🟢 **Mission demotion** — 9 unproven missions moved to
`docs/exploratory/missions/` pending real-run promotion evidence. The packet
description now lists only the 3 shipped missions plus the `fleet-program`
shell. Promotion criteria documented; no missions deleted.

🟢 **Versioned trace contract** — `fleet-trace.schema.json` v1.0 emits one
JSONL line per state transition into `.fleet/runs/<run_id>/trace.jsonl`.
vibe-kanban, Claude Code Agent View, and custom dashboards are interchangeable
consumers. Closes landscape Gap 8 without building UI.

🟢 **Write-lock discipline** — construction + request locks under
`.fleet/runs/<run_id>/locks/` with confirmed-dead-only steal mechanism.
Engine block in `engine.md` § WRITE-LOCK DISCIPLINE.

🟢 **Seat-analysis primitive** — `scripts/analyze_seat.py` computes per-run and
aggregate findings/cost/wallclock metrics across all archives, surfacing the
"earns its seat" signal across model/role pairs.

🟡 **Adversarial bench (results pending operator runs)** — scaffolding for a
substrate-off vs substrate-on comparator across 5 OSS targets. Methodology
shipped at `docs/external-dogfood/adversarial-bench-2026-06.md`. Numbers will
be cited in the next packet refresh once operator runs land.

🟢 **v0.1.0 + representative trace emission** — tagged release includes
`scripts/emit_representative_trace.py`, nine-primitive example-fixture trace,
`validate-headless.sh` gate, and 67+ real-world scenario tests. Mechanical
repro before submit:

```bash
./scripts/validate-all.sh
./scripts/validate-headless.sh
python scripts/emit_trace.py validate .fleet/runs/example-fixture/trace.jsonl
```

🟡 **Console submit — PENDING human operator** — form at
https://platform.claude.com/plugins/submit ; re-pin SHA to latest `main` at submit time.

# Pre-submission checklist (already done ✅)

- ✅ Both repos have `.claude-plugin/plugin.json` at the root
  - autonomous-fleet: SHA bumped to the latest `roadmap/post-substrate-impl` commit (re-pin at PR merge)
  - agent-skills: `813d097d0fe9fba2c30287a116034ef5ebdf3595`
- ✅ Both have `SKILL.md` files following the agentskills.io spec
- ✅ Both have full READMEs with banners + install instructions
- ✅ Both are MIT licensed
- ✅ Both have CI green on the submission SHA
- 🟡 Optional pre-submit: run `claude plugin validate` locally (the review pipeline runs the same check)

# Submission packet for `autonomous-fleet`

**Repository:** https://github.com/ravidsrk/autonomous-fleet
**Pinned SHA:** `2a0f7b9664fac8c19f192bac26809ee9f7360fd4` (the actual submission SHA bumps to the Commit-G merge commit; the four prior commits A–F precede it).
**Category:** development
**One-line pitch:** Multi-agent engineering framework for fully-autonomous coding runs. One portable engine. 4 runtime adapters. **3 shipped missions** + `fleet-program` campaign shell + a 4-layer verification substrate (schema-checked review findings, evidence-gating Stop hook, blind-fix anti-anchoring, manifest-audited run archive).

**Description** (paste into form):

> Portable multi-agent engineering framework for fully-autonomous coding runs. One tool-agnostic core engine, per-runtime adapters (Claude Code, Codex, Grok, Orca), and three shipped mission skills (`doc-sync`, `test-coverage`, `adversarial-review-and-fix`) composable into multi-step engineering campaigns via the `fleet-program` shell. A four-layer verification substrate (Layer 1 schema-checked review findings + reviewer source verifier; Layer 2 opt-in evidence-gating Stop hook; Layer 3 blind-fix anti-anchoring guard; Layer 4 manifest-audited run archive with sha256 + mtime ordering) moves "done" from self-attestation toward on-disk evidence. Twelve additional missions ship as exploratory documentation (`docs/exploratory/missions/`) and re-promote on first real-run progress + readiness + external archive triple.

**Marketplace entry** (ready-to-paste JSON): see [`autonomous-fleet.marketplace-entry.json`](./autonomous-fleet.marketplace-entry.json)

# Submission packet for `agent-skills`

**Repository:** https://github.com/ravidsrk/agent-skills
**Pinned SHA:** `813d097d0fe9fba2c30287a116034ef5ebdf3595`
**Category:** development
**One-line pitch:** Production-grade capability skills for AI coding agents. 5 battle-tested skills covering cloud infrastructure, research, and image generation.

**Description** (paste into form):

> Production-grade capability skills for AI coding agents. Five battle-tested skills: cloudflare-dns (migrate DNS from any registrar to Cloudflare with bulk record import and registrar nameserver flip), fly-to-aws-migration (end-to-end Fly.io → AWS migration playbook covering Postgres → Aurora, Machines → ECS Fargate, secrets, DNS cutover), deep-research (parallel multi-source research across X, Reddit, HackerNews, GitHub, Polymarket, YouTube, and Exa neural search), terminal-poster (dense retro-cyberpunk viral infographics via Nano Banana Pro), and ai-image-generation (best-in-class image generation routing). MIT licensed.

**Marketplace entry** (ready-to-paste JSON): see [`agent-skills.marketplace-entry.json`](./agent-skills.marketplace-entry.json)

# After submission

Approved plugins are pinned to a specific commit SHA in `claude-plugins-community` and the CI automatically bumps the pin on subsequent pushes to the source repo. The public catalog syncs nightly. Check whether your plugin is installable:

```bash
grep -i "autonomous-fleet\|agent-skills" <(curl -sL https://raw.githubusercontent.com/anthropics/claude-plugins-community/main/.claude-plugin/marketplace.json)
```

There's no SLA on review time — usually within a few days. If you don't see it after a week, follow up on the form's reply thread or open an issue at `anthropics/claude-plugins-community`.

# Other marketplaces (optional)

These are smaller/independent registries — useful for discoverability but not required:

| Marketplace | Submit at | Notes |
|---|---|---|
| 🟪 **claude-plugins-official** | (curated, no application) | Anthropic picks. Don't submit. |
| 🟦 **claude-plugins-community** | platform.claude.com/plugins/submit | **Primary target** — 2,200+ plugins |
| 🟦 **Agent Skill Hub** | https://agentskillhub.dev | GitHub import via web UI |
| 🟦 **skills.re** | https://skills.re/submit | GitHub URL import |
| 🟦 **agentskillsindex.com** | https://agentskillsindex.com | Public registry |
| 🟦 **SkillsMP** | https://skillsmp.com | Manus marketplace mirror |
| 🟦 **aiskillstore/marketplace** | github.com/aiskillstore/marketplace (PR) | Security-audited mirror |

The Community marketplace is by far the highest-value submission. Everything else is nice-to-have.

# Files in this packet

- `README.md` — this file
- `autonomous-fleet.marketplace-entry.json` — ready-to-paste marketplace.json entry
- `agent-skills.marketplace-entry.json` — same, for agent-skills
- `announcement-banner.jpg` — side-by-side banner for X/LinkedIn announcement
- `announcement-copy.md` — drafted post copy for X + LinkedIn + dev.to
