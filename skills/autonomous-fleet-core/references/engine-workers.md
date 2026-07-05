# Engine workers and placement

Load when spawning, placing, dispatching, researching for, or resuming workers, or mapping adapter primitives.

<!-- moved from engine.md by the instruction-budget split; preserve doctrine semantics. -->

## THE PRIMITIVES (the adapter must implement each; this core only ever calls these)
1. `SPAWN_WORKER(role, placement)` → a worker handle, in the chosen placement, in auto/max mode.
2. `DISPATCH(task, handle)` → hand a task spec to a worker so it will report completion.
3. `WAIT(types, timeout)` → block for completion/escalation/question events (non-busy).
4. `INSPECT()` → read current task/worker/message state WITHOUT consuming it (non-destructive).
5. `PLACE(kind)` → produce a placement: `independent` (isolated checkout/branch for a parallel
   PR) or `dependent` (same checkout/branch, fresh worker session).
6. `WORKER_DONE(...)` / `ASK(...)` / `REPLY(...)` → the worker→coordinator completion, blocking
   question, and the coordinator's answer.
7. `OPEN_PR` / `MERGE_PR(conflict-aware)` / `CLEANUP(worktree)` → ship primitives.
8. `SYNC_TASK_STATE(task, status)` → keep the tool's native task view aligned with the ledger.
9. `SET_GOAL(condition)` → bind the host's native goal/loop API to mission or campaign DONE
   (paraphrase ledger + readiness gates). Record under `## Runtime goal` in the ledger. See
   `references/runtime-goals.md`.
10. `UPDATE_GOAL(message)` → progress ping; does not complete the goal.
11. `GOAL_COMPLETE(summary)` → end native goal mode ONLY after the same checks as TERMINATE below.
12. `GOAL_BLOCKED(reason)` → pause goal; maps to `fleet-outcome.status: blocked`.
13. `LOOP_POLL(interval, condition)` → goal/loop polling primitive. Host-native scheduler (e.g. Grok
    `/loop` or `scheduler_create`, Claude `/loop`, Codex automations, or external cron) that re-
    evaluates a condition on a bounded cadence. Used by `runtime-goals.md` and adapters for the
    "check ledger every N minutes until DONE" pattern. Optional; adapters without a scheduler fall
    back to a foreground `check --wait` loop.
Primitives 9–13 are optional when the host has no goal/loop API (Orca: ledger + `check --wait`
loop is sufficient). The adapter documents the exact command for each. If the adapter offers a
primitive in multiple syntaxes across tool versions, it says "try X, fall back to Y." This core
never hard-codes a tool command — it calls the primitive by name and lets the adapter resolve it.

14. `CONTINUE_WORKER(role, placement, session_handle)` → re-attach an EXISTING resumable agent
    session for an in-flight task instead of spawning fresh. Adapters whose runtime exposes a
    restore command (`grok --resume <SESSION_ID>`, `codex exec resume [SESSION_ID]`,
    `claude --resume <session-id>` — live-verified, issue #91) implement it; adapters
    without one ALIAS it to `SPAWN_WORKER` (the documented idempotent-relaunch fallback).
    OPTIONAL, like 9–13. Constrained to `live`-classified rows only (per `<SUBSTRATE>/recovery_scan.py`): never
    re-attach a session whose PR merged or whose branch is gone. Resume budget is bounded by a
    coordinator-maintained `RESUME_COUNT` on the task row (incremented on every CONTINUE_WORKER) and
    audited by `recovery_scan`: when a row's `RESUME_COUNT` reaches `MAX_RESUME_ATTEMPTS` (3), the
    scanner recommends `ESCALATE_TO_DECISIONS` instead of another continue. The bound is only as
    reliable as the increment — the coordinator MUST bump `RESUME_COUNT` (or call the increment
    helper) on each re-attach, or the audited limit never trips.

TRACKER vs SCM bindings: primitive 7's ship verbs are the SCM binding (`OPEN_PR` against BASE,
conflict-aware `MERGE_PR`, `CLEANUP`); the issue-facing verbs (read issue, derive branch name, mark
issue done) are the TRACKER binding. `gh`/GitHub is the DEFAULT binding for both, NOT the contract:
the contract is "open a PR against BASE and conflict-aware merge it", satisfiable by `gh`, `glab`,
or a Linear-tracker + GitHub-SCM pairing. An adapter declares its TRACKER and SCM bindings
independently. This abstraction does NOT relax the conflict-aware, never-squash, or SHA-PIN rules —
those bind whatever SCM is used.

