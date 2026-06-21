# Orchestration decisions

Three strategic calls forced by the landscape research (`docs/orchestration-landscape.md`,
2026-06-20). The landscape's bottom line: our MODEL is validated, the MECHANISM is a solved problem
we should stop hand-rolling. These three decisions are where "stop hand-rolling" turns into a
concrete bet. Each records the call, the rationale, the alternatives, and a written trigger for when
to revisit, so a future run does not relitigate from scratch.

Format: one decision per section. Recommendation is the default the fleet adopts now; alternatives
are the options we considered and would fall back to; revisit-when is the named condition that
reopens the call.

## Decision 1: sandbox-by-reference default

Recommendation: adopt `dagger/container-use` as the default placement + OS-sandbox substrate. See
`docs/adopt-container-use.md` for the primitive mapping and per-adapter wiring.

Rationale: it closes two open gaps in one move. The engine currently has worktree-per-task isolation
hand-rolled per adapter (raw `git worktree`) and only a deny-list for the OS sandbox
(`run-sandboxed.sh`, which by its own RESIDUAL RISK note does not confine filesystem or network).
container-use is an MCP server that gives each agent a container plus its own git branch, is
tool-agnostic across every adapter host, and exposes git-checkout-to-review. It is an adapter-layer
drop-in: the core keeps calling `PLACE`/`CLEANUP` by name. We were going to need an OS sandbox AND
real worktree isolation regardless; this is one dependency that satisfies both, maintained by Dagger,
instead of two things we maintain.

Alternatives (also our fallback ladder, recorded in `fleet-config.md` per run):
- omnigent seatbelt/bwrap (`omnigent/inner/seatbelt_sandbox.py`, `bwrap_sandbox.py`): real same-host
  filesystem/network confinement, no container runtime required. The fallback when a host has no
  Docker. Months of security-sensitive work omnigent already ships; we shell `run-sandboxed.sh` out
  to it rather than write a sandbox.
- e2b / daytona / modal: remote microVM per worker. The fallback when the host can't sandbox locally
  but can reach a sandbox API. Heavier, network-dependent, reserve for untrusted or hosted fleets.
- bare `run-sandboxed.sh`: deny-list + secret scrub, no OS confinement. Acceptable only for trusted
  self-owned repos with no production credentials present.

Revisit when: container-use stops being maintained or its MCP transport breaks against a host we
support; or a host we must support has neither MCP nor Docker (then seatbelt/bwrap becomes the
default for that host, not the fallback); or we start running genuinely untrusted third-party repos
at volume (then re-weigh remote microVM isolation as the default for that class).

## Decision 2: evaluate ComposioHQ AO as the single-host supervisor under our method layer

Recommendation: for single-machine GitHub campaigns, evaluate running ComposioHQ
agent-orchestrator (AO) as the deterministic supervisor/control plane, with autonomous-fleet as the
METHOD layer on top. Do not rewrite AO's lifecycle engine in prose; borrow it or run on it. This is a
spike-and-decide, not an immediate adoption: prove the seam on one Tier 1 single-host campaign first.

Rationale: AO ships a tested, deterministic lifecycle engine (`packages/core/src/
lifecycle-status-decisions.ts`, MIT) plus runtime plugins (tmux/process/Docker) and tracker plugins
(GitHub/GitLab/Linear). That is exactly the poll-derive-react control plane the landscape says we
should stop hand-rolling. AO is also NOT Claude-Code-only: it plugs claude-code, codex, cursor,
aider, opencode, kimicode, grok. So the honest fleet-vs-AO delta is not cross-host coverage, it is
the method.

The honest delta (what is ours vs what is theirs):
- Ours (the method layer AO does not have): the mission catalog + campaign DAG + machine-checkable
  `fleet-outcome` contract; the empirical risk tiers (MSR AIDev 33,596-PR dataset) deciding what runs
  unattended; the research gate (research-as-trigger, monid-first, `unverified_assumptions: 0` exit);
  the prompt-injection trust boundary (repo/PR/worker output = DATA never INSTRUCTIONS, with
  `test_injection.py` as the mechanical backstop); the git-authorship doctrine (MAINTAINER author,
  never squash, no agent trailers).
