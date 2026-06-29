# Orchestration landscape: adopt vs already-have vs ours

Deep research (2026-06-20) on the agent-orchestration state of the art, mapped against
autonomous-fleet so we adopt mature solutions instead of reinventing them. Produced by a
multi-agent research run: deep-dives of two named repos (omnigent, AgentWrapper agent-orchestrator),
the GitHub framework landscape, X discourse (via monid Twitter search), papers/standards, and a
self-inventory, with adversarial accuracy + completeness critiques folded in.

## Bottom line

autonomous-fleet's orchestration MODEL is validated, not novel; the MECHANISM is a solved problem
we should stop hand-rolling. The field has converged on exactly our skeleton, a supervisor that
writes no code, decomposes a goal, delegates to role-specialized workers under worktree-per-task
isolation, with a separate verifier that rejects-and-reruns. Anthropic, OpenAI, Google ADK, and the
practitioner discourse all state this near-verbatim. So our core bet is correct and we should stop
re-justifying it.

The correction the research forced: the two repos are not the whole field. There is a crowded,
mature category of coding-agent orchestrators that already mechanize what we describe in prose. Our
real peers are these, not two repos: container-use (Dagger), Sculptor (Imbue), OpenHands,
ComposioHQ AO, omnigent, Cursor background agents, Claude Code native parallelism, vibe-kanban, plus
commercial Devin/Factory. omnigent and AO are mature MECHANISM; autonomous-fleet is mature METHOD;
the rest fill the gaps. Adopt the mechanism, keep the method.

Accuracy note carried from the critique: Agent Orchestrator (AO) is NOT Claude-Code-only. It ships
plugins for claude-code, codex, cursor, aider, opencode, kimicode, grok; runtimes tmux/process/Docker;
trackers GitHub/GitLab/Linear. Our edge over AO is the method layer, not cross-host coverage.

