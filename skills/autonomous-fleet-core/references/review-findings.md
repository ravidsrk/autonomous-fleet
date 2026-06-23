# Schema-verified review findings

This reference defines how review missions emit STRUCTURED findings that the
fleet can grep-verify against source. It is the cross-cutting protocol for any
mission whose reviewer phase produces findings — primarily
`adversarial-review-and-fix` today, but `bug-batch`, `dependency-update`, and
`take-product-to-completion` reviewer gates may adopt the same shape.

The schema lives at
`skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json`.

## Why this exists

Reviewer hallucination is the second most common failure mode after build
contamination. A reviewer with a 200-line diff in front of it will, at
non-trivial rates, invent a finding that quotes a line that doesn't exist in
the cited file — sometimes from a sibling file, sometimes from imagination.
That hallucinated finding then enters the fix loop, the builder dutifully
hunts a phantom bug, and an entire round is wasted in pursuit of nothing.

The countermeasure is mechanical, not procedural: every finding cites a
verbatim line, and the orchestrator greps the file for that line. Findings
whose quote can't be located are marked `verified: false` and DOWNGRADED — they
do NOT enter the fix loop, do not count toward `auto_applicable_findings`,
and DO count toward `unverified_findings` so the fleet-outcome reflects the
audit.

Lineage:
- GodModeSkill (99xAgency) `work-converge.py` self-consistency check — the
  quoted-line grep originated there.
- xreview (Aronchick) `internal/schema/review.json` — confidence,
  fix_alternatives, fix_strategy originated there.
- 2026-06-22 competitor audit (`/workspace/audit-work/borrowable-patterns-report.md`).

## The protocol

Reviewer phase:

1. The reviewer writes findings to a JSON file conformant to the schema. Path
   convention: `.fleet/runs/<run_id>/<reviewer>-findings.json` (one file per
   reviewer in multi-reviewer setups).
2. The coordinator runs `python scripts/verify_findings.py <findings.json>
   --repo <REPO_ROOT> --write --summary-out <summary.json>`.
3. The CLI exits 0 (all verified), 1 (at least one unverified), 2 (schema
   violation), or 3 (usage error). Coordinators MUST treat exit 1 as a fail —
   the fix loop SHALL NOT consume findings from an exit-1 verify.
4. The four summary metrics from `<summary.json>` (`verified_findings`,
   `unverified_findings`, `auto_applicable_findings`, `human_gated_findings`)
   land in `fleet-outcome.metrics` of the mission's readiness doc.

Fix phase consumes ONLY:
- `verified: true` AND `fix_strategy: auto` AND `confidence >= 80` → builder
  may apply the recommended `fix_alternative` without asking
- `verified: true` AND `fix_strategy: ask` → builder pauses for operator
  confirmation of which alternative to apply
- `verified: true` AND `confidence < 60` → reviewer is asked to gather more
  evidence or omit
- `verified: false` → DOWNGRADED. Operator inspects manually. The finding
  does NOT auto-feed the fix loop regardless of declared confidence or
  strategy. This is the safety property.

## Required fields per finding

| Field | Why |
|-------|-----|
| `id` | Stable across rounds. Same finding keeps the same id when re-asserted. |
| `severity` | critical / high / medium / low — gating tier. |
| `category` | bug / security / architecture / performance / style / test / root_cause_depth / other. |
| `claim` | One sentence. The finding itself. |
| `evidence.file_path` | Path relative to repo root (or absolute). |
| `evidence.quoted_line` | EXACT verbatim line. The grep target. |
| `fix_alternatives` | 1-4 labeled proposals (A/B/C/D), each with effort = minimal/moderate/large. |
| `confidence` | 0-100. Reviewer's certainty this is a real defect. |
| `fix_strategy` | `auto` or `ask`. Auto requires verified AND confidence ≥ 80. |

`cascade_impact` is REQUIRED for `category: root_cause_depth` (root-cause-depth
findings without a cascade are usually symptom-fix findings in disguise — see
the ROOT_CAUSE_DEPTH discipline, planned for Commit 3).

## Required verdict

```json
{
  "verdict": {
    "decision": "approve | request_changes | partial",
    "reasoning": "One paragraph: why approve, why not, or what partial means."
  }
}
```

## Example minimal finding

