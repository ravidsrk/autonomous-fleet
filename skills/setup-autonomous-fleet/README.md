# setup-autonomous-fleet

<p align="center">
  <img src="assets/banner.png" alt="setup-autonomous-fleet — autonomous-fleet skill" width="100%">
</p>

> User-invoked setup only — do not auto-activate.

🟦 **Tier 1 · Infrastructure** — the engine, entry point, setup

# Full description

User-invoked setup only — do not auto-activate. Configure a repo for autonomous-fleet: runtime adapter, branch prefix, default campaign bundle, optional community installs. Run when the user says setup autonomous fleet, configure fleet, or first fleet run on a repo.

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill setup-autonomous-fleet -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
