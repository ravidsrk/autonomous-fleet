# Run-archive scheme

Reference for the `.fleet/runs/<run_id>/` archive directory and its
`manifest.json`. The engine-recovery.md ARCHIVE_ENABLED block has the doctrine;
this doc has the operational detail.

## What's an archive?

Every run that emits ANY first-class artifact lands under a single directory:

```
.fleet/runs/<run_id>/
├── manifest.json                       # the audit trail
├── p0-review-findings.json             # Layer 1 schema-verified findings
├── p0-verify-summary.json              # Layer 1 verifier output
├── p0-skeptic-findings.json            # Layer 1 second-pass findings
├── p0-skeptic-verify-summary.json
├── reviewer-blind-fix-F-001.md         # Layer 3 anti-anchoring blind fix
├── reviewer-blind-fix-F-002.md
├── docs-arch-build-readiness.md        # T-FINAL output (also lives in docs/)
└── docs-arch-build-progress.md         # progress ledger snapshot
```

First-class artifacts:

| Kind | Producer | Notes |
|---|---|---|
| `findings` | reviewer | Layer 1 schema-verified findings JSON |
| `verify_summary` | verifier | Layer 1's `verify_findings.py --summary-out` |
| `blind_fix` | reviewer | Layer 3 anti-anchoring blind-fix file, mtime BEFORE findings |
| `prompt` | coordinator | The exact prompt sent to a worker/reviewer (text or JSON) |
| `response` | worker/reviewer | The raw response from a worker/reviewer |
| `diff` | builder | Patch or PR diff that was applied |
| `readiness` | T-FINAL | The mission's `*-readiness.md` |
| `progress` | coordinator | Snapshot of the `*-progress.md` ledger at terminate |
| `other` | any | Escape hatch; does not participate in mtime-ordering checks |

## run_id format

`YYYYMMDDTHHMMSSZ-<mission>-<6-hex>` (e.g.
`20260623T141522Z-adversarial-review-and-fix-3a9c2f`).

- UTC timestamp prefix: sort-by-time auditability.
- Mission slug middle: greppable (`ls .fleet/runs/ | grep adversarial`).
- 6-hex suffix: collision avoidance for concurrent runs on the same
  coordinator-pid in the same second.

Allocate with `scripts.lib.fleet_run.allocate_run_id(mission)`. Parse with
`parse_run_id(run_id)`. Freeform run-ids (operator pet names, branch names)
are REJECTED by the schema and the validator — the post-hoc replay machinery
indexes runs by this exact format.

## manifest.json

The manifest is the AUDIT TRAIL. Without it, the directory is files with no
provenance. Schema: `assets/fleet-run-manifest.schema.json`. Each file entry:

```json
{
  "path": "p0-review-findings.json",
  "kind": "findings",
  "sha256": "<64 hex>",
  "mtime_utc": "2026-06-23T14:18:33Z",
  "producer": "p0-reviewer-claude",
  "bytes": 4321
}
```

Notes:

- `path` is RELATIVE to the archive directory. `..` segments and absolute
  paths are rejected at write time (`file_entry_for` raises) and at validate
  time (belt + braces).
- `producer` pairs blind-fix and findings entries for the per-producer
  mtime-ordering check. A reviewer that emits N findings must have N blind
  fixes preceding them, all tagged with the same producer slug.
- `bytes` is checked before `sha256` (cheap fail-fast on truncated files).

## Mtime ordering invariants (the discipline)

Schema-clean is NECESSARY but NOT SUFFICIENT. The validator also enforces
the cross-cutting orderings that encode the Layers 1-3 disciplines:

1. **`blind_fix` mtime < `findings` mtime (per producer)** — Layer 3
   ANTI-ANCHORING. The reviewer's blind fix MUST exist on disk before it
   opened the candidate diff and wrote findings.

2. **`verify_summary` mtime > `findings` mtime (per producer)** — Layer 1.
   The verifier runs AGAINST a findings doc. A summary older than the
   findings is a stale audit from a previous run, mis-archived.

3. **`readiness` has the LATEST mtime in the archive** — T-FINAL is the last
   thing the mission does; anything mtime-after the readiness doc was
   written outside the run boundary and breaks the audit story.

