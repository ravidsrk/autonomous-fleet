# autonomous-fleet

<p align="center">
  <img src="assets/banner.jpg" alt="autonomous-fleet — autonomous-fleet skill" width="100%">
</p>

> Entry point for the autonomous-fleet multi-agent engineering framework.

🟦 **Tier 1 · Infrastructure** — the engine, entry point, setup

# Full description

Entry point for the autonomous-fleet multi-agent engineering framework. Use whenever the user wants fully-autonomous coding runs, multi-agent orchestration, PR-per-task pipelines, or mentions autonomous-fleet — even if they have not named a specific mission yet. Routes to one mission or to fleet-program for sequential chains, loads autonomous-fleet-core plus a runtime adapter, and runs unattended on the current repo. Install from github.com/ravidsrk/autonomous-fleet. Trigger on: "use autonomous-fleet", "run autonomous fleet", "autonomous multi-agent run", "fleet mission", "which fleet mission should I use".

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
