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
- `scripts/validate-all.sh` (framework clone only) — runs the verifier against the fixture
  archive on every CI run
- `tests/test_verify_blind_fix.py` — coverage gate at 100%

# Lineage

- `review-findings.md` § ANTI-ANCHORING (the protocol)
- `engine.md` ROLE TIER (reviewer is STRONG tier; this verifier protects
  the most-expensive reviewer slot)
- `engine.md` SIGNAL RECONCILIATION (Layer 3 is one of the reconciled
  signals, alongside Layer 1 verification and Layer 2 stop-verify
  decisions)

<!-- demoted from engine.md (issue #84) -->
═══════════════════════════════════════════════════════════
ANTI-ANCHORING: reviewer commits its own fix BEFORE reading the candidate patch.
═══════════════════════════════════════════════════════════
The cross-vendor build-blind reviewer rule says the reviewer never sees the build conversation.
That's necessary but not sufficient: even WITH no build context, a reviewer handed a patch and
asked "is this correct?" anchors on whatever it sees. The reviewer rationalises the existing fix,
because rationalising an artifact is cognitively cheaper than independently re-deriving the
correct one. SWE-Review's empirical result: reviewers given the same patch in two orders — patch
first vs root-cause-first — produce systematically different decisions on the same case.

The mechanical countermeasure: BEFORE the reviewer opens the candidate diff, it writes its
INDEPENDENT proposed fix to `.fleet/runs/<run_id>/reviewer-blind-fix-<finding-id>.md` (one file
per reviewer in multi-reviewer setups). The blind fix names:

- The POINT OF CREATION (file:function:line — same call-stack-depth language as ROOT_CAUSE_DEPTH).
- The shape of the change the reviewer would make (a paragraph; no code required).
- The reviewer's pre-commit confidence (0–100).

ONLY THEN does the reviewer open the candidate patch. The review then compares the candidate to
its own pre-committed blind fix and writes findings accordingly. A candidate that agrees with the
blind fix at the same call-stack depth gets weight; a candidate at a different depth triggers the
ROOT_CAUSE_DEPTH HARD RULE (engine.md stub; full doctrine in `review-findings.md`).

The blind-fix file is a first-class fleet artifact: it lands in `.fleet/runs/<run_id>/`
alongside the findings JSON, ships with the readiness doc's archive bundle, and is auditable
post-hoc. A review run whose blind-fix file is missing or is mtime-AFTER the candidate-findings
file is structurally suspect — the protocol requires blind-fix BEFORE patch read, and the
filesystem must reflect that order.

Lineage: SWE-Review's "Step 3: Write YOUR Proposed Fix (BEFORE reading the patch)" prompt step
(`prompts/agentic_review.md` Step 3). The committed-in-writing-first technique is the
proven anti-anchoring scaffold from the academic literature. See
`docs/competitor-audit-2026-06-22.md` #4.