4. **`findings` from different producers must not be byte-identical** —
   independent-review integrity. Two findings artifacts from DIFFERENT
   producer slugs sharing one sha256 mean the "independent second pass"
   (skeptic, second reviewer) was a copy, not a review. Same-producer
   duplicates are not flagged by this invariant (shape checks own those).
   Lineage: the quarantined first-substrate fixture shipped reviewer and
   skeptic findings with one sha256 and passed validation (issues #77/#78).

A manifest whose listed files don't satisfy these orderings FAILS
validation, even when every checksum matches.

## Validation

```sh
# All archives under .fleet/runs/
python3 <SUBSTRATE>/validate_run_archive.py

# Specific archive
python3 <SUBSTRATE>/validate_run_archive.py .fleet/runs/<run_id>/

# Cheap pre-flight (skip on-disk sha256 verification)
python3 <SUBSTRATE>/validate_run_archive.py --no-checksums
```

Exit 0 = pass, exit 1 = at least one archive failed. Lives behind
`scripts/validate-all.sh` like the fleet-outcome validator.

## archive_enabled in fleet-outcome

T-FINAL records two top-level fields in the readiness doc's fleet-outcome
frontmatter:

```yaml
fleet-outcome:
  mission: adversarial-review-and-fix
  status: done
  run_id: 20260623T141522Z-adversarial-review-and-fix-3a9c2f
  archive_enabled: true
  # ... rest of fleet-outcome
```

- `archive_enabled: true` requires the validator passes.
- `archive_enabled: false` is incompatible with `status: done` — the
  fleet-outcome validator rejects that combination.
- Missions that emitted no first-class artifacts OMIT both fields.

## Retention

The fleet does NOT garbage-collect run-archives. Operators decide retention
out-of-band (e.g. delete `.fleet/runs/` directories older than N days); the
engine loop never prunes. Old runs degrade gracefully: a pruned archive
referenced by a later readiness doc is recorded by `validate-all.sh` as a
broken provenance link but does not fail the build.

## What this does NOT replace

- EVID / WT_CLEAN: the archive PRESERVES the artifacts they're set against;
  it doesn't replace the disciplines themselves.
- The stop-verify hook (Layer 2): scans the archive for `verify_summary`
  files in window. ARCHIVE_ENABLED is what makes those files exist in a
  deterministic place; without the archive, the hook has nothing to find.
- Schema-verified findings (Layer 1): the findings JSON lives IN the
  archive; the schema and verifier are separate from the archive scheme.
- Anti-anchoring (Layer 3): the blind-fix file lives IN the archive; the
  mtime-ordering invariant in the archive validator is what makes the
  protocol tamper-evident.

The archive is the substrate every Layer 1-3 discipline sits on.

## Size cap

Each `.fleet/runs/<run_id>/` directory is capped at **5 MB**. Archives that
exceed the cap MUST use [`git lfs`](https://git-lfs.com/) for their large
artifacts (prompts/responses are the usual offenders). The 5 MB cap exists
because the archive is checked into the repo as a first-class artifact:
without a cap, a single oversized run would balloon the working tree for
every clone forever.

The canonical example of archive shape is `.fleet/runs/example-fixture/`,
generated by `scripts/_build_example_fixture.py`. It is committed verbatim
and exercised by `validate-all.sh` so a future schema change fails CI
before it lands. Do not delete it; use it as the template for what a
well-shaped real archive looks like.

Operators who need to archive a run larger than 5 MB should:

1. `git lfs track "*.prompt" "*.response"` (or whichever artifacts blew the
   budget) inside the run directory.
2. Commit the `.gitattributes` change along with the archive.
3. Confirm `git lfs ls-files` lists every oversized file before pushing.

The run-archive validator **hard-enforces** the cap: a manifest whose listed
`bytes` sum exceeds 5 MB fails validation unless the archive tracks its large
artifacts with git-lfs (a `.gitattributes` carrying `filter=lfs` in the archive
dir). `validate_run_archive.py` (run by `validate-all.sh`) reports the overage.
