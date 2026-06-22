# autonomous-fleet-adapter-template

<p align="center">
  <img src="assets/banner.png" alt="autonomous-fleet-adapter-template — autonomous-fleet skill" width="100%">
</p>

> TEMPLATE for writing a new autonomous-fleet adapter (e.g.

🟪 **Tier 2 · Adapter** — runtime bridge to one specific agent runtime

# Full description

TEMPLATE for writing a new autonomous-fleet adapter (e.g. codex, gemini-cli, a custom CLI fleet, or a raw tmux+worktrees setup). Copy this, rename to autonomous-fleet-adapter-YOUR-TOOL, and fill in how YOUR runtime implements each PRIMITIVE the core calls. The missions and the core never change — only this mapping does. Use when adding a new orchestration runtime to autonomous-fleet. Not a runnable mission skill.

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet-adapter-template -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
