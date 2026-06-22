# autonomous-fleet-adapter-codex

<p align="center">
  <img src="assets/banner.jpg" alt="autonomous-fleet-adapter-codex — autonomous-fleet skill" width="100%">
</p>

> The CODEX adapter for autonomous-fleet-core.

🟪 **Tier 2 · Adapter** — runtime bridge to one specific agent runtime

# Full description

The CODEX adapter for autonomous-fleet-core. Maps each engine PRIMITIVE to OpenAI Codex mechanics — subagents, git worktrees, shell for git/gh, and the file ledger as durable truth. Load alongside autonomous-fleet-core when running a mission in Codex (app, IDE, or CLI). The coordinator IS the main Codex thread; workers are subagents or worktree-scoped sessions; the file ledger survives compaction.

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet-adapter-codex -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
