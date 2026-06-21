# Adopt container-use for sandbox + isolation

How autonomous-fleet should adopt `dagger/container-use` as the default placement/sandbox
substrate. container-use is an open-source MCP server (powered by Dagger) that hands each agent its
own containerized environment backed by its own git branch, tool-agnostic across any MCP host, with
git-checkout-to-review. It closes two of our open gaps in one drop-in: the OS-sandbox gap (today only
a `run-sandboxed.sh` deny-list) and the worktree-per-task isolation the adapters hand-roll.

This is an adapter-layer change, not a core change. The engine keeps calling PRIMITIVES by name; the
adapter resolves `PLACE`/`SPAWN_WORKER`/`CLEANUP` to container-use environments instead of raw
`git worktree`. The core never learns the word "container".

## What container-use gives us

- One environment per agent: a fresh container plus a dedicated git branch, created on first tool
  call. Multiple agents run in parallel without touching each other's filesystem or working tree.
- Tool-agnostic: the same `container-use stdio` MCP server serves Claude Code, Cursor, Codex, Goose,
  VSCode/Copilot, Amazon Q, any MCP client. One mechanism, every adapter.
- git-checkout-to-review: an agent's work lands as commits on its branch. Review is `git checkout
  <env-branch>` or `cu checkout <env>`; merge is `cu merge <env>` (or `cu apply <env>` to bring the
  diff into the current branch). Discard is `cu delete <env>`, which throws away both the branch and
  the container with no residue.
- Full command history + logs per environment (`cu log <env>`, `cu watch`), and `cu terminal <env>`
  to drop into a live agent's shell for intervention.

The CLI surface we lean on: `cu list`, `cu checkout`, `cu merge`, `cu apply`, `cu diff`, `cu log`,
`cu watch`, `cu terminal`, `cu delete`. Requires Docker/Dagger on the host.

## Mapping engine primitives onto a container-use environment

The engine's placement model (`WORKER PLACEMENT` block in engine.md) splits work by dependency on
uncommitted state: `independent` gets an isolated checkout/branch for a parallel PR; `dependent`
reuses the same checkout in a fresh worker session. container-use maps cleanly:

```
PLACE(independent)  -> a NEW container-use environment off BASE: own container, own branch
                       (<BRANCH_PREFIX><slug>), own filesystem. The agent's first MCP tool call in
                       this env creates it. This is the parallel-PR placement.
PLACE(dependent)    -> REUSE the in-flight task's environment (same container, same branch), a fresh
                       worker session against it. Review-fix rounds and validate-this-branch work
                       stay in the same env so they see the uncommitted state.
SPAWN_WORKER(role,  -> launch the host agent pointed at its MCP server; the agent transacts through
  placement)           container-use tools, so its work is confined to the placement's environment.
                       REPO_ROOT is the seed the environment is built from; the agent never writes
                       the host tree directly.
WORKER_DONE         -> the agent's commits are on the env branch. The completion contract is
                       unchanged: write ledger flags + files + summary; the diff is reviewable via
                       cu checkout / git checkout of the env branch.
OPEN_PR / MERGE_PR  -> review the env branch (FRESH, build-blind reviewer reads the diff). On pass,
                       cu merge <env> into BASE (or push the env branch and gh pr merge --merge,
                       commits preserved, NEVER squash). Conflict handling is the engine's existing
                       conflict-aware SHIP step against the env branch.
CLEANUP(worktree)   -> cu delete <env>: branch AND container gone in one call. Replaces
                       `git worktree remove`. No orphan worktree, no leaked container. Retire the
                       env the moment its PR merges, exactly as the engine already requires.
```

The "one in-flight unit per hot file" rule is unchanged: an environment is the unit of isolation, so
two environments editing the same file still serialize at merge time per the engine's PARALLELISM
rule. container-use does not relax the hot-file serialize-always discipline; it just makes the
isolation real (separate container, not a shared host filesystem).

INSPECT maps to `cu list` + `cu log <env>` (non-destructive, reads env/branch/status without
consuming anything), composed with the file ledger as today.

## How each adapter wires it

Each adapter already documents how its host spawns a worker. Adopting container-use means: register
the MCP server once per host, then point `PLACE`/`CLEANUP` at environments instead of worktrees. The
register step, verbatim per host:

```
Claude Code:  claude mcp add container-use -- container-use stdio
Cursor:       MCP entry { "command": "container-use", "args": ["stdio"] }
Codex:        ~/.codex/config.toml:
                [mcp_servers.container-use]
                command = "container-use"
                args = ["stdio"]
Goose:        ~/.config/goose/config.yaml extensions:
                container-use: { type: stdio, cmd: container-use, args: [stdio], enabled: true }
VSCode/Copilot: .vscode/mcp.json servers.container-use: { type: stdio, command: container-use,
                args: ["stdio"] }
