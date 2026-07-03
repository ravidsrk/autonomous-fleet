<!-- title: The substrate | description: The 4-layer verification substrate that catches bad work before it ships. | sidebar_order: 7 -->

# The substrate (4-layer verification)

**On this page:** [Why a substrate](#why-a-substrate) · [The four layers at a glance](#the-four-layers-at-a-glance) · [Layer 1: findings schema](#layer-1--findings-schema) · [Layer 2: stop-verify hook](#layer-2--stop-verify-hook) · [Layer 3: blind-fix mechanical guard](#layer-3--blind-fix-mechanical-guard) · [Layer 4: mutation gate](#layer-4--mutation-gate) · [How the layers compose](#how-the-layers-compose) · [Kill switches](#kill-switches) · [The standing validator suite](#the-standing-validator-suite) · [Why mutation testing beats coverage](#why-mutation-testing-beats-coverage) · [What is not yet enforced](#what-is-not-yet-enforced)

The [engine](06-the-engine.md) decides what work to do and routes it to workers. The substrate is the
other half: it decides whether the work that comes back is real. This chapter is about how the
framework catches bad work, and why it catches it with running code instead of a prompt that says
"please be careful."

## Why a substrate

Most agent frameworks verify with a system prompt. They tell the reviewer "only report real bugs,"
they tell the builder "make sure your tests pass," and then they hope. Hope is not a control. An
over-eager reviewer hallucinates a finding that quotes a line that isn't in the file. A builder
declares "done" with no test run on disk. A reviewer reads the candidate patch first and then writes
a blind-fix that is not blind. None of those failures trip a prompt. They all trip code.

The substrate is four independent layers of code, each one a different shape of check:

```
  reviewer / builder output
            │
            ▼
  ┌───────────────────────────────────────────────────────────┐
  │ Layer 1  findings schema       is the claim grounded?      │  schema + grep
  │ Layer 2  stop-verify hook       is there fresh evidence?   │  filesystem + mtime
  │ Layer 3  blind-fix guard        was the fix written blind? │  mtime ordering + content
  │ Layer 4  mutation gate          do the tests above bite?   │  fault injection
  └───────────────────────────────────────────────────────────┘
            │
            ▼
       ships, or blocks
```

Each layer catches a class of failure the others cannot:

- Layer 1 catches a reviewer who invented a finding. It greps the cited file for the quoted line.
- Layer 2 catches a worker who declared done without doing the work. It scans the disk for fresh
  evidence inside a freshness window.
- Layer 3 catches a reviewer who peeked at the candidate patch before writing their independent
  diagnosis. It checks that the blind-fix file was written before the findings doc.
- Layer 4 catches a regression in layers 1 through 3 themselves. It injects a representative bug into
  the verifier code and asserts the test suite notices.

The first three are runtime gates: they fire while a mission runs (Layer 2's gate is shipped for Claude Code only today — other hosts run Loose; see chapter 11). The fourth is a build-time gate:
it fires in CI and makes the other three falsifiable. A verifier with no mutation pinning is a
verifier you cannot trust, because nothing proves it would catch the bug it claims to catch.

> The substrate is build-blindness made executable. The [Roles and blindness](08-roles-and-blindness.md)
> chapter explains why a fresh-terminal reviewer is structurally blind. This chapter is about the code
> that proves the reviewer stayed blind and that the builder produced evidence, rather than trusting
> either to self-report.

## The four layers at a glance

```
  ┌─────────┬───────────────────────────┬──────────────────────────────┬────────────────────────────┐
  │ Layer   │ What it checks            │ Where it lives               │ Kill switch (env var)      │
  ├─────────┼───────────────────────────┼──────────────────────────────┼────────────────────────────┤
  │ 1       │ Findings are grounded:    │ scripts/verify_findings.py   │ FLEET_DISABLE_VERIFY_      │
  │         │ every claim quotes a real │ scripts/lib/verify_          │ FINDINGS                   │
  │         │ line in the cited file    │ findings.py                  │                            │
  ├─────────┼───────────────────────────┼──────────────────────────────┼────────────────────────────┤
  │ 2       │ A session can't end       │ scripts/stop_verify.py       │ FLEET_DISABLE_STOP_VERIFY  │
  │         │ without fresh on-disk     │ scripts/lib/stop_verify.py   │                            │
  │         │ evidence                  │                              │                            │
  ├─────────┼───────────────────────────┼──────────────────────────────┼────────────────────────────┤
  │ 3       │ The blind-fix was written │ scripts/verify_blind_fix.py  │ FLEET_DISABLE_BLIND_FIX    │
  │         │ before the findings doc   │ scripts/lib/verify_          │                            │
  │         │ (mtime ordering)          │ blind_fix.py                 │                            │
  ├─────────┼───────────────────────────┼──────────────────────────────┼────────────────────────────┤
  │ 4       │ Layers 1-3 and every      │ tests/mutations.yaml         │ (CI gate; no per-run       │
  │         │ other mechanism actually  │ scripts/mutation_check.py    │  disable knob)             │
  │         │ fail when broken          │                              │                            │
  └─────────┴───────────────────────────┴──────────────────────────────┴────────────────────────────┘
```

Two things to notice in that table before we go deeper:

1. Each runtime layer has exactly one kill switch, and they all share one truthy rule. There are no
   aliases. We cover them in [Kill switches](#kill-switches) below.
2. Layer 4 has no per-run disable knob. You do not get to turn off the gate that proves the other
   gates work. That asymmetry is deliberate.

## Layer 1: findings schema

Layer 1 is the answer to reviewer hallucination. When a review mission like
`adversarial-review-and-fix` produces findings, every finding must cite a verbatim line from the
source file. The verifier greps the cited file for that line. A finding whose quote cannot be located
is marked unverified and is never allowed to drive a fix.

The schema authority is `skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json`. A
findings document is a JSON object with this top-level shape:

```json
{
  "schema_version": "1.0",
  "mission": "adversarial-review-and-fix",
  "review_id": "feat-locks-1-skeptic",
  "round": 1,
  "findings": [ ... ],
  "verdict": {
    "decision": "request_changes",
    "reasoning": "One blocking bug in the lock-steal liveness check; see F-001."
  }
}
```

The five required top-level fields are `schema_version`, `mission`, `review_id`, `findings`, and
`verdict`. `schema_version` is pinned to the constant `"1.0"`. `review_id` must match
`^[a-zA-Z0-9._/-]+$` so it is safe to use in archive paths. The optional `reviewer` block records the
reviewer's vendor, model, and role (`build-blind-reviewer`, `skeptic`, `integrator-review`, or
`other`) so the run-archive can audit cross-vendor diversity.

Each finding is the part that makes the layer bite:

```json
{
  "id": "F-001",
  "severity": "high",
  "category": "bug",
  "claim": "The lock-steal path treats a live holder as dead and steals the lock.",
  "evidence": {
    "file_path": "scripts/lib/locks.py",
    "line_number": 142,
    "quoted_line": "if isinstance(holder_pid, int) and _pid_alive(holder_pid):"
  },
  "fix_alternatives": [
    {
      "label": "A",
      "description": "Re-check liveness after acquiring the steal lock.",
      "effort": "minimal",
      "recommended": true
    },
    {
      "label": "B",
      "description": "Drop steal entirely; require manual unlock.",
      "effort": "moderate"
    }
  ],
  "confidence": 90,
  "fix_strategy": "ask"
}
```

The required finding fields are `id`, `severity`, `category`, `claim`, `evidence`,
`fix_alternatives`, `confidence`, and `fix_strategy`. The constraints that matter most:

```
  ┌──────────────────┬──────────────────────────────────────────────────────────────────────┐
  │ Field            │ Constraint                                                             │
  ├──────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ id               │ ^[A-Z]+-[0-9]+$ (e.g. F-001); unique within the doc                    │
  │ severity         │ critical | high | medium | low                                         │
  │ category         │ bug | security | architecture | performance | style | test |           │
  │                  │ root_cause_depth | other                                               │
  │ evidence         │ object with required file_path + quoted_line; optional line_number      │
  │ quoted_line      │ EXACT verbatim line from the source, character-for-character            │
  │ fix_alternatives │ 1 to 4 labeled proposals; labels ^[A-Z]$; at most one recommended=true  │
  │ confidence       │ integer 0-100 (a bool is rejected even though bool subclasses int)      │
  │ fix_strategy     │ auto | ask                                                             │
  │ cascade_impact   │ REQUIRED and non-empty when category=root_cause_depth                   │
  └──────────────────┴──────────────────────────────────────────────────────────────────────┘
```

The `quoted_line` is the load-bearing field. It is the EXACT verbatim line from the source file,
character-for-character including whitespace. If a reviewer cannot quote the exact line, the schema
description tells them to omit the finding rather than invent one.

The `category=root_cause_depth` rule is worth calling out. A finding that claims to have found a root
cause must name the other call paths the root cause can trigger, in a `cascade_impact` field. A
`root_cause_depth` finding without `cascade_impact` is almost always a symptom-fix finding
miscategorised, and the schema rejects it the same way it rejects an unverified quote.

### Two passes, run in order

The verifier runs two passes, and both must pass for exit code 0. The CLI entrypoint is
`scripts/verify_findings.py`:

```bash
python3 scripts/verify_findings.py .fleet/runs/<run_id>/p0-review-findings.json \
  --repo . \
  --summary-out .fleet/runs/<run_id>/p0-verify-summary.json
```

Pass 1 is structural validation. It checks required fields, enum values, id uniqueness, and the
`schema_version` pin. It runs first and bails before touching the filesystem so a malformed doc
produces a clean schema error instead of misleading file-not-found noise. The library splits this
into `validate_findings_doc` (shape) and keeps it separate from source verification on purpose: a
malformed doc still produces a useful structural error before any grep happens.

Pass 2 is source verification. For each finding, the verifier resolves `evidence.file_path` against
`--repo` and runs a whitespace-tolerant grep for `evidence.quoted_line`. Whitespace-tolerant means
runs of whitespace in both the quote and the source are collapsed to a single space before the
substring comparison, so tab-versus-space and line-wrap differences do not cause a false miss while
the integrity of the check stays intact. A finding whose quote is found gets `verified: true`. A
finding whose quote is not found gets `verified: false` and a `verify_reason`.

The `verified` and `verify_reason` fields are set by the verifier, NOT by the reviewer. A reviewer
cannot mark their own finding verified. That is the whole point.

### Why a hostile findings doc cannot become a read-anything primitive

A findings document is reviewer-produced data, which means it is suspect data. A hallucinated or
malicious finding could cite an absolute path like `/etc/passwd` or a `../` traversal to read outside
the repo. The verifier constrains every cited path to the repo root:

```python
candidate = Path(file_path)
if not candidate.is_absolute():
    candidate = repo_root / candidate
try:
    target = candidate.resolve()
    target.relative_to(repo_root.resolve())
except (OSError, ValueError):
    finding["verified"] = False
    finding["verify_reason"] = "file_path escapes repo root"
    return finding
```

A path that escapes the repo is marked unverified, not read. The verifier also caps source reads at
`MAX_SOURCE_BYTES` (8 MB) so a finding that cites a multi-gigabyte file, or a symlink to one, cannot
OOM the verifier. Both behaviours are pinned by mutations (see Layer 4):
`verify-findings-path-containment-off` and `verify-findings-hallucination-gate-off`.

### What the summary feeds

The `--summary-out` JSON is the artifact downstream consumers read. It reconciles cleanly:
`total_findings = verified + unverified + skipped_non_dict`. It also separates `auto_applicable`
findings from `human_gated` ones. The key discipline lives here: a finding is counted
auto-applicable ONLY when it is verified AND `fix_strategy == "auto"` AND `confidence >= 80`. An
unverified finding never qualifies for auto-apply regardless of its declared `fix_strategy`. That is
what makes the schema enforce the discipline rather than merely describe it. The
`unverified_findings` count is surfaced in `fleet-outcome.metrics`, and an unverified finding is a
likely reviewer hallucination the operator must inspect before the fix loop consumes it.

## Layer 2: stop-verify hook

Layer 1 verifies what a reviewer claims. Layer 2 verifies that a builder actually did the work. It is
a Claude Code Stop hook: when a worker tries to end its session, the hook scans the disk for fresh
evidence and refuses to let the session terminate if none exists.

This is the runtime counterpart of the engine disciplines EVID, WT_CLEAN, and `e2e_verified`. Without
the hook those disciplines are aspirational, because the builder self-attests in the readiness doc.
The hook makes them enforceable by refusing to let a worker declare done unless verifiable evidence is
on disk inside a freshness window. Today it ships on the Claude Code adapter, which is where the Stop
hook contract exists.

### The decision contract

The library (`scripts/lib/stop_verify.py`) is side-effect free: it inspects the filesystem and returns
a `Verdict`. The CLI (`scripts/stop_verify.py`) translates the verdict into Claude Code's Stop-hook
JSON:

```
  Verdict.allow = True   -> exit 0, no JSON       (session may end)
  Verdict.allow = False  -> exit 0, JSON {decision: "block", reason: <text>}
                            (Claude Code refuses to terminate the session)
```

The CLI ALWAYS exits 0. Claude Code treats a non-zero exit as a hook error, not a block, so the gate
is encoded in the JSON `decision` field, not the exit code. The hook also never raises to the Claude
Code harness. Any internal error is rendered as ALLOW with a stderr warning, because a broken hook
that traps a worker mid-session is a worse failure than a missed gate.

### What counts as evidence

The hook runs five detectors, each mtime-windowed. An artifact only counts if it was modified inside
the freshness window:

```
  ┌─────────────────┬───────────────────────────────────────────────────────────────────────┐
  │ Detector        │ What it looks for                                                     │
  ├─────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ progress_flag   │ EVID=true / WT_CLEAN=true in a docs/*-progress.md ledger file          │
  │ readiness       │ e2e_verified: true OR status: done in a docs/*-readiness.md frontmatter│
  │ verify_summary  │ a Layer-1 verify-summary JSON with unverified_findings == 0            │
  │ test_artifact   │ pytest cache, coverage, junit XML, jest/vitest json, cargo-nextest     │
  │ e2e_artifact    │ Playwright/Puppeteer report or screenshot PNG                           │
  └─────────────────┴───────────────────────────────────────────────────────────────────────┘
```

The mtime window is what makes evidence fresh. The default window is 30 minutes, the longest gap
between "evidence ran" and "agent declares done" that real fleet runs produce in steady state.
Anything longer is a smell. The window is clamped: it cannot go below `MIN_WINDOW_SEC` (30 seconds, so
ordinary disk-cache churn cannot cause false BLOCKs) and cannot exceed `MAX_WINDOW_SEC` (24 hours, so
yesterday's artifact cannot "prove" today's run).

The flag detectors are deliberately strict about the literal text. `EVID` must appear as `EVID=true`,
not bare `EVID`, so that a paragraph of prose discussing EVID cannot satisfy the gate. The pattern is
case-insensitive but requires the `=true`:

```python
EVID_PATTERN = re.compile(r"\bEVID\s*=\s*true\b", re.IGNORECASE)
WT_CLEAN_PATTERN = re.compile(r"\bWT_CLEAN\s*=\s*true\b", re.IGNORECASE)
```

The `verify_summary` detector is the strongest grade of evidence because it ties Layer 2 back to
Layer 1. It does not just check that a summary file exists. It parses the JSON and confirms
`unverified_findings == 0`. A failing verify is NOT evidence that the run can stop. (Mutation
`stop-verify-unverified-gate-off` flips that `== 0` to `>= 0` and a test catches it.)

### The verdict logic

The orchestrator runs every detector, counts the distinct evidence kinds, and decides:

```
  for each detector -> list of EvidenceHit (kind, path, mtime_age, detail)
  distinct_kinds = number of kinds with at least one hit

  if require_progress_flag and (no evid_flag OR no wt_clean_flag):
      BLOCK   (strict-progress mode)
  elif distinct_kinds < min_evidence_kinds:
      BLOCK
  else:
      ALLOW
```

`min_evidence_kinds` defaults to 1: any one fresh artifact is enough, which matches the upstream
patterns this was composed from. Operators who want a paranoid mode can raise it to 2 or 3, or set
`require_progress_flag` so BOTH `EVID=true` AND `WT_CLEAN=true` must appear in a freshly modified
ledger file, on top of whatever other evidence is present.

When the gate blocks, the reason string is written to be actionable. A vague BLOCK message produces a
worker that retries the same broken approach, so the message explains in plain English what was
missing and tells the agent exactly what to do: run the fix's own EVID reproduction, run the test
suite end-to-end, write the readiness doc with `status: done`, or run `verify_findings.py
--summary-out`. The block message also tells a no-edit turn how to opt out:
`FLEET_DISABLE_STOP_VERIFY=1`.

### Running it by hand

You can invoke the hook directly to see what it sees:

```bash
python3 scripts/stop_verify.py --explain --repo .
```

`--explain` prints a human-readable verdict to stderr (stdout is reserved for the decision JSON so the
two never corrupt each other). Other flags: `--window-min N` sets the freshness window, `--min-kinds
N` sets the threshold, `--strict-progress` requires both ledger flags, and `--json-out` forces a
decision payload even on ALLOW so a harness can grep for one.

## Layer 3: blind-fix mechanical guard

Layer 3 is the subtlest of the three runtime gates. It defends the anti-anchoring protocol from
`skills/autonomous-fleet-core/references/blind-fix.md`. The protocol says: before a reviewer reads the
builder's candidate patch, the reviewer writes their own independent diagnosis of how they would fix
the problem. That independent diagnosis is the "blind-fix." If the reviewer reads the candidate first
and then writes the blind-fix, the blind-fix is anchored to the builder's approach and the whole point
is lost.

You cannot verify "the reviewer did not peek" with a prompt. You can verify it with timestamps. The
blind-fix file must have been written BEFORE the findings doc. The guard checks exactly that, plus a
set of content invariants that catch a stub masquerading as a real diagnosis.

The CLI entrypoint is `scripts/verify_blind_fix.py`:

```bash
python3 scripts/verify_blind_fix.py .fleet/runs/<run_id>/ \
  --summary-out .fleet/runs/<run_id>/blind-fix-summary.json
```

It defaults to reading `<run_dir>/p0-review-findings.json` and locates each finding's blind-fix file
at the canonical `<run_dir>/reviewer-blind-fix-<finding_id>.md`, or at a per-reviewer subdirectory, or
at an explicit `blind_fix_chain.path` declared in the finding (run-archive-relative only; absolute
paths and `..` escapes are rejected, the same hardening as Layer 1).

### The five invariants

For each finding, the guard checks five things:

```
  ┌───┬───────────────────────────────────────────────────────────────────────────────────┐
  │ # │ Invariant                                                                         │
  ├───┼───────────────────────────────────────────────────────────────────────────────────┤
  │ 1 │ A blind-fix file exists at a recognised location                                  │
  │ 2 │ The blind-fix mtime is BEFORE the findings doc mtime (the ordering check)         │
  │ 3 │ It contains a point-of-creation statement: file:[symbol]:line                      │
  │ 4 │ It contains a pre-commit confidence (an integer 0-100)                            │
  │ 5 │ It is not a stub: long enough, no TODO/N/A/see PR/TBD, no diff markers             │
  └───┴───────────────────────────────────────────────────────────────────────────────────┘
```

Invariant 2 is the heart of the layer. Invariant 5 is the supporting cast: a blind-fix that contains a
unified diff marker (`diff --git`, `--- a/`, `+++ b/`) has almost certainly been written AFTER the
reviewer opened the candidate patch, because that is where the diff came from. A blind-fix shorter than
80 characters of normalized content, or that matches a stub pattern, is treated as "the reviewer did
not really do the blind fix."

### Why the mtime comes from the manifest, not the filesystem

A naive ordering check would read the file's `st_mtime` off disk. That is forgeable: anyone can
`touch` a file to any timestamp. So when a `manifest.json` exists in the run directory, the guard
reads the recorded `mtime_utc` from the manifest instead of trusting the live filesystem mtime:

```python
manifest_path = run_dir / "manifest.json"
if not manifest_path.is_file():
    return None
# ... load manifest, build {rel_path -> mtime_utc} ...
```

The manifest is the integrity record produced by `write_manifest` at run sealing time, with a sha256
and recorded mtime per file. Reading ordering from the manifest means the ordering check is anchored to
the sealed archive, not to mutable disk state. The ordering rule itself is simple and pinned by a
mutation:

```python
if findings_mtime is not None and mtime is not None and mtime > findings_mtime:
    reasons.append(
        f"mtime({path.name})={mtime:.0f} > findings.mtime={findings_mtime:.0f} "
        "(blind-fix must precede findings)"
    )
```

When the blind-fix mtime is later than the findings mtime, the finding fails. Mutation
`blind-fix-mtime-ordering-off` replaces that whole condition with `False` and a test catches it.
Mutation `blind-fix-ignores-manifest-ordering` forces the manifest path to be ignored, and a test
catches that too.

The summary reports `findings`, `verified_blind_fix`, `unverified_blind_fix`, and per-finding reasons,
mirroring Layer 1's shape so the two summaries are easy to read side by side.

## Layer 4: mutation gate

Layers 1 through 3 are tests. Layer 4 tests the tests. It is the standing mutation gate, and its
manifest is `tests/mutations.yaml`. There are 50 mutations in the manifest today.

The idea is fault injection. Each entry describes a representative bug as a `find` string and a
`replace` string in a real source file, plus the `guards` (test files) that MUST catch it. The gate
applies the mutation, runs the guards, and asserts they FAIL. A mutation whose guards still pass
SURVIVED, which means the test is weak or tautological. Here is the shape:

```yaml
- id: verify-findings-hallucination-gate-off
  file: scripts/lib/verify_findings.py
  find: "quoted_norm and quoted_norm in source_norm"
  replace: "True"
  guards: [tests/test_verify_findings.py]
```

That mutation neuters Layer 1's whole reason for existing: it makes the quoted-line grep always
"match," so every finding would verify regardless of whether its quote is real. If
`tests/test_verify_findings.py` did not fail when that mutation is applied, the test would be proving
nothing. The gate guarantees it does.

The manifest header states the discipline directly: add an entry whenever you add a mechanism, so that
"if this breaks, a test notices." The substrate's own layers are heavily represented. These eleven
mutations pin the four-layer substrate specifically:

```
  ┌──────────────────────────────────────────┬──────────────────────────────────┬──────────┐
  │ Mutation id                              │ What breaking would mean         │ Layer    │
  ├──────────────────────────────────────────┼──────────────────────────────────┼──────────┤
  │ verify-findings-hallucination-gate-off   │ quoted-line grep always matches  │ 1        │
  │ verify-findings-path-containment-off     │ findings can read outside repo   │ 1        │
  │ stop-verify-unverified-gate-off          │ a failing verify counts as done  │ 2        │
  │ kill-switch-layer2-lib-disable-off       │ stop-verify ignores its kill knob│ 2        │
  │ blind-fix-mtime-ordering-off             │ ordering check is inert          │ 3        │
  │ blind-fix-ignores-manifest-ordering      │ ordering uses forgeable disk mtime│ 3        │
  │ blind-fix-stub-detector-off              │ a stub blind-fix passes          │ 3        │
  │ blind-fix-diff-marker-detector-off       │ an anchored blind-fix passes     │ 3        │
  │ blind-fix-path-containment-off           │ blind-fix path can escape run_dir│ 3        │
  │ run-archive-anti-anchoring-off           │ archive ordering gate is inert   │ 1/3 seam │
  │ trace-details-secret-scan-off            │ trace can leak a secret          │ engine   │
  └──────────────────────────────────────────┴──────────────────────────────────┴──────────┘
```

The manifest covers more than the substrate. The same gate pins the fleet-outcome validators, the
sandbox blast-radius classifier, the campaign DAG runner, the lock manager, trace emission, and even
prose rails (a structural test must reject a semantic inversion of `engine.md`, for example flipping
`FROZEN SCOPE BOUNDARY` to say scope may expand freely).

Two of those entries are worth knowing as worked examples of the review discipline. The lock manager
has two liveness mutations, `lock-steal-liveness-check-off` and `lock-steal-second-liveness-check-off`.
The second one exists because an adversarial review found that a single liveness check left a race
where a live holder could still have its lock stolen; the fix added a second post-acquire liveness
check, and the mutation pins it so the second check can never silently rot. Likewise the trace details
redaction rule is pinned by `trace-details-secret-scan-off`: the engine's `validate_event` and
`emit()` scrub secrets and host-absolute paths from trace `details`, and the mutation guarantees a
test fails if that scan is turned off. The framework found and closed both of these bugs in its own
review pipeline; the mutations are how it keeps them closed.

### Running the gate

```bash
python3 scripts/mutation_check.py
```

The gate iterates the manifest, applies each mutation to a working copy, runs that entry's guards, and
reports any SURVIVORS. A clean run means every injected bug was caught by at least one guard. This runs
in CI, which is what makes it a build-time gate rather than a runtime one.

## How the layers compose

The layers are independent in implementation but ordered in effect. They form a funnel, and a failure
caught early never reaches the layers downstream:

```
  reviewer emits findings
        │
        ▼
  ┌──────────────────────────────────────────────┐
  │ L1  findings schema + quoted-line grep         │
  │     unverified finding -> dropped from the     │
  │     fix loop, surfaced in fleet-outcome        │
  └──────────────────────────────────────────────┘
        │  (only verified findings continue)
        ▼
  ┌──────────────────────────────────────────────┐
  │ L3  blind-fix ordering + content guard         │
  │     was the diagnosis written before the       │
  │     candidate patch? mtime from the manifest   │
  └──────────────────────────────────────────────┘
        │
        ▼
  ┌──────────────────────────────────────────────┐
  │ L2  stop-verify: can the worker end its        │
  │     session? fresh evidence on disk, including │
  │     a clean L1 verify-summary as the strongest │
  │     grade of evidence                          │
  └──────────────────────────────────────────────┘
        │
        ▼  (across all of the above, in CI)
  ┌──────────────────────────────────────────────┐
  │ L4  mutation gate: does each of L1, L2, L3     │
  │     actually fail when its core check is       │
  │     neutered?                                  │
  └──────────────────────────────────────────────┘
```

The composition rules, stated plainly:

- A finding caught at L1 (unverified quote) never reaches the fix loop. It is dropped and surfaced in
  `fleet-outcome.metrics.unverified_findings`. It cannot be auto-applied no matter what its
  `fix_strategy` says.
- L3's ordering check reads the same run directory L1 verified into. A blind-fix that fails the
  ordering or content invariants fails the finding before integration.
- L2 only allows a session to end when fresh evidence exists, and a clean L1 verify-summary
  (`unverified_findings == 0`) is the highest grade of that evidence. So L2 and L1 reinforce each
  other: passing L1 is itself a way to pass L2.
- L4 sits across all three. It does not run at mission time; it runs in CI and asserts that the checks
  in L1, L2, and L3 still bite. If someone refactors `verify_findings.py` and accidentally makes the
  grep always match, L4 catches the regression before it ships, because the mutation that simulates
  exactly that bug would survive.

The net effect: each layer narrows the set of work that can ship. A bad finding dies at L1. An anchored
blind-fix dies at L3. A worker with no evidence cannot even end its turn at L2. And a regression in any
of those gates dies at L4 in CI.

## Kill switches

Every runtime layer exposes one kill switch, and the convention is documented in
`skills/autonomous-fleet-core/references/substrate-disable-knobs.md`. The registry:

```
  ┌──────────────────────────┬────────────────────────────────┬────────────────────────────────┐
  │ Layer                    │ Script                         │ Env var                        │
  ├──────────────────────────┼────────────────────────────────┼────────────────────────────────┤
  │ 1: review-findings       │ scripts/verify_findings.py     │ FLEET_DISABLE_VERIFY_FINDINGS  │
  │ 2: stop-verify           │ scripts/stop_verify.py         │ FLEET_DISABLE_STOP_VERIFY      │
  │ 3: blind-fix             │ scripts/verify_blind_fix.py    │ FLEET_DISABLE_BLIND_FIX        │
  │ 4: run-archive           │ scripts/validate_run_archive.py│ FLEET_DISABLE_RUN_ARCHIVE      │
  └──────────────────────────┴────────────────────────────────┴────────────────────────────────┘
```

There is exactly ONE env var per layer. No legacy aliases, no fallbacks. If you find a name like
`STOP_VERIFY_DISABLED` anywhere in the codebase, it is stale and should be deleted on sight. The
substrate has no installed-user base yet, so shipping a back-compat surface now would just lock in
technical debt.

> The run-archive validator (`scripts/validate_run_archive.py`, `FLEET_DISABLE_RUN_ARCHIVE`) is the
> fourth knob in the registry, and it is the runtime-side disable for archive integrity. It is distinct
> from the Layer 4 MUTATION gate, which has no per-run disable knob at all. The registry knob turns off
> archive validation for one run; nothing turns off the mutation gate. Do not conflate the two.

### Truthy semantics

The truthy rule is case-insensitive and intentionally a strict allow-list:

```
  truthy:  1   true   yes   on
  falsy:   0   false  no   off   ""   unset   anything-else
```

The strict allow-list is deliberate. The framework does NOT treat "anything non-empty" as truthy,
because that turns a typo into a silent disable, and a silent disable is the exact failure mode the
substrate exists to prevent: an operator who thinks they are running the substrate but quietly is not.
All four layers delegate to one helper, `scripts/lib/substrate_disable.py`, so the rule never drifts
between layers. Two mutations, `kill-switch-truthy-relaxed` and `kill-switch-truthy-strict`, pin the
allow-list from both directions.

### The disable contract

When the env var is truthy, the CLI must:

1. Exit code 0 (success, no-op).
2. Print exactly `<layer-label>: DISABLED via <ENV_VAR>=1 (no-op exit 0)` to stderr. The format is
   pinned by tests so dashboards can grep it.
3. Short-circuit BEFORE arg parsing, so invalid arguments do not produce a non-zero exit when the
   layer is disabled.

"Disabled" means "treat this layer's verdict as PASS for this run." It is an escape hatch for a known
false positive that is blocking ship, not a way to run the framework with verification quietly off. If
you want fail-closed behaviour, do not use the disable knob; fix the upstream problem.

### Why the kill switches exist at all

There are two reasons, and the second is the interesting one:

1. An operator escape hatch. When a layer flags a known false positive and blocks ship, the operator
   needs a single-run override without re-deploying the substrate.
2. A falsifiable comparator for the adversarial bench. The substrate-off versus substrate-on delta IS
   the value the substrate must defend. Without real kill switches the bench's "off mode" would be
   fiction. The bench driver `export`s the four env vars in off-mode and `unset`s them in on-mode, and
   a regression test asserts the driver actually exports and unsets them, because the original bug was
   a driver that built the env string and only echoed it, never exporting it.

## The standing validator suite

The four numbered layers are the spine of the substrate, and they stay exactly as described above. But
the substrate has grown more checkable gates around that spine. These are not new layers in the Layer
1-4 sense: they are additional standing one-shot validators, each a small pure library plus a thin CLI,
each with its own `FLEET_DISABLE_*` kill switch, and most of them wired into `scripts/validate-all.sh`
so they run on every validation pass. They follow the same discipline as the four layers: the library
is side-effect free and the CLI does the filesystem and git work, each kill switch routes through the
same `scripts/lib/substrate_disable.py` helper, and a truthy env var makes the CLI early-exit 0 with the
pinned `<label>: DISABLED via <ENV_VAR>=1 (no-op exit 0)` stderr notice.

Five of them are gates in `validate-all.sh`, one (the recovery scanner) is an advisory tool that runs at
resume rather than as a standing gate:

```
  ┌────────────────────┬────────────────────────────────────┬──────────────────────────────┬──────────┐
  │ Validator          │ What it checks                     │ Kill switch (env var)        │ in       │
  │                    │                                    │                              │validate- │
  │                    │                                    │                              │ all?     │
  ├────────────────────┼────────────────────────────────────┼──────────────────────────────┼──────────┤
  │ verify-sha-pin     │ a reviewer PASS is bound to the    │ FLEET_DISABLE_SHA_PIN        │ yes      │
  │                    │ SHA it graded; branch divergence   │                              │          │
  │                    │ flips REVIEWED to OUTDATED         │                              │          │
  │ verify-round-      │ a task over its review-round       │ FLEET_DISABLE_ROUND_BUDGET   │ yes      │
  │   budget           │ budget must end BLOCKED, not MERGED│                              │          │
  │ registry-lint      │ shipped dirs vs catalog vs         │ FLEET_DISABLE_REGISTRY_LINT  │ yes      │
  │                    │ skills-lock all agree              │                              │          │
  │ verify-reviewer-   │ a reviewer producer is never       │ FLEET_DISABLE_REVIEWER_      │ yes      │
  │   sandbox          │ attributed a diff/commit on the    │ SANDBOX                      │          │
  │                    │ candidate branch                   │                              │          │
  │ validate-          │ every isolated branch + worktree   │ FLEET_DISABLE_NAMESPACING    │ yes      │
  │   namespacing      │ carries the run -<run_short> suffix│                              │          │
  │ recovery-scan      │ classifies each task row live/dead/│ (advisory; no kill switch)   │ no       │
  │                    │ partial/orphan, ADVISORY only      │                              │ (resume) │
  └────────────────────┴────────────────────────────────────┴──────────────────────────────┴──────────┘
```

Each validator follows the substrate's "no archives, exit 0" rule: the discipline is gated on artifact
production, not on a directory existing. A repo with no `sha-pin.json`, no `trace.jsonl`, no
`manifest.json` passes each gate cleanly.

### SHA-pin enforcement

A reviewer PASS is not a blanket blessing of a branch. It is a blessing of one specific SHA. The
reviewer records the SHA it graded in `.fleet/runs/<run_id>/sha-pin.json`, whose shape is pinned by
`assets/fleet-sha-pin.schema.json`:

```json
{
  "schema_version": "1.0",
  "review_id": "feat-locks-1-skeptic",
  "reviewed_sha": "0e1f2a3b4c5d6e7f8091a2b3c4d5e6f7a8b9c0d1",
  "branch": "fleet/feat-locks-1-a1b2c3",
  "verdict": "approve"
}
```

The required fields are `schema_version` (pinned to `"1.0"`), `review_id`, `reviewed_sha` (a 40-hex git
SHA), `branch`, and `verdict`; an optional `merged` boolean is allowed and nothing else. The pure
verifier in `scripts/lib/verify_sha_pin.py` only enforces records whose verdict is `approve` or `PASS`
(a `request_changes` or `fail` record is recorded but not enforced). For each enforced record it asks a
caller-injected `head_resolver` for the branch's current HEAD. The CLI (`scripts/verify_sha_pin.py`)
resolves that HEAD with `git -C <repo> rev-parse <branch>`. When the reviewed SHA no longer equals the
branch HEAD, the verifier emits `... moved <reviewed>..<head>: REVIEWED is OUTDATED, force re-review`:
the PASS is stale and the work must be re-reviewed against the new tip.

The deleted-branch case is handled honestly. If the resolver returns `None` (the branch is unknown or
deleted), a record carrying a merged marker is N/A, not a failure: a branch that was reviewed and then
merged and deleted is the normal happy path, not a divergence. The CLI derives that merged marker either
from `merged: true` on the record itself or from a sibling readiness / `fleet-outcome` doc that says
`merged: true` or `status: done`. Without any merged marker, a HEAD-unknown enforced record is a fail,
because there is then no evidence the reviewed work actually shipped. The kill switch is
`FLEET_DISABLE_SHA_PIN`, and the gate is wired into `validate-all.sh`.

### Round-budget circuit breaker

Review is not infinite. A task that keeps failing review round after round is not converging, and at
some point the honest outcome is BLOCKED, not a merge that papered over the disagreement. The
round-budget validator (`scripts/lib/verify_round_budget.py`) reads the run's `trace.jsonl`, counts
`REVIEWER` events with `status == "failed"` per task, and applies one invariant: a task with more than
`MAX_ROUNDS` (3) failed review rounds must finish as `GOAL_BLOCKED`/`blocked` and must not have shipped
through a successful `MERGE`. A task that ran four failed rounds and then MERGED is a violation
(`... ran N review rounds then MERGED without BLOCKED`); so is one that ran four failed rounds and
reached no terminal BLOCKED at all. The kill switch is `FLEET_DISABLE_ROUND_BUDGET`, and the CLI
(`scripts/verify_round_budget.py`) is wired into `validate-all.sh`.

### Registry lint

The mission and adapter registry has a single source of truth: `scripts/lib/fleet_registry.py`, whose
`MISSIONS` table is what `mission_registry.py` and `fleet_outcome.py`'s `MISSION_METRICS` derive from.
Registry lint (`scripts/lib/registry_lint.py`) keeps that table honest against the rest of the repo. It
checks three seams: every `shipped: true` registry row points at a real `skills/<dir>/SKILL.md` and
every on-disk mission skill has a `shipped: true` row (no drift in either direction); every shipped
mission id is mentioned in the catalog files (`README.md` and `skills/autonomous-fleet/SKILL.md`); and
the shipped skill dirs on disk reconcile with `skills-lock.json` (skills vendored from another source,
like `skill-creator` from `anthropics/skills`, are excluded so the check stays apples-to-apples). The
kill switch is `FLEET_DISABLE_REGISTRY_LINT`, and the CLI (`scripts/registry_lint.py`) is wired into
`validate-all.sh`.

### Reviewer-sandbox attribution

The reviewer is read-only, and Layer-style enforcement of that is the subject of the
[Roles and blindness](08-roles-and-blindness.md) chapter (the live `run-sandboxed.sh --role reviewer`
placement). The standing gate here is its audit-side companion:
`scripts/lib/reviewer_sandbox.py` reads a run-archive `manifest.json` and checks that no reviewer
producer slug is attributed a write. A reviewer producer (detected by `reviewer` appearing in the
producer slug, or passed explicitly with `--reviewer-producer`) may only emit `blind_fix`, `findings`,
or `verify_summary` entries. A reviewer attributed a `diff` or `commit` on the candidate branch is a
hard failure, and any other kind from a reviewer producer is rejected too. The kill switch is
`FLEET_DISABLE_REVIEWER_SANDBOX`, and the CLI (`scripts/verify_reviewer_sandbox.py`) is wired into
`validate-all.sh`.

### Namespacing

When several runs (or several checkouts of one run) share a host, their branches and worktrees must not
collide. The namespace helpers (`scripts/lib/namespace.py`) derive a 6-hex run suffix from the run_id
(`derive_run_short`) and stamp it onto every isolated branch (`namespaced_branch` ->
`<prefix><slug>-<run_short>`) and worktree (`namespaced_worktree` -> `../<repo>-<slug>-<run_short>`). The
validator reads each archive's manifest and the progress ledgers it lists, and fails any task row whose
branch or worktree path does not end with `-<run_short>`. The kill switch is `FLEET_DISABLE_NAMESPACING`,
and the CLI (`scripts/validate_namespacing.py`) is wired into `validate-all.sh`.

### Recovery scanner (advisory, at resume)

The recovery scanner is the one tool in this group that is not a standing gate. It runs at resume, and it
is purely advisory: it never shells out beyond the snapshots its caller hands it and never mutates the
repo. `scripts/lib/recovery_scan.py` takes three text snapshots (the markdown progress ledger,
`git worktree list --porcelain`, and `gh pr list --json number,headRefName,state,mergedAt`) and
classifies each task row as `live`, `dead`, `partial`, or `orphan`, then attaches a recommended action:
`CONTINUE`, `CLEANUP_WORKTREE`, `RE_DRIVE`, `ESCALATE_TO_DECISIONS`, or `ARCHIVE_ORPHAN`. A coordinator
inspects those classifications at resume time and decides what to do; the scanner itself never executes
any of the actions. A row whose `RESUME_COUNT` has reached `MAX_RESUME_ATTEMPTS` (3) is escalated rather
than continued or re-driven. Because it is advisory and runs at resume, it has no `FLEET_DISABLE_*` knob
and is not part of `validate-all.sh`. The CLI is `scripts/recovery_scan.py`.

## Why mutation testing beats coverage

Line coverage answers "did a test execute this line?" It does not answer "would a test fail if this
line were wrong?" Those are different questions, and only the second one matters.

Consider Layer 1's quoted-line grep. A test that calls `verify_findings_doc` and asserts nothing about
the result would still cover the grep line. Coverage would report it green. But if you broke the grep,
that test would stay green, because it never asserted the grep's behaviour. The line is covered and
untested at the same time.

The mutation `verify-findings-hallucination-gate-off` makes that impossible to fake. It replaces
`quoted_norm and quoted_norm in source_norm` with `True`. Now the grep always "matches." If the test
suite stays green under that mutation, the suite is tautological and the gate fails the build. The only
way to make the mutation get caught is to have a test that actually asserts a finding with a fake quote
is marked unverified. That is the test you wanted all along, and the mutation gate is what forces it to
exist.

```
  coverage asks:        was this line run?              (cheap, gameable)
  mutation testing asks: would a test fail if it broke?  (the question that matters)
```

This is why the substrate leans on mutation pinning instead of a coverage percentage. A high coverage
number is easy to reach and easy to fake. A surviving mutation is a specific, named admission that a
specific test does not actually test what it claims to. The manifest is a list of "if this breaks, a
test notices" promises, and the gate keeps those promises honest.

## What is not yet enforced

Honesty is doctrine here, so here is what the substrate does not do today, derived against `main`, not
copied from any older audit.

The trace stream is sparse in production. The substrate's verifiers run and gate as described above,
but the trace stream that a dashboard would read emits exactly one event in production code today:
`T-FINAL`, written by `fleet_run.write_manifest`. That event is now correctly emitted BEFORE the
manifest write, per the engine's "trace first, ledger second" doctrine, and the ordering is mutation
covered (`write-manifest-trace-emit-off`). The schema covers eleven primitives, and the stream is
intentionally sparse while per-transition emission rolls out: the coordinator and adapters emit the
rest per the engine TRACE EMISSION doctrine, but that rollout is in progress. See the
[Trace schema](16-trace-schema.md) reference for the full contract and the "what's emitted today"
section. This does not affect the four verification layers, which gate on artifacts on disk, not on the
trace stream.

Headless campaign mode is not yet fully validated end-to-end. The campaign scripts (`run-campaign.sh`)
drive each runtime's CLI in headless mode, which requires that CLI to be authenticated on the host. The
interactive path (chat, or `/goal`) is the supported flow today. The substrate's layers behave the same
either way; the caveat is about the campaign runner, not the verifiers. See the
[Campaigns](10-campaigns.md) chapter and the [Safety and secrets](12-safety-and-secrets.md) chapter for
the headless-mode details.

Layer 2 ships on the Claude Code adapter, where the Stop hook contract exists. Other adapters can adopt
the same gate, and the library is adapter-agnostic, but the wired-in Stop hook is a Claude Code
feature. The mtime-based ordering in Layer 3 and the path-containment in Layers 1 and 3 are
adapter-independent and apply to any run-archive.

What you should take away: the verification is real and the gates bite, pinned by 50 mutations of which
eleven target the substrate directly. The trace stream that visualizes it is still being wired
transition by transition. We document both, because documentation that hides a limitation is worse than
no documentation.
## Real-world use cases

### Example — Layer 1 findings on fixture

`p0-review-findings.json` in example-fixture: two findings, F-001 verified with blind-fix chain
to `reviewer-blind-fix-F-001.md`.

### Invocation — substrate-off bench comparator

`docs/external-dogfood/adversarial-bench-2026-06.md` documents running twice per target with
`FLEET_DISABLE_STOP_VERIFY=1` (off) vs unset (on). Results: PENDING operator runs.

### Real run on stop-verify log

Fixture includes `stop-verify-decisions.log` (producer: `stop-verify-hook`) — Layer 2 evidence from
the adversarial-review-and-fix archive shape.

---

← [Previous: The Engine](06-the-engine.md) · [Guide Index](README.md) · [Next: Roles and Blindness →](08-roles-and-blindness.md)