═══════════════════════════════════════════════════════════
WORKER PLACEMENT — the DECISION LOGIC (tool-agnostic). The adapter maps it to real commands.
═══════════════════════════════════════════════════════════
"Fresh worker" ≠ new isolated checkout. Decide placement by dependency on uncommitted state:
- INDEPENDENT work (self-contained; doesn't need another in-flight task's uncommitted state) →
  PLACE(independent): an isolated checkout/worktree on its own branch off BASE, for a parallel PR.
- DEPENDENT work (needs the current branch's uncommitted state, must validate/PR the current
  branch, or is a review-fix cycle on an open PR) → PLACE(dependent): the SAME checkout, a FRESH
  worker session.
- Always wait for the worker to be ready before DISPATCH (the adapter defines "ready"). Keep
  dependency chains ≤3–4 deep. Retire each isolated checkout the moment its PR merges; no
  speculative/duplicate workers. Log placement + concurrency per task.

CONTAINER-USE-PLACEMENT — the optional sandboxed variant of PLACE(independent) (tool-agnostic; each
adapter supplies its own `<tool> mcp add container-use -- container-use stdio` registration command,
needs Docker). When the container-use MCP is configured, PLACE(independent) MAY use a container-use
ENVIRONMENT instead of a host `git worktree`, closing the OS-sandbox gap (the worker runs in an
isolated Linux container, not the host) and the isolation gap (each environment is its own git
branch) in one move. The loop is identical across adapters:
- SPAWN_WORKER(independent): give the worker the container-use MCP tools and instruct it to do ALL
  file/shell work through the environment (`environment_create` → env id + branch
  `container-use/<env>`, then `environment_file_write` / `environment_run_cmd`). One env per task
  unit; never touch `.git` directly.
- INSPECT(): `container-use list` / `log <env>` / `diff <env>` (non-destructive).
- OPEN_PR / SHIP (preferred): `container-use checkout <env>` (local branch from
  `container-use/<env>`), push, `gh pr create --base BASE` — keeps the SHA-pin + conflict-aware
  review gate. NOTE: `container-use merge <env>` merges into the CURRENT branch (no `--base`) and
  BYPASSES the PR/review gate, so use it only after an explicit `git checkout BASE`, never as the
  default ship path.
- CLEANUP: `container-use delete <env>` (or `--all` at run end) instead of `git worktree remove`.
- FALLBACK: no container-use MCP → the plain `git worktree` PLACE(independent) above (host-level
  isolation, no sandbox). Adoption details: docs/adopt-container-use.md.
- COUPLING-AWARE PARTITIONING (run at decomposition, UPSTREAM of the hot-file rule below):
  before splitting work, build a static import/symbol graph of the touched files. Then: (a) CLUSTER
  tightly-coupled files (a file and the symbols it imports/defines that the change spans) into ONE
  task rather than slicing a coupled unit across parallel PRs that then fight at merge; (b) mark
  high-in-degree HUB / utility files (imported by many — base classes, shared types, core config) as
  SERIALIZE-ALWAYS singletons: at most one in-flight task may touch a hub, upstream of and stricter
  than the per-file hot rule. This is the same conflict-minimizing intuition the hot-file rule
  encodes, applied at the GRAPH level before tasks exist. Empirically: partitioning by
  module-coupling (not just file-touch overlap) reduces review-time conflicts and reviewer-
  rejections on the FOUNDATION cluster. Optional tooling: `scripts/coupling-graph.py` (framework clone only) emits the
  import/symbol graph + hub list; absent it, derive coupling by inspection. A mission over loosely
  coupled files (the common case) clusters trivially and proceeds.
- PARALLELISM: parallelize ACROSS non-overlapping files/modules; SERIALIZE work that touches the
  same file (one in-flight task per hot file — the next change to that file starts only after the
  prior PR merges). This both enables parallelism and minimizes merge conflicts.

═══════════════════════════════════════════════════════════
WORKER SKILLS — capability skills for workers only (not the coordinator).
═══════════════════════════════════════════════════════════
If the active mission declares `## Worker skills`, the coordinator MUST inject the listed skills
into each DISPATCH / task spec for matching pipeline roles (@claude builder, @grok builder, etc.):
- Prepend a **Worker skills** block: "Activate and follow these installed skills before doing this
  task: `<skill-a>`, `<skill-b>`."
- Workers are full agents — they load those skills in their own session; the coordinator does NOT
  load domain skills into its orchestration loop.
- If a listed skill is not installed, use that row's "If unavailable" fallback from the mission.
- Optional skills (coordinator-only) and worker skills are disjoint — see composition.md.

