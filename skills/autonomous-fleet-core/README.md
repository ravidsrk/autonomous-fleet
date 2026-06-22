# autonomous-fleet-core

<p align="center">
  <img src="assets/banner.png" alt="autonomous-fleet-core — autonomous-fleet skill" width="100%">
</p>

> The portable, tool-agnostic ENGINE for running fully-autonomous multi-agent engineering jobs.

🟦 **Tier 1 · Infrastructure** — the engine, entry point, setup

# Full description

The portable, tool-agnostic ENGINE for running fully-autonomous multi-agent engineering jobs. Mission skills (doc-sync, test-coverage, dependency-update, cleanup, bug-batch, adversarial-review-and-fix, targeted-migration, design-integration, landing-page-convergence, legacy-rebuild, take-product-to-completion) invoke THIS engine plus exactly one ADAPTER (orca, claude-code, grok, or another runtime). This core holds everything that does NOT depend on orchestration tool: self-orientation, fully-autonomous coordinator behaviour with file-ledger boolean gates, context-handoff to survive compaction, the worker-placement DECISION LOGIC (dependent vs independent), the PR-per-task pipeline with commits-preserved + conflict-aware merge + worktree cleanup, the empirical risk tiers, safety rails, secret hygiene, and commit/authorship policy. It speaks in PRIMITIVES; the ACTIVE ADAPTER maps each primitive to its tool's real commands. Load with a mission skill and one runtime adapter — do not run alone.

# Source of truth

🟢 **[`SKILL.md`](./SKILL.md)** — agent-facing spec. Anything agents need (process, references, scripts, validation gates) lives there.

This README is a thin human-facing surface. Skill behavior is governed entirely by `SKILL.md` and its references/.

# Quick install

```bash
npx skills add https://github.com/ravidsrk/autonomous-fleet \
  --skill autonomous-fleet-core -y
```

Then activate in your agent (e.g. Claude Code, Cursor, Grok, Codex, or Mogra) and reference by name.

# See also

- [autonomous-fleet README](../../README.md) — full framework overview
- [AGENTS.md](../../AGENTS.md) — repo conventions for AI coding agents
