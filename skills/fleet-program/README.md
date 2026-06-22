# fleet-program

<p align="center">
  <img src="assets/banner.png" alt="fleet-program — autonomous-fleet skill" width="100%">
</p>

> Orchestrate autonomous-fleet missions on one repo — sequential chains and conditional campaign DAGs with if-outcome edges.

🟦 **Tier 1 · Infrastructure** — the engine, entry point, setup

# Full description

Orchestrate autonomous-fleet missions on one repo — sequential chains and conditional campaign DAGs with if-outcome edges. Reads fleet-outcome YAML from each mission's readiness doc to branch (e.g. audit then tests if no P0s, else dependency-update). One mission active at a time per repo; cross-repo parallel via separate sessions. Does not run parallel missions on the same repo. Use for "repo health program", "audit then test", "docs then bugs if needed", mission chains, fleet campaign, ship with proof, align then ship, quality gate. Install from github.com/ravidsrk/autonomous-fleet. Trigger on: "fleet program", "fleet campaign", "mission chain", "if P0 then", "repo health", "conditional fleet run", "ship safely", "ship with proof", "finish stalled product", "align then ship", "production ready", "quality gate".

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill fleet-program -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