HANDLE RESOLUTION — a mission's `@<vendor>` handle denotes a ROLE, not a hard vendor requirement.
On a multi-vendor host, prefer the named vendor (it is what makes the cross-vendor build-blind
review a mechanical guarantee — see the REVIEW step). On a SINGLE-VENDOR host, map every handle to a
fresh same-vendor subagent for that role (a `@grok reviewer` on a Claude-only host becomes a fresh
Claude subagent acting as reviewer). Record the substitution in DECISIONS.md. The role's discipline
(fresh context, write isolation) is what binds; the vendor name is the preferred, not the required,
binding — exactly as `gh` is the DEFAULT, not the contract, for the SCM binding above.

═══════════════════════════════════════════════════════════
RESEARCH DISCIPLINE — verify external facts on demand; never code from stale memory.
═══════════════════════════════════════════════════════════
Research is NOT a phase you do once and ignore for the rest of the mission — it is a TRIGGER that
fires as-and-when required, throughout. Training data is stale for current library/API behavior,
versions, advisories, and anything external, so a worker that codes from memory ships wrong
assumptions. Both coordinator (at gates) and workers (mid-task) apply this; the worker preamble
below ships on EVERY DISPATCH, not only when a mission lists worker skills.

- TRIGGER (when research is REQUIRED): before committing to any external fact you cannot verify
  from THIS repo — a library/framework's current API or version behavior, a config/flag's present
  semantics, a CVE/advisory, a payment/auth/provider surface, a design or competitive pattern,
  anything dated after your training cutoff. When unsure whether a fact is stale-prone, treat it
  as yes. Do not guess and ship: verify, then act.
- THE LOOP (host-conditional tooling; issue #86 removed the hard-coded binding): resolve the
  research tool ONCE at SELF-ORIENTATION, record it in DECISIONS.md, and use it for every trigger:
  1. `docs/agents/fleet-config.md` `RESEARCH_TOOLS`, if recorded by setup.
  2. Tools actually present on the host, probed not assumed — e.g. `monid` on PATH
     (`monid discover` → `inspect` → `run`), a Context7/library-docs MCP for pure
     current-library-docs lookups, a `deep-research`-class skill for corroborating
     high-stakes findings.
  3. Fallback ALWAYS available: the host's native web search/fetch. No fleet host lacks one;
     "the good tool isn't installed" never excuses skipping verification.
  A worker must NEVER invoke a research tool it has not confirmed exists — a failed
  `monid` call retried in a loop, or a fabricated "verified" line, is worse than the fallback.
  Never skip verification entirely.
- SPIKE (when reading is not enough): for a load-bearing unknown, build ONE throwaway proof to
  validate the approach before the freeze, record findings in `docs/research-notes.md`, then discard
  it. A spike validates behavior; it is not documentation lookup and is not kept as build output.
- THE LEDGER (append, never freeze): each trigger writes one line to `docs/research-notes.md` —
  `<unknown> | <source: url or provider/endpoint> | <finding> | verified|unverified`. It grows
  through the WHOLE mission, so a later task reuses an earlier finding instead of re-searching and
  the reviewer sees every external fact the build leaned on.
- THE GATE (verify at the END, do not pre-gate): T-FINAL records in the readiness `fleet-outcome`
  `unverified_assumptions: 0` (every external decision the build made has a logged source) and
  `sources_logged: <n>`. A reviewer FAILS a PR that codes against an unverified external fact. The
  campaign never blocks waiting on upfront research; it blocks only if the mission shipped an
  unsourced external assumption (a campaign edge may branch on `unverified_assumptions == 0`).

Worker preamble (append to every DISPATCH, alongside OPERATING BEHAVIORS):
```
RESEARCH: before coding against any external fact you can't confirm from this repo (library/API
behavior, versions, CVEs, provider surfaces, competitive/design patterns), verify it first with
the research tool named in this dispatch (from DECISIONS.md; fallback: this host's native web
search). Use only tools you have confirmed exist. Log each check to docs/research-notes.md
(unknown | source | finding | verified). Ship no unverified external assumption; the reviewer
fails PRs that do.
```

═══════════════════════════════════════════════════════════
MODEL & COST ROUTING — match the model tier to the role; track spend; gate on a budget.
═══════════════════════════════════════════════════════════
TRIGGER: the host supports per-call model/effort selection, or a mission sets BUDGET.
CORE RULES: route by ROLE tier (STRONG: coordinator/reviewer/freeze; MID: builders; CHEAP: mechanical triage), record tiers in DECISIONS.md; cost_estimate is a declared estimate, never silently exceed a stated BUDGET.
FULL DOCTRINE (read when the trigger applies): `references/cost-routing.md`.