Amazon Q:     mcpServers.container-use: { command: container-use, args: ["stdio"], timeout: 60000 }
```

Adapter-by-adapter:

- `autonomous-fleet-adapter-claude-code`: today PLACE(independent) is `git worktree add ... -b
  <prefix><slug> BASE` and CLEANUP is `git worktree remove`. With container-use registered as above,
  PLACE(independent) becomes "the subagent/sub-session transacts in a new container-use environment
  off BASE"; CLEANUP becomes `cu delete <env>`. The file ledger stays the source of truth (Claude
  Code has no external task daemon); environments add real OS isolation the worktree path lacks.
- `autonomous-fleet-adapter-codex` / `-grok`: same shape. These hosts read `config.toml`-style MCP
  config; register `container-use` once, then resolve PLACE/CLEANUP to `cu` commands. The grok
  headless-auth caveat (GEM-001 in DECISIONS.md) is orthogonal: container-use isolates whatever the
  worker session is, however it was launched.
- `autonomous-fleet-adapter-orca`: Orca already manages worktrees/workspaces natively. container-use
  is the alternative placement backend for hosts WITHOUT Orca's worktree management, or when an Orca
  run targets an untrusted repo and wants a hard container boundary. Document it as opt-in here; do
  not rip out Orca-native worktrees where they already isolate.
- `autonomous-fleet-adapter-template`: add a "container-use placement" section to the template so new
  adapters get the wiring for free: register the MCP server, resolve PLACE(independent) -> new env,
  PLACE(dependent) -> reuse env, CLEANUP -> `cu delete`, INSPECT -> `cu list`/`cu log`, review ->
  `cu checkout`/`cu diff`, ship -> `cu merge`.

`setup-autonomous-fleet` records the chosen placement backend (container-use vs host-native
worktrees vs OS-sandbox fallback) in `docs/agents/fleet-config.md` alongside `BRANCH_PREFIX`, so the
coordinator reads it at self-orientation.

## Why this also closes the OS-sandbox gap

The engine's TRUST BOUNDARIES and RESIDUAL RISK blocks say it plainly: `run-sandboxed.sh` is a
deny-list that scrubs known-prefix secrets and refuses a small known-bad command set; it does NOT
confine filesystem or network reach. The engine then says untrusted repos SHOULD additionally run
inside an OS-level sandbox (container / VM / restricted user). container-use IS that OS-level sandbox.
Adopting it for placement means every worker already runs in a container with no host filesystem
access and no ambient production credentials, so the two open items collapse into one move:

- Worktree-per-task isolation: satisfied (separate container + branch per environment).
- OS sandbox: satisfied (container boundary, not a shared host tree).

`run-sandboxed.sh` stays as the in-container command guard (deny-list + secret scrub), and the
omnigent `blast_radius` port (force-push / `rm -rf /` / publish-command classifier) runs as the
PreToolUse guard INSIDE the environment. Defense in depth: the container is the wall; `blast_radius`
is the guard at the door. Neither replaces the other.

## Fallback for hosts without MCP (or without Docker)

container-use needs an MCP-capable host and Docker/Dagger. Where either is missing, degrade in this
order, recording the chosen tier in `fleet-config.md`:

1. omnigent OS sandbox (same-host, no daemon): shell `run-sandboxed.sh` out to omnigent's real
   sandbox backends instead of running bare. macOS: `omnigent/inner/seatbelt_sandbox.py`
   (`sandbox-exec -f <profile>`, narrowed `/dev` access, no `iokit-open`/`mach-priv-host-port`).
   Linux: `omnigent/inner/bwrap_sandbox.py` (hermetic mount namespace, read-only `/usr`, `$HOME`
   never mounted, fresh `/proc` `/dev` `/tmp`, seccomp on top). These give a real filesystem/network
   boundary on a single host with no container runtime, and they share one `SandboxPolicy` shape, so
   the adapter sets read/write roots from REPO_ROOT and the worktree once.
2. Remote microVM sandbox (clean machine per worker): e2b or daytona (or modal). Use when the host
   can't sandbox locally but can reach a sandbox API: provision a fresh microVM per worker, seed it
   from REPO_ROOT, run the worker there, pull commits back to BASE. Heavier and network-dependent;
   reserve for genuinely untrusted targets or hosted/headless fleets.
3. Bare `run-sandboxed.sh` only (status quo): deny-list + secret scrub, no OS confinement. Acceptable
   ONLY for trusted, self-owned repos with no production credentials in the environment, which is the
   common dogfood case. The engine's RESIDUAL RISK note already says this is best-effort; keep that
   honesty in the readiness doc.

Decision rule for the adapter: MCP host + Docker present -> container-use (tier 0, the default).
No Docker but same-host sandbox tools present -> omnigent seatbelt/bwrap (tier 1). Neither, but a
sandbox API reachable -> e2b/daytona (tier 2). Trusted self-owned repo only -> bare run-sandboxed.sh
(tier 3). Record the tier and why in DECISIONS.md, same as every other placement choice.
