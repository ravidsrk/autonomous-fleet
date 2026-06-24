<!-- title: Security Policy | description: Threat model, what autonomous-fleet defends against, what it does not, and how to report a vulnerability. | sidebar_order: 99 -->

# Security Policy

**On this page:** [Supported versions](#supported-versions) · [Threat model](#threat-model) · [What we defend against](#what-we-defend-against) · [What we do not defend against](#what-we-do-not-defend-against) · [Reporting a vulnerability](#reporting-a-vulnerability) · [Track record](#track-record)

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
                 terraform|tofu|kubectl|helm|databricks apply|deploy|destroy|delete
  ASK  (exit 3)  ordinary git push, gh release, rm -rf of a scoped path
  ALLOW          reads, tests, edits, local git (commit, merge, worktree)
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

## What we do not defend against

> `run-sandboxed.sh` is best-effort. It is NOT an OS sandbox. It does not confine filesystem, network,
> or syscall reach.

Concretely, the framework does not protect you from:

- A malicious or careless `--yolo` operator. If you auto-approve tool calls against an untrusted repo,
  every defense above is something you chose to wave through. The classifier is a static heuristic over
  tokens, not a security boundary: a command constructed at shell runtime (command substitution,
  `eval` of a built string, base64 payloads) can evade it.
- A compromised upstream agent CLI. The fleet drives Claude Code, Codex, Grok, and Orca. If one of
  those binaries is backdoored, it runs with your privileges and the wrapper cannot see inside it.
- Supply-chain attacks on `npm` packages (the skills install path, your repo's own dependencies).
  Nothing here vets package integrity.
- Model-honored trust boundaries. A sufficiently persuasive prompt-injection payload inside repo
  content could still cause a worker to misbehave between sandbox checks.

For genuinely untrusted targets, run the fleet under `run-sandboxed.sh` AND inside a container, VM, or
restricted user account, with no production credentials in the ambient environment.

## Reporting a vulnerability

Email the maintainer privately: ravidsrk@gmail.com. Do not open a public GitHub issue for a security
report. Include a reproduction, the impact, and the affected commit. Expect an acknowledgement, and a
fix or a coordinated timeline within a 90-day disclosure window.

## Track record

No disclosed vulnerabilities yet. Resolved reports will be listed here with the reporter's credit
(opt-in) and the fixing commit.

---

[Guide Index](README.md)
