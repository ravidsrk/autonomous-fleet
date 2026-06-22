# autonomous-fleet-adapter-orca

<p align="center">
  <img src="assets/banner.png" alt="autonomous-fleet-adapter-orca — autonomous-fleet skill" width="100%">
</p>

> The ORCA adapter for autonomous-fleet-core.

🟪 **Tier 2 · Adapter** — runtime bridge to one specific agent runtime

# Full description

The ORCA adapter for autonomous-fleet-core. Maps each engine PRIMITIVE (spawn worker, dispatch, wait, inspect, place, worker_done/ask/reply, open/merge PR, sync task state) to the real Orca orchestration CLI commands. Load this alongside autonomous-fleet-core when running a mission on Orca. Handles Orca's worktree/terminal model, --inject dispatch, check --wait supervision, version-tolerant worker_done, and task-update syncing. Default agent handles: @grok builds, @codex reviews (codex exec), @claude integrates — overridable by the mission's role pipeline.

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet-adapter-orca -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
