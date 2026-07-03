---
title: "Run-archive anatomy"
description: "Every file inside a .fleet/runs/<id>/ directory, the manifest schema field-by-field, and the integrity gates that make a run replayable."
sidebar:
  order: 15
---

# Run-archive anatomy

Every run that produces first-class artifacts leaves a directory behind:
`.fleet/runs/<run_id>/`. That directory is the run-archive. It holds the findings the
reviewer filed, the blind-fix notes that prove the reviewer was not anchored on the patch,
the verifier's summary, the fix attestation, the trace stream, the stop-verify decisions,
and the `fleet-outcome.yaml` that says whether the run is done. At the center sits one
`manifest.json` that lists every file with a sha256, a size, an mtime, and a producer.

This chapter is the reference for that directory. It walks every file kind, then the
manifest schema field-by-field, then the integrity gates the validator enforces. If you
want to know how the archive is _produced_ (who calls what, in what order), that is
[The engine](/06-the-engine/), not here. This chapter is about reading an archive that
already exists on disk.

**On this page:** [Why an archive exists](#why-an-archive-exists) ·
[The directory at a glance](#the-directory-at-a-glance) ·
[The manifest](#the-manifest) · [Manifest schema, field-by-field](#manifest-schema-field-by-field) ·
[File kinds](#file-kinds) · [The artifact files](#the-artifact-files) ·
[The SHA-pin record](#the-sha-pin-record) ·
[Integrity gates](#integrity-gates) · [The size cap](#the-size-cap) ·
[Validating an archive](#validating-an-archive) ·
[The example fixture](#the-example-fixture) · [Quick reference](#quick-reference)

## Why an archive exists

The doctrine is simple: a run that produced artifacts must be reconstructable after the
fact from the listed files plus their checksums. No database, no server, no log aggregator.
A directory of files and one manifest that pins their integrity. You can `tar` it, attach
it to a PR, hand it to an auditor, or `git`-commit it, and a year later the validator can
still tell you whether anything was tampered with.

Two properties make the archive worth more than "a folder of logs":

1. Integrity. Every file is pinned by sha256 and byte-size in the manifest. The validator
   re-hashes on disk and fails loudly on any mismatch. A file that was edited after archive
   time is detected, not silently trusted.

2. Ordering. The manifest records each file's mtime, and the validator enforces
   cross-cutting ordering invariants between file kinds. The reviewer's blind-fix must
   predate the findings. The verifier's summary must postdate the findings. The readiness
   doc must be the latest file. These orderings are not cosmetic. They are the
   anti-anchoring discipline made auditable: a run that files findings before writing its
   blind fix has cheated, and the archive catches it.

The enforcement surface is `scripts/lib/fleet_run.py`. The CLI that runs it over your
`.fleet/runs/` tree is `scripts/validate_run_archive.py`. Both are covered below.

## The directory at a glance

A run-archive is flat. Every artifact sits directly under the run-id directory, no
nesting. Here is the shape, using the canonical example fixture's file set (plus the
`sha-pin.json` a review-and-fix run adds, which the fixture itself does not carry):

```
.fleet/runs/<run_id>/
├── manifest.json              the audit trail: one entry per file below
├── p0-review-findings.json    reviewer findings (kind: findings)
├── p0-verify-summary.json     verifier output over the findings (kind: verify_summary)
├── reviewer-blind-fix-F-001.md  blind fix for F-001 (kind: blind_fix)
├── reviewer-blind-fix-F-002.md  blind fix for F-002 (kind: blind_fix)
├── p1-fix-attestation.json    fix-landed attestation (kind: other)
├── stop-verify-decisions.log  stop-verify hook decisions (kind: other)
├── trace.jsonl                the dashboard contract stream (kind: other)
├── sha-pin.json               reviewer's pinned branch HEAD at PASS (kind: other; not in fixture)
├── fleet-outcome.yaml         the run outcome doc (kind: readiness)
└── README.md                  human-readable directory note (kind: other)
```

The directory name is the run-id. Its format is strict:
`YYYYMMDDTHHMMSSZ-<mission>-<6-hex>`, for example
`20260623T000000Z-adversarial-review-and-fix-000001`. The UTC timestamp prefix gives
sort-by-time auditability, the mission slug gives greppability, and the 6-hex suffix
disambiguates two runs that start in the same second on the same coordinator. The validator
only picks up directories whose basename matches that regex (`RUN_ID_PATTERN` in
`fleet_run.py`), so operator scratch directories like `tmp/` or `notes/` are skipped.

> The example fixture is the one deliberate exception: its directory is named
> `example-fixture` (obviously not a real run) while the `run_id` _field_ inside its
> `manifest.json` is a regex-valid id. See [The example fixture](#the-example-fixture).

## The manifest

`manifest.json` is the heart of the archive. It is the only file the validator reads
directly; every other file is verified _through_ the manifest. The library that writes it
is `fleet_run.write_manifest`. Here is the full manifest from the example fixture, lightly
trimmed in the middle for length:

```json
{
  "schema_version": "1.0",
  "run_id": "20260623T000000Z-adversarial-review-and-fix-000001",
  "mission": "adversarial-review-and-fix",
  "coordinator": "example-coordinator",
  "base_branch": "roadmap/post-substrate-impl",
  "created_utc": "2026-06-23T00:00:00Z",
  "files": [
    {
      "path": "reviewer-blind-fix-F-001.md",
      "kind": "blind_fix",
      "sha256": "72515941c67914824420ac2e9b0824cb617448ec63db07b27f055734a93db1b2",
      "mtime_utc": "2026-06-23T00:01:00Z",
      "producer": "p0-reviewer-claude",
      "bytes": 576
    },
    {
      "path": "p0-review-findings.json",
      "kind": "findings",
      "sha256": "91a7ca0885bd414613bbf11c2d02d9eb1bab48e66a0ceefca0d006b3cbbabf06",
      "mtime_utc": "2026-06-23T00:05:00Z",
      "producer": "p0-reviewer-claude",
      "bytes": 2570
    }
  ],
  "notes": "Canonical example fixture, exercises every validator in validate-all.sh."
}
```

Two things to notice before the field reference:

- The manifest is created at the _start_ of the run, then files accrete during it. So
  `created_utc` is earlier than the mtime of any listed file. This is an enforced invariant,
  not a convention.
- `files` is never empty. A run that produced zero artifacts has no archive, hence no
  manifest. The schema sets `minItems: 1`, and `write_manifest` raises
  `ValueError("manifest requires at least one file entry")` if you hand it nothing.

## Manifest schema, field-by-field

The authoritative schema is
`skills/autonomous-fleet-core/assets/fleet-run-manifest.schema.json` (JSON Schema draft
2020-12, `$id` `https://autonomous-fleet.dev/schemas/fleet-run-manifest.schema.json`). The
lib in `fleet_run.py` re-implements the same constraints in plain Python so the library
stays dependency-free, and a drift test asserts the two agree. `additionalProperties` is
`false` at both the top level and inside each file entry: an unexpected key fails validation.

Top-level fields:

```
field           required  type    constraint
─────────────── ────────  ──────  ────────────────────────────────────────────────────
schema_version  yes       string  const "1.0". Bumps require synchronous lib + verifier
                                   + doc updates. Mismatch is a hard error.
run_id          yes       string  ^[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*[a-z0-9]-[0-9a-f]{6}$
                                   Freeform pet-name ids are REJECTED.
mission         yes       string  minLength 1. MUST equal the slug embedded in run_id.
                                   The validator cross-checks; mismatch fails.
created_utc     yes       string  ISO 8601 UTC, Z-terminated, optional fractional seconds.
                                   Earlier than every file's mtime.
files           yes       array   minItems 1. One entry per first-class artifact.
coordinator     no        string  minLength 1. Slug that orchestrated the run, e.g.
                                   "codex", "claude-code". Used by post-mortem chaining.
base_branch     no        string  minLength 1. The branch the run was based on. For replay.
notes           no        string  Freeform human note. NOT used by the validator.
```

Each entry in `files` is a `file_entry`. All six fields are required:

```
field      type     constraint
────────── ───────  ──────────────────────────────────────────────────────────────────
path       string   minLength 1. RELATIVE to the archive directory. No leading "/",
                     no ".." segments. Path-escape attempts are rejected at validation
                     time AND at construction time in file_entry_for().
kind       string   enum of 9 values (see File kinds below). Drives mtime ordering.
sha256     string   ^[0-9a-f]{64}$. Hex sha256 of the file's on-disk bytes at archive
                     time. The validator re-hashes and rejects mismatches.
mtime_utc  string   ISO 8601 UTC, Z-terminated. The file's mtime when the manifest was
                     written. Drives the kind-ordering invariants.
producer   string   minLength 1. The worker/reviewer slug that produced the file, e.g.
                     "p0-reviewer-claude", "fixer-codex", "verifier", "human".
                     Blind-fix/findings ordering is paired BY producer, not globally.
bytes      integer  minimum 0. File size at archive time. Checked before sha256 as a
                     cheap fail-fast on size mismatch.
```

The `producer` field is load-bearing for the ordering checks. The validator does not pair
"the earliest blind-fix" with "the earliest findings" globally. It groups by producer first,
so a multi-reviewer run with reviewer A and reviewer B is checked per reviewer: A's blind-fix
must predate A's findings, B's blind-fix must predate B's findings, and the two reviewers do
not constrain each other. The shipped example fixture records the `verify_summary` producer as
`verifier`; the validator groups verify summaries by exact producer slug when applying the
verify-summary-after-findings check.

## File kinds

`kind` is a closed enum of nine values. Three of them participate in the mtime-ordering
invariants; the rest are categorical only.

```
kind            ordering role
─────────────── ──────────────────────────────────────────────────────────────────────
findings        Pinned: blind_fix < findings < verify_summary (per producer).
verify_summary  Pinned: must be strictly AFTER its producer's findings.
blind_fix       Pinned: must be strictly BEFORE its producer's findings.
readiness       Pinned: must hold the LATEST mtime in the archive.
prompt          Categorical only. No ordering constraint.
response        Categorical only. No ordering constraint.
diff            Categorical only. No ordering constraint.
progress        Categorical only. No ordering constraint.
other           Escape hatch. Does NOT participate in ordering. A kind=other file that
                carries meaningful mtime claims is a smell, per the schema note.
```

Note that the example fixture stores `stop-verify-decisions.log`, `p1-fix-attestation.json`,
`trace.jsonl`, and even `README.md` as `kind: other`. They are real artifacts, but they do
not constrain ordering, so `other` is correct. A real review-and-fix run's `sha-pin.json` is
`kind: other` for the same reason (the fixture does not carry one). The only `readiness` file
in the fixture is `fleet-outcome.yaml`, which is why that file carries the latest mtime in the
manifest.

## The artifact files

Beyond the manifest, here is what each artifact in a typical
`adversarial-review-and-fix` archive holds. The fixture is the reference; your real runs
will have the same shapes with real content.

### Findings (`p0-review-findings.json`)

The reviewer's structured output, conforming to
`skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json`. It carries the
review id, the reviewer identity (vendor, model, role), the round, an array of findings,
and a verdict. Each finding has an `id` (e.g. `F-001`), a `severity`, a `category`, a
`claim`, an `evidence` block (file path, line number, the quoted line), one or more
`fix_alternatives`, a `confidence` score, a `fix_strategy`, and a `verified` boolean. In the
fixture, `F-001` is a verified real defect and `F-002` is a deliberately seeded
hallucination (`verified: false`, with a `verify_reason` explaining the quoted line is not
in the cited file) so the archive exercises the Layer-1 downgrade path. The verdict is
`request_changes`.

### Verify-summary (`p0-verify-summary.json`)

The verifier's roll-up over the findings, produced by `scripts/verify_findings.py`. It
records the `run_id`, the `findings_doc` it audited, `total_findings`, `verified_findings`,
`unverified_findings`, and an `unverified_ids` array. The fixture shows
`total_findings: 2`, `verified_findings: 1`, `unverified_findings: 1`,
`unverified_ids: ["F-002"]`, which is the verifier catching the seeded hallucination.

### Blind-fix files (`reviewer-blind-fix-F-001.md`, `reviewer-blind-fix-F-002.md`)

One per finding, written by the reviewer _before_ they file findings. The discipline is in
`skills/autonomous-fleet-core/references/blind-fix.md`: the reviewer records where the bug
originates and the shape of the fix, blind to whatever candidate patch exists, so the
review cannot be anchored on the patch's framing. Each file is markdown with frontmatter
(`finding_id`, `reviewer`) followed by the point-of-creation analysis and a pre-commit
confidence score. The mtime of a blind-fix file must be strictly before the matching
findings file's mtime, paired by producer. That ordering is what makes the blind-fix
genuinely blind, and the archive validator enforces it.

### Fix attestation (`p1-fix-attestation.json`)

The fixer's record that a fix landed. It carries the `mission`, `run_id`, `finding_id`,
a `fix_landed` boolean, a `blind_fix_chain` (the blind-fix path plus the
`reviewer_quote_sha`, `fixer_draft_sha`, and `integration_sha` that chain the reviewer's
quote through the fixer's draft to the integrated commit), `attested_by`, and `attested_at`.
It is stored as `kind: other`.

### Stop-verify decisions (`stop-verify-decisions.log`)

A JSONL log from the Claude Code adapter's stop-verify hook (`scripts/stop_verify.py`,
Layer 2 of the substrate). Each line is one decision: a `decision` (`block` or `allow`), a
`reason`, a timestamp `ts`, and the `worker`. In the fixture, line one is a `block`
("unverified findings present") and line two is an `allow` ("all findings verified or
downgraded"), showing the gate doing its job across the run.

### Trace stream (`trace.jsonl`)

The dashboard contract stream, conforming to
`skills/autonomous-fleet-core/assets/fleet-trace.schema.json`. One JSON object per line.
Each event carries a `primitive`, a `role`, a `status`, the `run_id`, the `mission`, a
`schema_version`, a `ts`, and (for worker-scoped events) a `task_id`. The fixture's stream
walks `SPAWN_WORKER` (started) to `INSPECT` (succeeded) to `FREEZE` (succeeded) to `COMMIT`
(succeeded). This file is the subject of the next chapter,
[Trace schema (v1)](/16-trace-schema/).

> What's emitted today: in production code, exactly one trace event is wired, the `T-FINAL`
> event emitted by `fleet_run.write_manifest`. The schema covers all 11 primitives, and the
> fixture's richer stream shows the contract, but the live stream is intentionally sparse
> while per-transition emission rolls out across the coordinator and adapters. Do not expect
> a full event-per-transition stream in a real run yet. See
> [Trace schema (v1)](/16-trace-schema/) for the rollout detail.

### SHA-pin record (`sha-pin.json`)

The reviewer's machine substrate that records the exact branch SHA inspected at PASS time.
It is stored as `kind: other` (it carries no ordering claim) and is the subject of the next
section, [The SHA-pin record](#the-sha-pin-record). Its job: a REVIEWED verdict is only valid
while the branch HEAD still equals the SHA the reviewer actually looked at. If the branch
moves after the reviewer signed off, the pin flips that verdict to OUTDATED and forces a
force re-review, so a stale approval can never ride a later commit into a merge.

### Outcome doc (`fleet-outcome.yaml`)

The `readiness` file: the single document that says whether the run is done and what it
produced. It is YAML frontmatter (the machine-readable `fleet-outcome` block) followed by a
human-readable body. The frontmatter carries `mission`, `status`, `repo`, `base_branch`,
`prs_merged`, `archive_enabled`, `run_id`, `cost_estimate`, a `metrics` map
(`p0_open`, `p1_open`, `findings_open`, `ops_queue_count`, `unverified_findings`,
`e2e_verified`), and a `run` block (`duration_min`, `note`). Campaign gates read these
fields from the previous node. The full field reference for this file is
[fleet-outcome schema](/17-fleet-outcome-schema/). Because it is the `readiness` kind, it
must hold the latest mtime in the archive.

## The SHA-pin record

`sha-pin.json` is a small reviewer-written artifact that closes a specific cheat: a reviewer
approves a branch, then the branch gains new commits, and the stale REVIEWED verdict rides
the new code into a merge unreviewed. The pin makes a PASS verdict valid only while the
branch HEAD still equals the SHA the reviewer actually inspected.

The schema is `skills/autonomous-fleet-core/assets/fleet-sha-pin.schema.json` (JSON Schema
draft 2020-12, `$id` `https://autonomous-fleet.dev/schemas/fleet-sha-pin.schema.json`). The
enforcement lib is `scripts/lib/verify_sha_pin.py`; the CLI that loads records and resolves
branch heads is `scripts/verify_sha_pin.py`, wired into `validate-all.sh`. The record is a
single object with `additionalProperties: false`:

```json
{
  "schema_version": "1.0",
  "review_id": "p0-review-001",
  "reviewed_sha": "0123456789abcdef0123456789abcdef01234567",
  "branch": "fleet/some-feature-a1b2c3",
  "verdict": "PASS",
  "merged": true
}
```

Field by field:

```
field           required  type     constraint
─────────────── ────────  ───────  ─────────────────────────────────────────────────────
schema_version  yes       string   const "1.0".
review_id       yes       string   ^[a-zA-Z0-9._/-]+$. Stable id for this review run.
reviewed_sha    yes       string   ^[0-9a-fA-F]{40}$. The exact commit SHA the reviewer
                                    inspected. This is what HEAD must still equal.
branch          yes       string   ^[a-zA-Z0-9._/-]+$. The branch whose HEAD is pinned
                                    to reviewed_sha while the task is unmerged.
verdict         yes       string   enum: approve, PASS, request_changes, partial, fail,
                                    FAIL. Only approve/PASS are ENFORCED; the others are
                                    schema-valid but skipped (nothing to enforce).
merged          no        boolean  Post-merge marker. If true and the branch is gone,
                                    the check is N/A instead of a failure.
```

The enforcement logic in `verify_sha_pin.verify_sha_pin` is hermetic: it takes the parsed
records plus an injected `head_resolver(branch) -> sha | None`, so the pure function does no
git or filesystem I/O. For each record:

- A non-approving verdict (anything outside `{approve, PASS}`) is skipped. There is nothing
  to enforce on a request-changes record.
- An enforced record whose branch HEAD still equals `reviewed_sha` passes. The reviewer
  looked at exactly what is there.
- An enforced record whose branch moved (`reviewed_sha != head`) is an error:
  `<branch> moved <reviewed_sha>..<head>: REVIEWED is OUTDATED, force re-review`. This is the
  flip from REVIEWED to OUTDATED.
- An enforced record whose branch is unknown or deleted (`head_resolver` returns `None`) is
  the careful case. If `merged: true`, the deletion is the expected post-merge cleanup and the
  check is N/A. If there is no merged marker, it is an error: the pin cannot be enforced and a
  bare missing branch is not allowed to silently pass.

The whole gate honors the substrate kill-switch `FLEET_DISABLE_SHA_PIN` (see
`scripts/lib/substrate_disable.py`). As with every other gate, only set it when you know
precisely why you are turning a safety check off.

## Integrity gates

The validator runs four classes of check. All four must pass: shape, mtime ordering, the size cap
(see [The size cap](#the-size-cap) below), and on-disk verification.

### 1. Shape

`_validate_shape` re-implements the JSON Schema in Python: required fields present,
`schema_version == "1.0"`, `run_id` matches the regex, `mission` equals the run-id slug,
`created_utc` is a valid Z-terminated UTC timestamp, `files` is a non-empty list, and every
file entry has a valid `path` (no leading slash, no `..`), a `kind` in the enum, a 64-hex
`sha256`, a valid `mtime_utc`, a non-empty `producer`, and a non-negative integer `bytes`
(bools are explicitly rejected, since `True` is an `int` in Python).

### 2. Mtime ordering

`_validate_ordering` enforces the three cross-cutting invariants from the engine's
ARCHIVE_ENABLED hard rule, and `_validate_independence` adds a fourth. These are the
disciplines made auditable:

```
Invariant 1  blind_fix mtime  <  findings mtime         (strictly, per producer)
             A violation is an ANTI-ANCHORING violation: the reviewer filed findings
             before writing the blind fix, so the blind fix was not blind.

Invariant 2  verify_summary mtime  >  findings mtime     (strictly, per producer)
             A violation is a stale-audit violation: the verifier "audited" findings
             that did not exist yet.

Invariant 3  readiness mtime  =  max(all file mtimes)
             A violation is a readiness-not-latest violation: some artifact was written
             after the run was declared done.

Invariant 4  findings sha256 unique across producers
             A violation is an independent-review violation: two findings artifacts
             from different producers sharing one sha256 mean the "independent second
             pass" was a copy, not a review (the quarantined first-substrate fixture
             exhibited exactly this — issues #77/#78).
```

A manifest can be schema-clean and still fail here. That is the point. The doctrine is not
"files exist", it is "files exist in the order the discipline demands". The ordering parser
skips entries that already failed the shape check (so errors are not double-reported) and
uses `datetime.fromisoformat` after swapping the trailing `Z` for `+00:00`.

### 3. On-disk verification

`_validate_files_on_disk` walks each listed file: it resolves the path and re-checks it does
not escape the archive root (belt and braces with the shape check), confirms the file exists,
compares the on-disk size against `bytes` (cheap fail-fast, skips hashing a wrong-sized
file), then re-hashes the file and compares against `sha256`. Any mismatch is an error. This
is the gate that catches post-archive tampering: edit a file after the manifest was written
and its sha256 (and usually its size) no longer match.

You can skip the on-disk hash pass with `--no-checksums` for a cheap pre-flight, but the
full validator (shape + ordering + size cap + checksums) must pass before `T-FINAL`.

## The size cap

Alongside the sha256 and mtime-ordering invariants, the validator enforces a per-archive size cap.
`_validate_size_cap` sums the `bytes` field of every file entry in the manifest and rejects the
archive when the total exceeds `MAX_ARCHIVE_BYTES`, which is 5 MB (`5 * 1024 * 1024` in
`fleet_run.py`). The cap keeps a run-archive committable inline: a directory that balloons past a
few megabytes does not belong in the repo as ordinary blobs, it belongs in git-lfs.

git-lfs is the overflow path, not an exception that disables the cap. When the total goes over 5 MB,
the validator reads the archive directory's own `.gitattributes`, parses out the path globs tracked
by lfs (`_lfs_patterns` picks lines carrying `filter=lfs`), and re-checks the cap against only the
files NOT matched by those globs (`_matches_lfs` matches both the full relative path and the
basename). If the non-lfs bytes stay under 5 MB, the archive passes: the large artifacts are tracked
by lfs and exempt from the in-repo cap, while everything else still has to fit. An lfs rule that does
not actually match the oversized files does not save the archive, the non-lfs total is still over and
it fails. With no `.gitattributes` (or no lfs patterns in it), the cap applies to every byte.

The failure line names the cap and points at the fix:

```
FAIL .fleet/runs/<id>
  - .../manifest.json: non-LFS archive bytes exceed the 5242880-byte cap; track the large
    artifacts with git lfs (see references/run-archive.md)
```

Like the other gates, this runs on the manifest's recorded `bytes`, so it is part of the cheap
pre-flight too: `--no-checksums` skips the on-disk hash pass but still enforces shape, ordering, and
the size cap.

## Validating an archive

The CLI is `scripts/validate_run_archive.py`. With no arguments it scans
`.fleet/runs/*` under the current directory and validates every directory whose name matches
the run-id regex:

```bash
python scripts/validate_run_archive.py
```

Validate specific archives by passing their paths:

```bash
python scripts/validate_run_archive.py .fleet/runs/20260623T000000Z-doc-sync-a1b2c3
```

Point the default scan at a different repo root:

```bash
python scripts/validate_run_archive.py --repo-root /path/to/repo
```

Cheap pre-flight, schema and ordering only, no hashing:

```bash
python scripts/validate_run_archive.py --no-checksums
```

Print only failures (suppress the per-archive `OK` lines):

```bash
python scripts/validate_run_archive.py --quiet
```

Output is one line per archive. A passing archive prints `OK   <path>`. A failing archive
prints `FAIL <path>` followed by one indented `- <error>` line per problem. Exit codes:

```
0  all validated archives pass, OR no archives are present
1  one or more archives failed
```

The validator honors the substrate kill-switch. If the `FLEET_DISABLE_RUN_ARCHIVE`
environment variable is set (see `scripts/lib/substrate_disable.py`), it announces it is
disabled and returns without validating. Use that only when you know why you are turning a
safety gate off.

A few representative failure lines, so you recognize them:

```
FAIL .fleet/runs/<id>
  - .../manifest.json: schema_version must be '1.0', got '2.0'
  - .../manifest.json.files[2]: sha256 mismatch, manifest says <a>, disk says <b>
  - .../manifest.json: ANTI-ANCHORING violation: blind_fix '...' (producer='...') mtime
    ... is not strictly before findings '...' mtime ...
  - .../manifest.json: readiness-not-latest violation: other file '...' mtime ... is
    after the latest readiness mtime ...
```

For the human-readable mapping of failure to fix, see
[Troubleshooting](/14-troubleshooting/).

## The example fixture

The repo ships a canonical archive at `.fleet/runs/example-fixture/`. It is not a real run.
It is the input every validator in `validate-all.sh` exercises, so a future schema or
library drift fails CI loudly instead of silently. It is generated by
`scripts/_build_example_fixture.py`, which pins each file's mtime with `os.utime` to a
deterministic UTC instant. To regenerate it:

```bash
python scripts/_build_example_fixture.py
```

The script is idempotent and overwrites everything under the directory; the resulting
fixture is committed verbatim.

The fixture is deliberately constructed to walk every check:

- Two `blind_fix` files (T+1m, T+1m30s) precede the `findings` file (T+5m), which precedes
  the `verify_summary` (T+6m). Invariants 1 and 2 pass.
- `fleet-outcome.yaml` (T+10m) is the latest mtime. Invariant 3 passes.
- `F-001` is a real verified finding; `F-002` is a seeded hallucination so the verifier's
  downgrade path is exercised end-to-end.

One thing to be aware of when you read the fixture: its directory is named `example-fixture`
(so it is obviously not a real run), while the `run_id` field inside its `manifest.json` is
`20260623T000000Z-adversarial-review-and-fix-000001`, which is regex-valid. That lets the
manifest's run-id and mission cross-checks pass without special-casing the fixture. The
directory-name exemption from the run-id regex is handled by the validator only picking up
regex-matching directory names during a default scan; the fixture is fed to the validator
explicitly.

## Quick reference

```
.fleet/runs/<run_id>/                  the archive directory (name matches run-id regex)
  manifest.json                        the audit trail (the only file read directly)
  *.json / *.md / *.yaml / *.log ...   the artifacts, each pinned in the manifest

run-id format    YYYYMMDDTHHMMSSZ-<mission>-<6-hex>
manifest schema  skills/autonomous-fleet-core/assets/fleet-run-manifest.schema.json
lib              scripts/lib/fleet_run.py   (write_manifest, validate_manifest_payload, ...)
cli              scripts/validate_run_archive.py
kill-switch      FLEET_DISABLE_RUN_ARCHIVE  (scripts/lib/substrate_disable.py)

sha-pin record   sha-pin.json (kind: other)  reviewer pins reviewed_sha + branch + verdict
sha-pin schema   skills/autonomous-fleet-core/assets/fleet-sha-pin.schema.json
sha-pin lib      scripts/lib/verify_sha_pin.py   cli scripts/verify_sha_pin.py (validate-all)
sha-pin switch   FLEET_DISABLE_SHA_PIN
  REVIEWED -> OUTDATED when branch HEAD != reviewed_sha; N/A when deleted + merged:true

ordering invariants
  blind_fix  <  findings  <  verify_summary   (strict, per producer)
  readiness  =  max(all mtimes)

size cap         5 MB total non-LFS bytes (MAX_ARCHIVE_BYTES); LFS-tracked files exempt

validate everything   python scripts/validate_run_archive.py
validate one          python scripts/validate_run_archive.py .fleet/runs/<id>
pre-flight only       python scripts/validate_run_archive.py --no-checksums
failures only         python scripts/validate_run_archive.py --quiet
exit 0 pass · exit 1 one or more failed
```

Related reference chapters: [Trace schema (v1)](/16-trace-schema/) for `trace.jsonl`, and
[fleet-outcome schema](/17-fleet-outcome-schema/) for `fleet-outcome.yaml`.
## Real-world use cases

### Example — example-fixture manifest

Nine manifest files (kinds spanning `blind_fix`, `findings`, `verify_summary`, `readiness`) plus an
eleven-line `trace.jsonl` — run_id `20260623T000000Z-adversarial-review-and-fix-000001`.

### Invocation — write_manifest + T-FINAL

`fleet_run.write_manifest` emits T-FINAL into `trace.jsonl`; representative helper fills the other
primitives for mechanical validation.

### Worked example — sha256 + mtime on every file

Each manifest entry in example-fixture includes `sha256`, `mtime_utc`, `bytes` — replay attack
surface is checksum-bound.

---

← [Troubleshooting](/14-troubleshooting/) · [Guide Index](/) · [Trace schema (v1)](/16-trace-schema/) →