```json
{
  "id": "F-007",
  "severity": "high",
  "category": "bug",
  "claim": "Worktree path resolution falls back to active checkout silently when WT_CLEAN gate fails.",
  "evidence": {
    "file_path": "scripts/run-sandboxed.sh",
    "line_number": 142,
    "quoted_line": "    [ -z \"$wt\" ] && wt=\"$ACTIVE_CHECKOUT\""
  },
  "fix_alternatives": [
    {
      "label": "A",
      "description": "Replace silent fallback with explicit error: return 1 with diagnostic.",
      "effort": "minimal",
      "recommended": true
    },
    {
      "label": "B",
      "description": "Gate the fallback behind a `--allow-active-fallback` opt-in flag.",
      "effort": "moderate"
    }
  ],
  "confidence": 92,
  "fix_strategy": "auto",
  "cascade_impact": "Three callers in scripts/lib/ rely on the WT_CLEAN gate; silent fallback breaks all three."
}
```

After `verify_findings.py` runs against this:
- If `scripts/run-sandboxed.sh` contains a line matching (whitespace-tolerant)
  `[ -z "$wt" ] && wt="$ACTIVE_CHECKOUT"` — finding gets `verified: true`,
  counts toward `auto_applicable_findings` (auto + conf ≥ 80).
- If the line isn't there — finding gets `verified: false` with
  `verify_reason: "quoted_line not found in cited file"`, counts toward
  `unverified_findings`. Operator inspects.

## ROOT_CAUSE_DEPTH — schema-enforced

A finding tagged `category: root_cause_depth` is the schema's encoding of
the engine's ROOT_CAUSE_DEPTH HARD RULE (see `engine.md`): the candidate
patch sits at a shallower call-stack location than the bug's point of
creation, so the same root cause can still be triggered via other paths
even though the originally reported path no longer reproduces.

When `category` is `root_cause_depth`, the schema REQUIRES `cascade_impact`
to be present and non-empty. The verifier rejects findings that violate
this — a root-cause-depth finding without a named cascade is almost always
a symptom-fix finding miscategorised, and the fleet refuses to file it.

The builder MUST re-EVID every cascade path named in `cascade_impact`,
not just the originally reported reproduction. Closing only the first path
leaves the discipline unsatisfied — the same root cause still fires through
the other named paths. The mission's readiness doc records the aggregate
audit result in the top-level `root_cause_audited` boolean (see
`fleet-outcome.md`): `true` when every cascade closed, `false` when any
were deferred (which then MUST appear in `deferred_missions`).

## ANTI-ANCHORING — blind-fix-first protocol

Reviewers anchor on the candidate patch they see. The fleet's countermeasure
is procedural: before opening any candidate diff, the reviewer commits its
own independent proposed fix to disk.

Path convention: `.fleet/runs/<run_id>/reviewer-blind-fix-<reviewer-or-finding-id>.md`,
one per reviewer in multi-reviewer setups, or one per finding in
fix-loop-phase reviews. Contents:

- The POINT OF CREATION the reviewer would change (file:function:line,
  same language as ROOT_CAUSE_DEPTH).
- The shape of the change in a paragraph (no code required).
- The reviewer's pre-commit confidence (0–100).

The audit trail is mtime-ordered: the blind-fix file MUST exist on disk
BEFORE the candidate-findings file's mtime. A blind-fix file that is
missing or mtime-after the findings file means the protocol was violated;
the coordinator surfaces the violation and re-runs review on the affected
PR. The mission's adversarial-review-and-fix SKILL wires this into Phase 1
explicitly.

The blind fix is a first-class fleet artifact: it ships with the readiness
doc's archive bundle (see `engine.md` STRICT MODE evidence kinds — a
blind-fix file qualifies as an `e2e_artifact`-grade fleet output for the
stop-verify hook) and is post-hoc auditable.

## What this does NOT replace

- The `EVID` discipline still applies. A finding only CLOSES when its own
  reproduction stops reproducing — `verified: true` is necessary but not
  sufficient for closure. See `engine.md` FROZEN-ARTIFACT CLOSE TEST. For
  `category: root_cause_depth` findings, EVID applies separately to EACH
  cascade path named in `cascade_impact`, not just the originally reported
  reproduction.
- The build-blind reviewer rule still applies. Verification is a check on
  *what the reviewer said*; build-blindness is a check on *how the reviewer
  came to say it*; anti-anchoring is a check on *the order in which the
  reviewer formed the opinion*. The three rules compose.
- The cross-vendor reviewer rule still applies. A reviewer that hallucinates
  consistently is a candidate for rotation regardless of any single-finding
  verification result.

The schema is one more layer on top of the existing disciplines, not a
replacement for any of them.
