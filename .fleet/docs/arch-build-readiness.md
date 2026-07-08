---
fleet-outcome:
  schema_version: "1.0"
  mission: adversarial-review-and-fix
  status: done
  repo: ravidsrk/autonomous-fleet
  base_branch: cursor/adversarial-review-base-256a
  prs_merged: 13
  run_id: 20260708T184204Z-adversarial-review-and-fix-c6c486
  archive_enabled: true
  reviewer_mode: same-vendor-instructed
  e2e_verified: true
  metrics:
    p0_open: 0
    p1_open: 0
    findings_open: 0
    ops_queue_count: 0
    verified_findings: 21
    unverified_findings: 0
    auto_applicable_findings: 15
    human_gated_findings: 6
  deferred_missions:
    - doc-sync
---

# Arch-build readiness — adversarial-review-and-fix (c6c486)

Generated: 2026-07-08T19:19:41Z

## Summary

Code-grounded adversarial review of the entire autonomous-fleet app (scripts, substrate, CI, campaign orchestration, security surfaces). Phase 0 froze 21 confirmed findings (1 DO_NOT_FIX). Phase 1 closed all 15 Lane A findings via merge-commits into BASE `cursor/adversarial-review-base-256a`. Six Lane B findings are HUMAN_GATED with draft-both variants in `.fleet/docs/DECISIONS.md`.

## Finding status

### CLOSED (Lane A) — merged into BASE

| ID | PR | Notes |
|----|-----|-------|
| SEC-001 | #135 | eval removed; HOST allowlist; argv exec |
| SEC-008 | #135 | skills@1.5.12 pin (same PR) |
| SEC-002 | #136 | run_id validation + containment |
| SEC-003 | #137 | bwrap --unshare-net |
| SEC-007 | #138 | SECURITY.md classifier sync |
| BUG-003 | #139 | namespace regex = RUN_ID_PATTERN |
| ARCH-001 | #140 | fleet-verify sha-pin + reviewer-sandbox layers |
| BUG-001 | #141 | created_utc precedes file mtimes |
| ARCH-002 | #142 | archived mission exec gate |
| BUG-002 | #142 | remove \|\| true on blocked parse |
| BUG-004 | #143 | table-row resume increment |
| ARCH-003 | #144 | FLEET_LEDGER_DIR in promotion |
| OPS-001 | #145 | fatal real-run archive emit |
| OPS-002 | #146 | adapter auth timeout |
| SEC-011 | #147 | findings JSON byte cap |

### HUMAN_GATED (Lane B)

SEC-004, SEC-005, SEC-009, ARCH-004, ARCH-005, SEC-010 — see `.fleet/docs/DECISIONS.md`.

### DO_NOT_FIX

SEC-006 — intentional version-tolerant auth probe + timeout.

## OPS queue

None. Lane B items are human policy choices, not out-of-band ops.

## Recommended next missions

1. **doc-sync** — SECURITY.md already patched; remaining docs may drift after this wave.
2. Human review of Lane B variants (especially SEC-004 Action SHA pins and SEC-005 sandbox fail-closed).

## PRs

- Integration BASE: https://github.com/ravidsrk/autonomous-fleet/pull/134
- Fix PRs: #135–#147 (merged into BASE locally; GitHub merge may require human if token lacks merge)

## Validation notes

- Substrate: `scripts/sync_substrate_assets.py` re-run after merges.
- Reviewer mode: `same-vendor-instructed` (Grok/Cursor single-vendor host).
- `gh` GraphQL create/merge unavailable for integration token; PRs opened via ManagePullRequest; merges performed as local merge-commits into BASE then pushed.
