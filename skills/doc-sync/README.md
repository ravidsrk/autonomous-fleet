# doc-sync

<p align="center">
  <img src="assets/banner.png" alt="doc-sync — autonomous-fleet skill" width="100%">
</p>

> [Tier 1 · highest cross-agent merge-success category (documentation) · safe to run unattended] Bring a repo's documentation back into alignment with its actual code: README, docs/, AGENTS.md/CLAUDE.md, API references, setup/usage instructions, code comments that have drifted, and inline examples that no longer run.

🟧 **Tier 3 · Mission** — a discrete engineering job, safe to compose

# Full description

[Tier 1 · highest cross-agent merge-success category (documentation) · safe to run unattended] Bring a repo's documentation back into alignment with its actual code: README, docs/, AGENTS.md/CLAUDE.md, API references, setup/usage instructions, code comments that have drifted, and inline examples that no longer run. Use when docs are stale, after a refactor or dependency change, when onboarding docs are wrong, or for a periodic documentation-truth pass. This is a documentation mission ONLY — it does not change application behaviour or logic; it makes the docs match the code as it actually is. Runs fully autonomously via the autonomous-fleet-core engine. Trigger on: "sync the docs", "our README is out of date", "docs don't match the code", "update documentation", "fix onboarding/setup instructions", "documentation audit".

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill doc-sync -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