- Theirs (the mechanism we would stop hand-rolling): the tested lifecycle/state engine, signal
  reconciliation, runtime/tracker plugins. AO is mature MECHANISM; we are mature METHOD.

The seam: AO runs the lifecycle (spawn, poll, derive status, react to CI/review signals) on one host;
autonomous-fleet supplies the mission/campaign contract, the risk-tier gating, the research gate, and
the injection boundary as the layer that decides WHAT runs and WHETHER it is allowed to run
unattended. AO answers "is this PR done"; we answer "should this mission run unattended, what is the
campaign edge, did the build verify its external facts". The minimum viable proof: drive one Tier 1
single-host GitHub campaign (e.g. doc-sync or dependency-update) with AO as the supervisor and the
fleet contract as the method, and confirm the `fleet-outcome` validator still passes end to end.

Alternatives:
- Keep the prose control plane, borrow only AO's three lifecycle rules into engine.md (signal
  reconciliation, anti-flap evidence-hash, oscillation-aware CI budget), as the landscape's next-move
  3 already proposes. Lower integration cost, but we keep maintaining the lifecycle engine in prose.
- Full custom control plane (status quo): rejected by the landscape: hand-rolling a tested mechanism.

Revisit when: AO's lifecycle API or plugin contract changes materially; or a campaign needs
multi-host coordination AO does not model (then AO-as-single-host-supervisor stops fitting and we
re-weigh); or the spike shows the method layer cannot cleanly sit on top of AO's state model without
leaking AO's lifecycle assumptions into our mission contract.

## Decision 3: evaluate ONE protocol adapter to subsume several per-host adapters

Recommendation: evaluate a single protocol adapter (MCP-server or ACP) that subsumes several of the
five per-host adapters (claude-code, codex, grok, orca, template), instead of one hand-written
adapter per tool. Spike against the two hosts that already speak the protocol; keep the per-host
adapters until the protocol adapter passes the same composition tests.

Rationale: we maintain five adapters that each re-resolve the same PRIMITIVES to a different tool's
native commands. The landscape notes MCP is a viable orchestration transport (container-use proves
it: one `container-use stdio` server, every host) and that one MCP/ACP adapter could subsume per-host
adapters. If a host speaks MCP (tools) or ACP (agent-to-agent), the adapter resolves SPAWN/DISPATCH/
WAIT/INSPECT through the protocol once, and every conforming host inherits it. That collapses
N hand-written adapters toward one protocol adapter plus thin per-host shims for the primitives the
protocol does not cover (notably non-busy WAIT on daemon-less hosts, the landscape's biggest adapter
gap).

The split to respect: MCP is tools, A2A/ACP is agents. SPAWN_WORKER/DISPATCH and inter-agent
WAIT/ASK/REPLY are agent-shaped (lean ACP/A2A); PLACE/CLEANUP/INSPECT and capability skills are
tool-shaped (lean MCP, as container-use already does). A clean protocol adapter may use BOTH: MCP for
placement/inspection, ACP for the worker lifecycle. Do not force one protocol to carry both halves.

Alternatives:
- Keep per-host adapters (status quo): five hand-maintained skills, each drifting independently.
  Works today, but every new host is a new full adapter.
- One MCP-server adapter only: subsumes placement/inspection/tools cleanly (container-use is the
  proof), but leaves the agent-lifecycle WAIT/ASK/REPLY per-host. Partial win.
- One ACP adapter only: subsumes the agent lifecycle, but placement/tools still need MCP. Partial
  win the other way.

Revisit when: a second host ships native ACP/A2A support (today the field is early, so this is a
"when the ecosystem catches up" trigger, not "do it now"); or maintaining the five per-host adapters
in lockstep starts costing more than a protocol adapter plus shims would; or the WAIT-on-daemon-less
gap gets a native host answer (Claude Code Agent View / Agent Teams, landscape next-move 1), which
removes the main reason a protocol adapter still needs a per-host shim.

## How these three compose

Decision 1 is adopt-now (container-use is a maintained drop-in with a clear fallback ladder).
Decisions 2 and 3 are evaluate-and-spike: each names the minimum proof and the revisit trigger, so we
commit only after the seam holds against the existing composition tests, not on the landscape's
say-so. All three push the same way: keep building the method layer that is genuinely ours, stop
hand-rolling the mechanism the field has already solved.
