# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Cursor, GitHub Copilot, Antigravity, Gemini CLI, OpenCode, Grok Build, Mogra, etc.) when working with code in this repository.

# Repository Overview

`autonomous-fleet` is a portable framework for running multi-agent engineering jobs designed for fully-autonomous coding runs across orchestration tools. A tool-agnostic **core** holds the method; thin **mission** skills describe specific jobs; per-tool **adapters** map the method to each runtime's real commands.

21 skills are organized into 3 tiers:

- 🟦 **Tier 1 · Infrastructure** (4) — engine, entry point, program orchestrator, setup
- 🟪 **Tier 2 · Adapters** (5) — Grok, Claude Code, Codex, Orca, template
- 🟧 **Tier 3 · Missions** (12) — doc-sync, test-coverage, dependency-update, cleanup, bug-batch, adversarial-review-and-fix, targeted-migration, design-integration, landing-page-convergence, legacy-rebuild, take-product-to-completion, inference-cost

# Skill Discovery

When working in this repo:

1. **Use the skill that matches the task.** Check `skills/` for relevant capabilities before implementing from scratch.
2. **Skills auto-activate via description.** Every `SKILL.md` description includes trigger phrases. Match those.
3. **Read `SKILL.md` top-to-bottom** before invoking — every skill has frontmatter declaring required deps, references to load, and validation gates.
4. **`SKILL.md` is the source of truth.** Per-skill `README.md` is human-facing scaffolding only; never duplicate spec content into the README.

# Execution Model

For every request:

1. **Determine if any skill applies.** If a mission fits, that's the path.
2. **For multi-mission work,** prefer `fleet-program` (chains + conditional DAGs) over manual orchestration.
3. **One mission active at a time per repo.** Cross-repo parallel is fine via separate sessions; same-repo parallel is not supported.
4. **Read `autonomous-fleet-core` first** when invoking any mission — it carries the engine's disciplines, guards, and outcome contracts.
5. **Pick exactly one adapter** for the runtime you're in. Don't mix.

# Repository Conventions

- Every skill lives in `skills/<name>/` with `SKILL.md` (agent-facing spec) + `README.md` (human-facing) + `assets/banner.{jpg,png}` + `assets/banner-prompt.txt`
- YAML frontmatter has `name` (must match directory) + `description` (1-1024 chars, with trigger phrases)
- Scripts go in `skills/<name>/scripts/`
- References (loaded on demand) go in `skills/<name>/references/`
- Top-level `docs/` is for repo-level decisions, reviews, and audit logs — not skill-specific content
- `tests/` covers the engine, campaign edge evaluator, sandbox guard, and dashboard

# Boundaries

- **Always:** Read `SKILL.md` before invoking. Set required env vars at runtime (in-memory only, never write to disk).
- **Always:** Run `./scripts/validate-all.sh` before committing skill changes.
- **Never:** Hardcode secrets in skill scripts. Use env vars.
- **Never:** Duplicate skill instructions in `README.md` — link to `SKILL.md` instead.
- **Never:** Modify a skill's banner or prompt without updating both together — they're coupled artifacts.

# Common Operations

- **Add a new skill:** Copy structure from an existing one (e.g. `doc-sync`), update `SKILL.md` frontmatter, generate a banner (see below), generate `README.md` from frontmatter, run validator.
- **Validate all skills:** `./scripts/validate-skills.sh` (single-skill) or `./scripts/validate-all.sh` (skills + fleet-outcome + goals + pytest).
- **Run a mission headless:** `./scripts/run-mission-headless.sh <adapter> <mission> --max-turns 50`
- **Run a campaign preset:** `./scripts/run-campaign.sh <adapter> --preset repo-health --dry-run`

# Imagery & Banners

The repo is anchored by **1 hero banner + 3 tier banners + 24 per-skill banners**. Every image has its prompt checked in alongside it — reproducer artifacts are first-class.

**Design language (keep new skills consistent):**

- **Style:** Clean schematic / cockpit / control-room aesthetic. Engineering-serious. Linear.app + Vercel + GitHub-Actions dark-mode feel. NOT photorealistic, NOT cyberpunk, NOT neon, NOT terminal-poster dense.
- **Aspect ratio:** 2:1 (~1200×600) for skill + tier banners; 16:9 for the repo hero.
- **Background:** Deep midnight `#0B1220` (with optional subtle gradient toward `#0F172A` at edges).
- **Primary accent:** Warm amber `#F59E0B`.
- **Secondary accent:** Cool slate / steel blue `#94A3B8`.
- **Highlight:** White `#FFFFFF` (sparingly).
- **Ink for text:** Warm off-white `#F8FAFC`.
- **Composition logic:** Each banner tells the skill's story in one glance via abstract isometric or schematic illustration. Engine → adapter banners use a left-cube → right-card layout; mission banners use whatever shape best represents the action (progress bar, spiral, DAG, sync arrows, etc.).
- **Required labels:** Top-left `skills/<name>` in small monospace; bottom-center thin amber line + one-line caption.

**Generation pipeline:**

```bash
# Requires $OPENROUTER_API_KEY
bash /path/to/agent-skills/skills/terminal-poster/scripts/generate.sh \
  skills/<name>/assets/banner-prompt.txt \
  skills/<name>/assets/banner.png
```

- **Model:** Nano Banana Pro (`google/gemini-3-pro-image-preview`) via OpenRouter
- **Cost:** ~$0.002–0.01 per image
- **Latency:** ~30 seconds. **Generate candidates in parallel** via background bash when iterating.

**Known gotchas (DO NOT REPEAT):**

🔴 **Nano Banana Pro often returns JPEG even when you write to `.png`.** Sniff magic bytes after generation (`\xff\xd8\xff` = JPEG, `\x89PNG` = PNG) and rename. The generator script warns you but doesn't auto-rename.

🔴 **The model drops, duplicates, or garbles text labels** under load. Past failures across the agent-skills sibling repo: "HACKER NUDS" instead of "HACKER NEWS", GITHUB rendered twice while EXA was dropped entirely, "example.com" rendered as "onomplo.com".

Fixes:
- Add explicit constraints: "the word X must appear exactly once", "do not duplicate any label", "do not render fake domain names"
- Render labels OUTSIDE cards (below them), not inside
- List the FULL set of expected labels with quoted exact text and the phrase "EXACTLY"

🔴 **Always vision-audit before shipping.** After generation, run `read(path, prompt="List the text labels visible")` — it catches problems that are invisible at thumbnail size. If text is wrong, regenerate with a tighter prompt; don't try to upscale-fix.

**Adding a banner to a new skill:**

1. Write `skills/<name>/assets/banner-prompt.txt` following the design language above
2. Generate with the command above
3. Sniff format and rename if needed (JPEG-as-PNG quirk)
4. Vision-audit for spelling/legibility
5. Reference in the skill's README: `<img src="assets/banner.{jpg,png}" alt="<name> — autonomous-fleet skill" width="100%">` above the description
6. Commit both the image AND the prompt — reproducers are first-class artifacts in this repo

# See Also

- [README.md](README.md) — framework overview, installation, available skills
- [docs/](docs/) — decisions log, reviews, audit reports, research notes
- Sibling repo: [ravidsrk/agent-skills](https://github.com/ravidsrk/agent-skills) — complementary capability-skill collection (DNS, AWS migration, research, image gen). Different visual identity (warm cream + coral) for clarity.