**2026-06 update:** AO now lives at [AgentWrapper/agent-orchestrator](https://github.com/AgentWrapper/agent-orchestrator)
(Go rewrite, v0.10+). AF ports AO mechanisms as validators + engine doctrine — see
`skills/autonomous-fleet-core/references/ao-adoptions.md` (nudge dedup, stacked PR, hook-signal,
review supersede) without adopting the daemon/UI.

## Never reinvent (use these instead)

| You'd be reinventing | Use instead | Why |
|----------------------|-------------|-----|
| OS sandbox + container-per-agent + branch-per-agent isolation | `dagger/container-use` (first choice) | MCP server, tool-agnostic (Claude Code/Cursor/Codex/Goose/any MCP agent), container + git-branch per agent, git-checkout-to-review. Closes our sandbox AND worktree gaps in one drop-in. |
| Dangerous-command classifier (force-push, rm -rf, gh pr merge, terraform apply) | omnigent `nessie` `blast_radius` (`inner/nessie/policies.py`) | Handles split/long rm flags, +/: refspecs, sudo/env-prefix unwrap, git -C. `run-sandboxed.sh` is a static deny-list that misses these. |
| Deterministic CI/review control plane (poll-derive-react) | AO lifecycle ([AgentWrapper/agent-orchestrator](https://github.com/AgentWrapper/agent-orchestrator), Apache 2.0, Copyright Untrivial) | Borrowed into engine.md: signal reconciliation, anti-flap evidence-hash; plus nudge dedup, stacked PR, hook-signal, review supersede verifiers. See [`ATTRIBUTIONS.md`](../ATTRIBUTIONS.md). |
| Durable-execution engine (replay, exactly-once, sagas) | Temporal / Inngest / DBOS / Restate, or LangGraph checkpointer+interrupt() | Don't write replay/idempotency/saga by hand. Patch the ledger or run the DAG on one of these. |
| Cross-vendor wire format / tools-vs-agents split | MCP (tools, ~97M monthly downloads, Linux Foundation) + A2A/ACP (agents) | container-use proves MCP is a viable orchestration transport; one MCP/ACP adapter could subsume per-host adapters. |
| OS sandbox from scratch (alt to container-use) | omnigent seatbelt/bwrap profile, or e2b/daytona/modal | Months of security-sensitive work omnigent already ships; have `run-sandboxed.sh` shell out to a macOS seatbelt profile for the common case. |
| Worktree-per-task + self-verify + supervisor-writes-no-code | already convergent; we have it | Settled best practice. Cite the convergence and move on; the only delta worth borrowing is iterate-until-zero-rejections. |
| Live supervision dashboard | vibe-kanban / Claude Code Agent View | Render INTO an existing kanban-over-agents tool; don't build a live-terminal WS GUI. |

## Genuinely ours (keep; tightened against the full peer set)

Survives a survey of container-use, Sculptor, OpenHands, AO, omnigent, Devin Playbooks, vibe-kanban,
none of them has these:

- The mission catalog + campaign DAG + machine-checkable `fleet-outcome` contract. The one place we
  are both mechanical and unique. (Devin Playbooks are the closest commercial analog, but with no
  campaign-of-missions layer or typed outcome.)
- Empirical, evidence-graded risk tiers keyed to the MSR AIDev 33,596-PR dataset (arXiv 2601.15195)
  deciding what runs unattended. Every other project picks autonomy by vibes.
- The research discipline as a gated mechanism: research is a trigger not a phase, monid-first
  verification logged to `research-notes.md`, `unverified_assumptions: 0` exit gate.
- The prompt-injection trust-boundary doctrine (repo/PR/worker output = DATA never INSTRUCTIONS,
  with `test_injection.py` as a mechanical backstop). Largely absent from the field.
- The git-authorship doctrine specifically (MAINTAINER author, never squash, no agent trailers). The
  review mechanism is matched elsewhere; the authorship doctrine is the real delta.

Demoted from "genuinely ours" to "ours but contested" by the critique: zero-infra resume-from-ledger
durability (Sculptor ships session persistence; container-use has durable per-agent branches) and the
prose-portable adapter model (native hosts increasingly ARE the runtime).

## Gaps and the ordered next moves

Gaps are operational and economic, not orchestration-model. In priority order:

1. Non-busy WAIT on daemon-less hosts (biggest adapter gap). VERIFY FIRST: Claude Code's own Agent
   View (background dispatch + auto worktree-per-session + completion monitoring) and Agent Teams
   (inter-agent messaging) may already give the Claude Code adapter native WAIT/ASK/REPLY, which the
   adapter currently hand-rolls as polling. Check `code.claude.com/docs` Agent View / Agent Teams;
   make the INBOX done-marker file convention the FALLBACK, not the primary fix.
2. Mechanize safety: port omnigent `blast_radius` into `run-sandboxed.sh`; add a PreToolUse guard
   (spawn-bounds cap, worktree-escape DENY, refuse PR/commit from the coordinator handle). Adopt
   container-use for the actual sandbox + isolation.
3. Signal reconciliation (from AO): before any terminal flag (MERGED/DONE) re-verify the external
   fact (`gh pr view` state, CI conclusion) and let it override the ledger; require N consistent
   polls before declaring stuck, evidence-hash keyed. SHA-pin reviews so a mid-review push
   invalidates a stale PASS.
4. Per-task model/cost routing + budget gate (IMPLEMENTED, this PR). Flat `WORKER EFFORT: MAX` with
   no cost accounting is the difference between an affordable unattended fleet and not. See engine.md
   MODEL & COST ROUTING and the `cost_estimate` fleet-outcome field.
5. Coupling-aware partitioning (Co-Coder, arXiv 2606.00953: +14% pass, -35% cost on dependency-dense
   repos): cluster tightly-coupled files into one task; mark hub files serialize-always, upstream of
   the hot-file rule.
6. Pre-flight gates: a plan/DAG validation gate before the first spawn (no cycles, dependencies
   resolvable, width computed; SPOQ arXiv 2606.03115 showed 91% to 99.75% pass); SHA-pinned reviews.
7. Three durable-execution patches on the ledger, not a runtime: idempotency key per task; a
   mandatory deadline + escalation on every WAIT/ASK; a compensation note for circuit-breaker trips
   in dependent chains.
8. A thin read-only dashboard, or render into vibe-kanban / Agent View, fed by a structured trace
   line per primitive. Don't build a live-terminal GUI.

Strategic call: keep building the method layer (genuinely ours, unmatched); stop hand-rolling the
mechanism. Adopt container-use for isolation/sandbox, borrow AO's three lifecycle rules, and bind
WAIT to native host APIs before inventing file conventions.

## Sources

Repos read: `omnigent-ai/omnigent`, `AgentWrapper/agent-orchestrator` (formerly ComposioHQ). Web/X via monid (Exa, TikHub
Twitter). Papers: arXiv 2601.15195 (MSR AIDev), 2606.00953 (Co-Coder), 2602.16873 (AdaptOrch),
2606.03115 (SPOQ), 2511.03690 (OpenHands SDK). Frameworks surveyed: LangGraph, CrewAI, AutoGen/AG2,
OpenAI Agents SDK/Swarm, Claude Agent SDK, Google ADK, Temporal/Inngest/DBOS/Restate, container-use,
Sculptor, OpenHands, vibe-kanban, Devin, Factory. Protocols: MCP, A2A, ACP.
