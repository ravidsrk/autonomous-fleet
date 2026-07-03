# Layer 3 — Blind-Fix Verification

Layer 3 of the verification substrate. Mechanical guard for the anti-anchoring
protocol defined in [`review-findings.md` § ANTI-ANCHORING](review-findings.md).
This file is the spec the verifier (`<SUBSTRATE>/verify_blind_fix.py`) enforces.

Layer 1 (`verify_findings.py`) protects against reviewer **hallucination**
(quoted lines that don't exist).
Layer 2 (`stop_verify.py`) protects against premature **STOP** (worker
declares done without evidence).
Layer 3 protects against reviewer **anchoring** (reviewer reads a candidate
patch first, then "discovers" findings that match it).
Layer 4 (`validate_run_archive.py`) protects against tampered **archives**.

# The invariant

For each finding `<finding-id>` in `<run_id>`:

1. A blind-fix file MUST exist at one of:
   - `.fleet/runs/<run_id>/reviewer-blind-fix-<finding-id>.md` (canonical),
     OR
   - `.fleet/runs/<run_id>/<reviewer>/reviewer-blind-fix-<finding-id>.md`
     (multi-reviewer setups)

2. The blind-fix file's mtime MUST be EARLIER than the
   `p0-review-findings.json` mtime.
   - mtime ordering is the corpus-grounded signal of "this opinion was
     formed before that opinion."

3. The blind-fix file MUST contain a **point of creation** statement
   (file:function:line shape), in the same language as ROOT_CAUSE_DEPTH.

4. The blind-fix file MUST contain a **pre-commit confidence** number 0–100.

5. (Optional, when present) The optional `blind_fix_chain` block in the
   finding MUST reference an existing blind-fix file. A finding that
   claims a `blind_fix_chain.path` that doesn't exist on disk fails the
   verifier.

# What the verifier does NOT check

- The semantic correctness of the blind fix. A reviewer can be wrong about
  the point of creation and still pass Layer 3. Layer 1 (verified evidence)
  and the FROZEN-ARTIFACT CLOSE TEST cover correctness.
- The blind fix's similarity to the final fix. We deliberately do NOT
  measure how close the reviewer's pre-commit guess matches the eventual
  fix. The protocol is about ordering, not accuracy.
- Multi-reviewer agreement. That's a separate concern (cross-vendor
  diversity audit, see `engine.md` SIGNAL RECONCILIATION).

# Failure modes the verifier catches

| Mode | Detection |
|---|---|
| Reviewer skipped the blind-fix step entirely | No file at the canonical path → fail |
| Reviewer wrote the blind-fix file AFTER opening the candidate patch | mtime(blind-fix) > mtime(findings) → fail |
| Reviewer pasted the candidate patch's diff into the blind-fix file | content lacks point-of-creation line OR contains `diff --git`/`+++ b/` markers → fail |
| Reviewer claimed a blind-fix chain in JSON but the file is missing | `blind_fix_chain.path` resolves to a non-existent file → fail |
| Reviewer wrote a stub ("TODO", "n/a", "see PR") | content too short (< 80 chars after stripping) OR matches stub patterns → fail |

# Exit codes

- `0` — every closed finding has a valid blind-fix chain
- `1` — at least one finding violates the protocol (details in stderr)
- `2` — usage error (bad CLI args, missing run-archive)

# Wiring

- `<SUBSTRATE>/verify_blind_fix.py` — CLI entrypoint
- `<SUBSTRATE>/lib/verify_blind_fix.py` — library (jsonschema-free, like
  `verify_findings.py`)
- `scripts/validate-all.sh` — runs the verifier against the fixture
  archive on every CI run
- `tests/test_verify_blind_fix.py` — coverage gate at 100%

# Lineage

- `review-findings.md` § ANTI-ANCHORING (the protocol)
- `engine.md` ROLE TIER (reviewer is STRONG tier; this verifier protects
  the most-expensive reviewer slot)
- `engine.md` SIGNAL RECONCILIATION (Layer 3 is one of the reconciled
  signals, alongside Layer 1 verification and Layer 2 stop-verify
  decisions)
