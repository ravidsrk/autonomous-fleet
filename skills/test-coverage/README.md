# test-coverage

<p align="center">
  <img src="assets/banner.png" alt="test-coverage — autonomous-fleet skill" width="100%">
</p>

> [Tier 1 · lower-than-doc/build cross-agent merge-success (test) · guard hollow-test risk] Raise real test coverage on a repo or a target area with behaviour-exercising tests — not coverage-padding stubs.

🟧 **Tier 3 · Mission** — a discrete engineering job, safe to compose

# Full description

[Tier 1 · lower-than-doc/build cross-agent merge-success (test) · guard hollow-test risk] Raise real test coverage on a repo or a target area with behaviour-exercising tests — not coverage-padding stubs. Use when a module is undertested, before a refactor to lock current behaviour, after a feature shipped without tests, or for a periodic coverage pass. Adds/strengthens unit, integration, and where relevant UI tests that genuinely assert behaviour; does NOT change application logic. Runs fully autonomously via the autonomous-fleet-core engine. Trigger on: "add tests", "raise coverage", "this module has no tests", "write tests for X", "improve test coverage", "lock current behaviour with tests".

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill test-coverage -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
