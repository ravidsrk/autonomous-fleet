<!-- title: Security Policy | description: Threat model, what autonomous-fleet defends against, what it does not, and how to report a vulnerability. | sidebar_order: 99 -->

# Security Policy

**On this page:** [Supported versions](#supported-versions) · [Threat model](#threat-model) · [What we defend against](#what-we-defend-against) · [What we do not defend against](#what-we-do-not-defend-against) · [Privacy and data flow](#privacy-and-data-flow) · [Reporting a vulnerability](#reporting-a-vulnerability) · [Track record](#track-record)

`autonomous-fleet` spawns autonomous agents that read your repo, write code, and open PRs. That is a
real attack surface. This page is honest about where the boundaries are.

## Supported versions

There are no tagged releases yet. Security fixes land on `main`, and `main` is the only supported
version. Pin to a commit if you need stability, then re-pin forward when a fix you need merges.

## Threat model

The campaign driver takes operator-supplied inputs and turns them into agent actions against a repo.
From the `scripts/run-campaign.sh` header:

> `--repo` and `--campaign` are operator-supplied paths. Campaign YAML can name arbitrary missions
> and repos. With `--yolo`, agents auto-approve all tool calls against that repo: treat untrusted
> inputs as a full RCE surface; keep yolo off unless you trust both.

So the two things you control are: which repo the fleet runs against, and whether `--yolo` is on.
A trusted repo with `--yolo` off is the safe default. An untrusted repo with `--yolo` on is full
remote code execution, by design. `run-campaign.sh` enforces this: `--yolo` against an external
`--repo` exits non-zero unless you pass `--yolo-untrusted-acknowledged` or run under the sandbox.

## What we defend against

Two mechanical layers, plus an optional container boundary.

```
  operator command
        |
        v
  +--------------------------+   scrubs credential-shaped env vars,
  |  run-sandboxed.sh        |   classifies the command by blast radius,
  |  (best-effort wrapper)   |   REFUSES (exit non-zero) on DENY or ASK
  +--------------------------+
        |
        v
  +--------------------------+   one isolated Linux container per worker
  |  container-use (opt-in)  |   (PLACE(independent)), each its own git branch
  +--------------------------+
        |
        v
  the target repo
```

Env scrubbing. `scripts/run-sandboxed.sh` execs the wrapped command via `env -i` with an allowlist.
It keeps `PATH HOME USER LOGNAME SHELL LANG TERM TMPDIR PWD` plus `LC_*`, and strips credential-shaped
names: `AWS_*`, `*_TOKEN`, `*_KEY`, `*_SECRET`, `*_PASSWORD`, plus `GH_TOKEN`, `GITHUB_TOKEN`,
`XAI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`.

Blast-radius classifier. The same wrapper classifies the command line and refuses irreversible or
outward-facing actions before exec:

```
  DENY (exit 2)  force-push, remote-branch delete, rm -rf of a critical/system path,
                 git reset --hard to a remote ref, gh pr merge, gh repo delete,
                 shred, dd of=/dev/*, chmod|chown|chgrp -R of an absolute system path,
                 find <abs-system-path> with -delete / -exec / -ok
  ASK  (exit 3)  ordinary git push, gh release, rm -rf of a scoped path,
                 terraform|tofu|kubectl|helm|databricks apply|deploy|destroy|delete,
                 npm|pnpm|yarn|cargo publish, aws|gcloud destructive verbs,
                 curl|wget piped into a shell
  ALLOW          everything else (reads, tests, edits, local git, and — by default —
                 any command the wrapper does not specifically inspect; see below)
```

The wrapper is non-interactive, so an ASK has no human to prompt: it refuses too, and you re-run the
command by hand once you have eyeballed it. The classifier fails safe: on an ambiguous construction it
errs toward DENY or ASK rather than ALLOW. Inspect a verdict without running anything:

```bash
./scripts/run-sandboxed.sh --classify rm -rf /etc    # prints DENY
./scripts/run-sandboxed.sh --classify git push       # prints ASK
```

Container isolation. When the `container-use` MCP is configured, `PLACE(independent)` can run each
worker inside its own Linux container on its own git branch, instead of a host `git worktree`. That
closes the OS-sandbox gap the wrapper cannot: the worker's filesystem and process reach are confined
to the container.

Kill switches. Each verification-substrate gate exposes a `FLEET_DISABLE_*` env var that, when set
truthy, makes that gate's CLI early-exit. This is an operator escape hatch and the bench's
substrate-off comparator — but every disabled gate is a defense you turned off, so audit them before
a run against an untrusted target. The registry has grown past the original four substrate layers
(`FLEET_DISABLE_VERIFY_FINDINGS`, `FLEET_DISABLE_STOP_VERIFY`, `FLEET_DISABLE_BLIND_FIX`,
`FLEET_DISABLE_RUN_ARCHIVE`); the live set now also includes `FLEET_DISABLE_SHA_PIN`,
`FLEET_DISABLE_ROUND_BUDGET`, `FLEET_DISABLE_REGISTRY_LINT`, `FLEET_DISABLE_REVIEWER_SANDBOX`, and
`FLEET_DISABLE_NAMESPACING`. The canonical registry and per-knob semantics live in
`skills/autonomous-fleet-core/references/substrate-disable-knobs.md`. The security-critical gates —
the SHA-pin and reviewer-sandbox attribution checks — are being moved to fail closed (a missing or
unreadable manifest fails the gate) rather than fail open, so a malformed run archive cannot silently
pass them.

## What we do not defend against

> `run-sandboxed.sh` is best-effort. It is NOT an OS sandbox. It does not confine filesystem, network,
> or syscall reach.

Concretely, the framework does not protect you from:

- A malicious or careless `--yolo` operator. If you auto-approve tool calls against an untrusted repo,
  every defense above is something you chose to wave through.
- Most destructive commands. The classifier is not an allowlist of safe commands — it is a small
  best-effort blocklist of the most common destructive ones, and **everything it does not specifically
  recognize is ALLOW by default**. Today the wrapper inspects `rm`, `git push`/`git reset`, `gh`,
  infra tools (`terraform`/`tofu`/`kubectl`/`helm`/`databricks`), plus the catastrophic / outward
  heads covered by the DENY/ASK matrix above (`shred`, `dd` to a device, recursive
  `chmod`/`chown`/`chgrp` on a system path, `find` with `-delete`/`-exec` on a system path,
  package `publish`, `aws`/`gcloud` destructive verbs, and `curl`/`wget` piped into a shell). Those
  plainly-written forms classify DENY or ASK (and are refused) — they are **not** residual ALLOW
  examples. What still slips through is everything outside that inspected set, plus constructions
  the static token heuristic cannot see: runtime command substitution (`$(...)` / backticks),
  `eval` of a built string, base64-decoded payloads, and unknown or renamed binaries the wrapper
  does not specifically inspect — those still classify as ALLOW today. The shape does not change:
  it is a best-effort blocklist of common destructive commands, **NOT** a security boundary. Rely
  on OS-level sandboxing — `container-use`, a VM, or a restricted account — for the boundary.
- A compromised upstream agent CLI. The fleet drives Claude Code, Codex, Grok, and Orca. If one of
  those binaries is backdoored, it runs with your privileges and the wrapper cannot see inside it.
- Supply-chain attacks on `npm` packages (the skills install path, your repo's own dependencies).
  Nothing here vets package integrity.
- Model-honored trust boundaries. A sufficiently persuasive prompt-injection payload inside repo
  content could still cause a worker to misbehave between sandbox checks.

For genuinely untrusted targets, run the fleet under `run-sandboxed.sh` AND inside a container, VM, or
restricted user account, with no production credentials in the ambient environment.

## Privacy and data flow

Running a mission is not a local-only operation. A worker reads your repo and feeds that content to a
third-party model to do its work, so be deliberate about what you point it at.

- **Repo content leaves your machine.** File contents, diffs, and anything else the worker reads —
  including any secrets that live in tracked files (`.env` checked into git, hard-coded keys,
  credentials in fixtures) — are transmitted to whichever model provider your chosen agent uses:
  Anthropic for Claude Code, OpenAI for Codex, or xAI for Grok. Scrub secrets out of the repo before
  a run; env scrubbing in `run-sandboxed.sh` only covers the process environment, not file contents.
- **Banner generation uses OpenRouter.** The exploratory-banner helper
  (`scripts/banner/generate_exploratory_banner.sh`) sends its prompt and source image to OpenRouter
  (via `OPENROUTER_API_KEY`) when generation is enabled. It is opt-in and unrelated to mission work.
- **No first-party telemetry.** `autonomous-fleet` does not phone home. It adds no analytics,
  telemetry, or data-collection endpoint of its own; it talks only to GitHub (via `gh`) and to the
  model/banner providers above. Your data goes wherever those providers' terms say it goes — that is
  between you and them, governed by their data-retention policies:
  - Anthropic — <https://www.anthropic.com/legal/privacy>
  - OpenAI — <https://openai.com/policies/privacy-policy>
  - xAI — <https://x.ai/legal/privacy-policy>
  - OpenRouter — <https://openrouter.ai/privacy>

## Reporting a vulnerability

Email the maintainer privately: ravidsrk@gmail.com. Do not open a public GitHub issue for a security
report. Include a reproduction, the impact, and the affected commit. Expect an acknowledgement, and a
fix or a coordinated timeline within a 90-day disclosure window.

## Track record

No disclosed vulnerabilities yet. Resolved reports will be listed here with the reporter's credit
(opt-in) and the fixing commit.

---

[Guide Index](README.md)
