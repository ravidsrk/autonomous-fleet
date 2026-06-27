---
title: "Safety and secrets"
description: "The threat model, the sandbox wrapper, --yolo, container-use placement, and secret hygiene rules for running autonomous-fleet on a repo you care about."
sidebar:
  order: 12
---

# Safety and secrets

**On this page:** [Threat model](#threat-model) · [The sandbox wrapper](#the-sandbox-wrapper) ·
[--yolo mode](#yolo-mode) · [container-use placement](#container-use-placement) ·
[Secret hygiene](#secret-hygiene) · [Headless mode caveat](#headless-mode-caveat) ·
[Reporting a vulnerability](#reporting-a-vulnerability)

You are about to point an autonomous fleet of agents at a git repository, hand them
auto-approval on shell commands, and walk away. That is the whole pitch, and it is also exactly
the moment to be honest about what protects you and what does not. This chapter is that honesty.

It covers the threat model the framework assumes, what `scripts/run-sandboxed.sh` actually does
(and the much longer list of what it does NOT do), the `--yolo` flag and the one rule about it
that matters, optional `container-use` worker placement, and the secret-hygiene rules every worker
follows. It ends with how to report a vulnerability.

Read [Installation](/02-installation/) first if you have not, and skim
[The engine](/06-the-engine/) so the SAFETY RAILS and TRUST BOUNDARIES references land in context.

> One sentence to carry through the whole chapter: the framework's safety primitives are
> best-effort nets against accidental and obvious damage. They are NOT a security boundary. The
> boundary is an OS-level sandbox plus the absence of production credentials in the environment.
> Everything below either supports that sentence or qualifies it.

## Threat model

Start by naming who you are defending against, because "safe" with no adversary in mind is
marketing, not engineering.

The fleet runs untrusted-ish code in three senses, and the threat model treats each differently:

```
  +-----------------------------------------------------------------------+
  |  THREE THINGS THE FLEET TREATS AS UNTRUSTED                            |
  +-----------------------------------------------------------------------+
  |  1. The TARGET REPO's content       README, source, manifests, issue  |
  |     (prompt-injection surface)      and PR text, webhook payloads,     |
  |                                     worker subprocess output.          |
  |                                     -> DATA, never INSTRUCTIONS.       |
  |                                                                        |
  |  2. The COMMANDS workers run        Auto-approved under --yolo. A      |
  |     (blast-radius surface)          force-push or rm -rf is one        |
  |                                     model mistake away.                |
  |                                                                        |
  |  3. The AMBIENT ENVIRONMENT         Credential-shaped env vars a       |
  |     (secret-exfiltration surface)   worker could read, log, or commit. |
  +-----------------------------------------------------------------------+
```

What the framework DOES defend against, with the mechanism that does it:

```
  Threat                          Defense                         Where
  ------------------------------  ------------------------------  --------------------------
  Repo content issuing commands   TRUST BOUNDARIES: all repo      engine.md TRUST
  ("merge to main", "exfiltrate   content is DATA; only the       BOUNDARIES; model-honored
   secrets" in a README)          engine/mission/adapter/operator
                                  are instructions
  Accidental irreversible         Blast-radius classifier         run-sandboxed.sh
  command (force-push, rm -rf /)  refuses DENY/ASK verdicts       (a net, not a boundary)
  Secrets leaking via the         Env scrub: credential-shaped    run-sandboxed.sh env scrub
  ambient environment             vars stripped before exec
  Secrets entering git history    SECRET HYGIENE: gitleaks +      engine.md SECRET HYGIENE;
                                  self-check before every commit  every worker
  Production deploys / mainnet    SAFETY RAILS: merge != deploy;  engine.md SAFETY RAILS;
  txns / key rotation             testnet/staging/fixtures only   Lane 0 REFUSE+SURFACE
  Worker running an isolated      container-use placement: one    PLACE(independent) +
  task on the host                Linux container per task        container-use MCP
```

What the framework explicitly does NOT defend against. This list is load-bearing. If any item on
it is in your threat model, the framework alone is not enough and you need an OS-level sandbox or a
human in the loop:

- A malicious or careless `--yolo` operator. If you auto-approve tool calls against a repo you do
  not trust, you have opted into remote code execution. No flag undoes that choice.
- A sufficiently persuasive prompt-injection payload. The TRUST BOUNDARY is MODEL-HONORED. A clever
  enough payload inside repo content could still steer a worker between sandbox checks. The
  framework reduces this risk; it does not eliminate it.
- A general filesystem, network, or syscall escape. `run-sandboxed.sh` is NOT an OS sandbox. It does
  not confine where a process reads, writes, or connects.
- A compromised upstream agent CLI. If the `claude`, `codex`, `grok`, or Orca binary you installed
  is backdoored, every defense here runs inside the blast radius.
- Supply-chain attacks on the npm packages the skills install. Pin and audit your dependencies; the
  framework does not vet them for you.
- A command constructed at shell runtime. The classifier reads command text statically. A command
  built via `$(...)`, `eval` of an assembled string, base64-decoded payloads, or positional-arg
  injection cannot be resolved from its text. Where such a construct is detectable the classifier
  fails safe to ASK; where it is not, a determined caller can evade it.

> The honest summary: the framework is a net for accidental and obvious damage and a discipline
> against secret leakage and prompt injection. For a genuinely untrusted target, run it inside a
> container, VM, or restricted user account, with no production credentials anywhere in the ambient
> environment. That OS-level isolation, not any script in this repo, is the security boundary.

## The sandbox wrapper

`scripts/run-sandboxed.sh` is a best-effort safety wrapper for headless fleet runs against repos you
do not fully trust. It does two things before it execs your command, and it is loud about being
"best-effort", not a sandbox.

Run any command through it:

```bash
./scripts/run-sandboxed.sh ./scripts/run-mission-headless.sh grok doc-sync --yolo
```

Or just inspect the verdict without running anything:

```bash
./scripts/run-sandboxed.sh --classify rm -rf /etc      # prints DENY, exits 0
./scripts/run-sandboxed.sh --classify git push          # prints ASK,  exits 0
./scripts/run-sandboxed.sh --classify pytest             # prints ALLOW, exits 0
```

And see the scrubbed environment it would hand a command:

```bash
./scripts/run-sandboxed.sh env       # prints only the kept vars, no tokens
```

### What it caps: the blast-radius classifier

Before exec, the wrapper classifies the whole command line by blast radius and refuses the command
when the verdict is DENY or ASK. The classifier is ported from omnigent's `nessie` `blast_radius`
policy. The verdict is the most severe across every statement on the line (chained with `;`, `&&`,
`||`, `|`, `&`), so one dangerous statement condemns the whole line.

```
  +---------+-----------+----------------------------------------------------------+
  | VERDICT | EXIT CODE | MEANING                                                  |
  +---------+-----------+----------------------------------------------------------+
  | DENY    |     2     | Irreversible. Refused, never run.                        |
  |         |           |   force-push (--force / -f / +refspec / --mirror)        |
  |         |           |   remote-branch delete (--delete / --prune / -d / :ref)  |
  |         |           |   rm -rf of / ~ $HOME or a system dir                    |
  |         |           |   git reset --hard origin/* (remote-tracking ref)        |
  |         |           |   gh pr merge / gh repo delete                           |
  |         |           |   terraform|tofu|kubectl|helm|databricks                 |
  |         |           |     apply|deploy|destroy|delete                          |
  +---------+-----------+----------------------------------------------------------+
  | ASK     |     3     | Outward / destructive-but-recoverable. Refused.          |
  |         |           |   ordinary git push                                      |
  |         |           |   gh release                                             |
  |         |           |   rm -rf of a scoped path                                |
  +---------+-----------+----------------------------------------------------------+
  | ALLOW   |     0     | Reads, tests, edits, local git (commit/merge/worktree).  |
  |         |  (execs)  | Env is scrubbed, then the command runs.                  |
  +---------+-----------+----------------------------------------------------------+
```

Note the ASK tier. This wrapper is non-interactive, so an ASK has no human to prompt. It refuses too
(exit 3). The contract is: review the command, then re-run it by hand outside the wrapper if it is
intended. Refusing a rare safe command is acceptable; silently running an irreversible one is not.

The classifier handles a long list of evasions so the obvious tricks do not slip a dangerous command
past it: a leading `sudo` (including its value-taking options and a `--` terminator), shell env
assignments (`CI=1 git push --force`), command chaining, `git -C <dir>` global options, combined and
split `rm` flags (`-rf`, `-r -f`, `--recursive --force`), `+`/`:` push refspecs, and transparent
command wrappers (`command`, `env`, `xargs`, `nice`, `timeout`, `flock`, and friends) that would
otherwise hide the real binary. A `bash -c "<string>"` is re-classified recursively, and a `-c`
script whose behavior depends on caller-supplied positional args (`$@`, `$1`, ...) fails safe to ASK
because its real effect cannot be read from the string alone.

It FAILS SAFE: on an ambiguous wrapper construction it errs toward DENY or ASK rather than ALLOW.

### What it scrubs: the env allowlist

The wrapper does not pass your environment through. It builds an allowlist of variables to KEEP,
then execs via `env -i` with only those. Kept:

```
  PATH  HOME  USER  LOGNAME  SHELL  LANG  TERM  TMPDIR  PWD  LC_*
```

Everything else is dropped, which already excludes credential-shaped names. As defense in depth, the
preserved list is then filtered a second time to explicitly drop anything matching:

```
  GH_TOKEN  GITHUB_TOKEN  XAI_API_KEY  OPENAI_API_KEY  ANTHROPIC_API_KEY
  AWS_*  *_TOKEN  *_KEY  *_SECRET  *_PASSWORD
```

So even if one of those somehow rode in on the allowlist, it is stripped before exec. The net
effect: the wrapped command runs with locale, a working directory, and a PATH, and with no API
keys, no cloud credentials, and no git-host tokens in its environment.

> The right mental model is `env -i` with a tiny allowlist plus a refuse-list of dangerous command
> shapes. It is a seatbelt, not a roll cage. The blast-radius classifier is a STATIC heuristic over
> tokens, not a security boundary. Pair it with real OS-level isolation for untrusted targets. The
> sandbox-internals live in the source comments of `scripts/run-sandboxed.sh`; this chapter
> deliberately summarizes rather than duplicates them.

## --yolo mode

`--yolo` auto-approves every agent tool call. Inside this clone, on a repo you own, that is how you
get an unattended run. Against a repo you do not trust, it is a full remote-code-execution surface,
because an auto-approved worker steered by prompt-injected repo content can run anything its CLI can
run.

What `--yolo` does and does not change:

```
  WITHOUT --yolo                          WITH --yolo
  --------------------------------------  --------------------------------------
  Each tool call may prompt for approval  Every tool call is auto-approved
  A human is in the loop per action       No human is in the loop
  SAFETY RAILS still apply                SAFETY RAILS still apply
  SECRET HYGIENE still applies            SECRET HYGIENE still applies
  TRUST BOUNDARIES still apply            TRUST BOUNDARIES still apply
```

`--yolo` removes the per-action human gate. It does NOT disable the engine's SAFETY RAILS, SECRET
HYGIENE, or TRUST BOUNDARIES. Those are model-honored disciplines, not approval prompts, so they
hold regardless of the flag. What you lose is the last human checkpoint before an action runs.

The framework refuses to let you point `--yolo` at an external repo without acknowledging the risk.
`scripts/run-campaign.sh` guards this directly: if `--yolo` is set and `--repo` is outside the
autonomous-fleet clone, the run refuses to start unless you also pass
`--yolo-untrusted-acknowledged` (or wrap it in the sandbox):

```bash
# Refused: --yolo against an external --repo auto-approves every tool call (a full RCE surface).
./scripts/run-campaign.sh grok --preset repo-health --repo /tmp/someones-repo --yolo

# Accepted, two supported paths:
#   (a) wrap it in the sandbox wrapper, or
./scripts/run-sandboxed.sh ./scripts/run-campaign.sh grok --preset repo-health \
  --repo /tmp/someones-repo --yolo
#   (b) explicitly accept the RCE risk:
./scripts/run-campaign.sh grok --preset repo-health --repo /tmp/someones-repo \
  --yolo --yolo-untrusted-acknowledged
```

The exact refusal, verbatim from the script:

```
error: --yolo against an external --repo auto-approves every tool call, a full RCE surface.
       Run under scripts/run-sandboxed.sh, or pass --yolo-untrusted-acknowledged to accept the risk.
```

When `--yolo` IS set, the script also prints a standing warning to stderr on every run, so the
choice is never invisible in the logs:

```
warning: --yolo auto-approves all agent tool calls; untrusted --repo/--campaign + yolo = full RCE surface
```

> WHEN TO USE `--yolo`: an unattended run on a repo YOU OWN, ideally inside an OS-level sandbox.
> WHEN TO NEVER USE IT: against a repo, a campaign YAML, or a target you do not fully trust, unless
> the whole thing is wrapped in `run-sandboxed.sh` AND running inside a container, VM, or restricted
> user account with no production credentials in the environment. The acknowledgement flag is not
> permission from the framework; it is you taking responsibility for the RCE surface.

## container-use placement

`--yolo` plus `run-sandboxed.sh` closes the command and credential gaps but not the isolation gap:
without it, a worker still runs on your host filesystem. `container-use` closes that gap by running
each independent worker inside its own Linux container.

It is the optional sandboxed variant of `PLACE(independent)`, the engine's placement for self-
contained parallel work. When the `container-use` MCP is configured (each adapter supplies its own
`<tool> mcp add container-use -- container-use stdio` registration command; Docker is required),
`PLACE(independent)` may use a `container-use` ENVIRONMENT instead of a host `git worktree`. That
closes two gaps at once:

```
  +--------------------------+----------------------------------------------------+
  | GAP                      | WHAT container-use DOES ABOUT IT                   |
  +--------------------------+----------------------------------------------------+
  | OS-sandbox gap           | The worker runs in an isolated Linux container,    |
  |                          | not on the host. One environment per task unit.    |
  +--------------------------+----------------------------------------------------+
  | Isolation gap            | Each environment is its own git branch             |
  |                          | (container-use/<env>), so parallel workers do not  |
  |                          | fight over the host working tree.                  |
  +--------------------------+----------------------------------------------------+
```

The loop is identical across adapters: a worker does ALL file and shell work through the environment
(`environment_create` yields an env id and a `container-use/<env>` branch, then
`environment_file_write` / `environment_run_cmd`), never touching `.git` directly. Inspection is
non-destructive (`container-use list` / `log <env>` / `diff <env>`).

One sharp edge worth repeating from the engine spec. The preferred ship path keeps the review gate:

```bash
# PREFERRED ship path: keeps the SHA-pin + conflict-aware review gate.
container-use checkout <env>          # local branch from container-use/<env>
git push
gh pr create --base BASE
```

```bash
# AVOID as a default: this BYPASSES the PR/review gate.
container-use merge <env>             # merges into the CURRENT branch, no --base
```

`container-use merge <env>` merges into whatever branch you are on, with no `--base`, and skips the
PR and review gate entirely. Use it only after an explicit `git checkout BASE`, never as the default
ship path. Cleanup is `container-use delete <env>` (or `--all` at run end) instead of
`git worktree remove`.

If the `container-use` MCP is not configured, `PLACE(independent)` falls back to a plain
`git worktree`, which gives host-level isolation only and no OS sandbox. For an untrusted target,
the container path is the one you want. Adoption details live in `docs/adopt-container-use.md`.

> `container-use` is the closest the framework gets to an actual OS sandbox per worker, and it is
> the recommended placement when you run `--yolo` against anything you would not run on your laptop
> unsupervised. It is still not a guarantee against a container escape, but it raises the bar from
> "best-effort net" to "isolated process per task".

## Secret hygiene

The secret-hygiene rules are unconditional. They hold regardless of mission, adapter, or the
`--yolo` flag, because they are model-honored disciplines, not approval prompts. They come straight
from the SECRET HYGIENE block in `engine.md`, and every worker follows them.

The two rules, verbatim in intent:

1. SCAN BEFORE EVERY COMMIT. If the repo has a gitleaks config or a secret-scan test, the worker
   runs `gitleaks protect --staged` before every commit or push, and `gitleaks detect` pre-push.
   ANY hit blocks the commit: the worker reports an escalation, it never force-commits past a hit.
   If there is no gitleaks config, the worker still NEVER commits secrets and self-checks the diff
   for keys, tokens, and `.env` content before pushing.

2. NEVER WRITE A SECRET ANYWHERE PUBLIC. No worker commits, pushes, logs, or writes into any PR,
   commit, comment, or doc any of:

```
  API / broker keys          encryption keys           auth secrets
  private / wallet keys       .env* file contents       OAuth tokens
  customer data               real wallet addresses     live infra endpoints
```

Config reads secrets from the environment, never inline. Ledger and readiness docs reference work by
ID and PUBLIC `file:line` only, never by quoting the secret.

This composes with two adjacent disciplines worth knowing:

- TRUST BOUNDARIES + the trace stream. The trace `details` object is free-form but MUST NOT carry
  secrets or host-absolute paths; sensitive evidence is referenced by `evidence_hash` instead. This
  is no longer a prose-only request: it is enforced by `emit_trace.validate_event` plus `emit()`
  before any trace event is written. See the [Trace schema](/16-trace-schema/) reference for the
  redaction contract.

- ROTATE-BEFORE-SCRUB. Any git-history purge, history rewrite, secret-scrub, or leaked-secret
  removal task is hard-gated on a file-tracked `ROTATION_CONFIRMED=yes` boolean that a human sets.
  If that flag is absent, the fleet records the required rotation as a human action and does NOT
  scrub history yet. Scrubbing before rotation gives false safety, because an already-committed
  secret is already compromised. Rotate the credential first, then scrub.

And the env scrub from the sandbox wrapper is the belt-and-suspenders backstop: even if a worker
ignored every rule above, a secret that never entered the process environment cannot be exfiltrated
from it. That is why the supported pattern for an untrusted run is `run-sandboxed.sh` (which scrubs
the environment) plus an OS sandbox (which confines the rest).

> A note on a spec wrinkle, because honest docs surface these. The TRUST BOUNDARIES prose in
> `engine.md` describes `run-sandboxed.sh` as refusing a named deny-list of publish commands
> (`npm publish`, `cargo publish`, `aws`, `gcloud`, `git push --tags`, ...). The actual wrapper on
> `main` today refuses by the DENY/ASK/ALLOW blast-radius classifier documented above, which is a
> broader and structurally different mechanism. The classifier is the source of truth for what is
> refused; treat the engine.md prose as the older, narrower description of the same intent. The
> defense you get is the classifier, not the literal list.

## Headless mode caveat

This is a current limitation, stated plainly because hiding it would be worse than not documenting
it at all.

The campaign scripts (`scripts/run-campaign.sh`) drive each runtime's CLI in headless mode. That
requires the CLI to be authenticated on the host, and the headless path is NOT yet fully validated
end-to-end. The supported flow today is the interactive path: invoke a mission in a chat session, or
drive a runtime goal with `/goal`. Treat headless campaign mode as in-progress, not as a guaranteed
unattended pipeline.

```
  +--------------------------------------+----------------------------------------+
  | PATH                                 | STATUS TODAY                           |
  +--------------------------------------+----------------------------------------+
  | Interactive chat / /goal             | Supported. This is the path to use.    |
  +--------------------------------------+----------------------------------------+
  | Headless campaign (run-campaign.sh)  | Not yet fully validated end-to-end.    |
  |                                      | Requires the runtime CLI authenticated |
  |                                      | on the host.                           |
  +--------------------------------------+----------------------------------------+
```

The safety reason this lands in the safety chapter: headless mode is precisely where `--yolo` and an
external `--repo` combine into the RCE surface above. The RCE guard in `run-campaign.sh` exists for
exactly this path. Until headless mode is validated end-to-end, prefer the interactive path for
anything beyond a repo you fully own, and wrap any headless `--yolo` run in `run-sandboxed.sh`.

## Reporting a vulnerability

If you find a security issue in autonomous-fleet, please report it privately rather than opening a
public issue, so it can be fixed before it is broadly known.

The live destination is the repository root `SECURITY.md`, which carries the supported-versions
table, the threat model, and the private reporting channel. Follow that policy: email
ravidsrk@gmail.com privately, do not open a public GitHub issue, and use the documented 90-day
disclosure window.

When you report, include the exact command line or repo content that triggers the issue, the runtime
and adapter you used, whether `--yolo` was set, and the verdict `run-sandboxed.sh --classify`
returns for the offending command if it is command-shaped. A classifier evasion (a dangerous command
the classifier rates ALLOW) is a valid and useful report, because the classifier is a heuristic and
closing gaps in it is ongoing work.
## Real-world use cases

### Example — sandboxed classify pass

Doc-sync progress lists `scripts/run-sandboxed.sh --classify` on worker git/gh commands — safety
classifier discipline exercised on a real run.

### Invocation — headless without secrets on disk

`validate-headless.sh` never writes API keys; dry-run paths preview commands only.

### Worked example — reviewer sandbox

Wave 2 shipped `scripts/run-sandboxed.sh --role reviewer` — read-only reviewer isolation tested in
`tests/test_reviewer_sandbox.py`.

---

← [Previous: Strict mode](/11-strict-mode/) ·
[Guide Index](/) ·
[Next: Extending →](/13-extending/)
