---
finding_id: F-002
reviewer: grok
---

# Blind fix for F-002

The point of creation is `scripts/validate-first-substrate-archive.sh:37` — the
Layer-1 gate invokes `verify_findings.py` with `--summary-out` but omits
`--write`, so verified flags never persist into `p0-review-findings.json`.

The shape of the fix is to add `--write` on the same invocation block (between
`--repo "$ROOT"` and `--summary-out`), matching how operators run verify during
live missions.

Pre-commit confidence: 88/100.