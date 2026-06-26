# first-substrate-review (frozen Phase 0, 2026-06-27)

PHASE: REVIEW_FROZEN  
MISSION: adversarial-review-and-fix  
SCOPE: post-v0.1.0 substrate proof (headless trace, fleet_run, validators)

## Confirmed findings (skeptic-narrowed)

| ID | Sev | Lane | Area | Status |
|----|-----|------|------|--------|
| F-001 | medium | A | fleet_run progress resolution | OPEN → fix |
| F-002 | low | A | validate-first-substrate-archive | OPEN → fix |

## Refuted / do-not-fix

(none)

## F-001 — progress_text_for_mission ignores mission_registry remapping

**Severity:** medium · **Category:** bug · **Lane:** A · **Tag:** CODE

**Problem:** `fleet_run.progress_text_for_mission` builds `docs/{mission}-progress.md`
naively. `adversarial-review-and-fix` maps to `docs/arch-build-progress.md` via
`mission_registry.progress_path`, and `run-mission-headless.sh` already uses that
mapping for `/goal` text. Headless dry-run trace emission therefore falls back to
synthetic progress (`PHASE: mechanical validation`) and derives wrong INSPECT/MERGE/
GOAL_BLOCKED statuses for the shipped adversarial mission.

**Evidence:** `scripts/lib/fleet_run.py:239`

```python
    path = source_root / "docs" / f"{mission}-progress.md"
```

Repro: `progress_text_for_mission(Path('.'), 'adversarial-review-and-fix')` returns
synthetic fallback while `docs/arch-build-progress.md` exists on disk.

**Fix:** Resolve the progress doc via `mission_registry.progress_path(mission)` (same
primitive `run-mission-headless.sh` uses). Reuse in-tree `progress_path`; add regression
test in `tests/test_headless_trace.py`.

**Acceptance:** Headless dry-run for `adversarial-review-and-fix` archives an excerpt
containing `arch-build-progress` header text; `plan_dryrun_trace_from_progress` reads
`PHASE: DONE` from the real ledger.

## F-002 — validate-first-substrate-archive omits verify_findings --write

**Severity:** low · **Category:** test · **Lane:** A · **Tag:** CODE

**Problem:** Lane-1 archive gate runs `verify_findings.py` with `--summary-out` only.
Without `--write`, `verified` / `verify_reason` fields are not persisted into
`p0-review-findings.json` on disk. The archive summary and exit code pass, but the
findings artifact is not self-describing for post-hoc audit.

**Evidence:** `scripts/validate-first-substrate-archive.sh:37-39`

```bash
  "$VENV_PYTHON" "$ROOT/scripts/verify_findings.py" \
    "$ARCHIVE/p0-review-findings.json" --repo "$ROOT" \
    --summary-out "$ARCHIVE/p0-verify-summary.json"
```

**Fix:** Add `--write` to the invocation so verified findings are stamped in the JSON
artifact the gate already requires.

**Acceptance:** After `validate-first-substrate-archive.sh`, every finding in
`p0-review-findings.json` has `verified: true`.

## Validated strengths (do-not-touch)

- `mission_registry.progress_path` / `readiness_path` remapping table
- `emit_dryrun_lifecycle_trace` eleven-primitive orchestration
- `write_manifest` T-FINAL-before-write ordering
- example-fixture canonical CI shape

## Hot-file collision map

| File | Findings |
|------|----------|
| `scripts/lib/fleet_run.py` | F-001 |
| `scripts/validate-first-substrate-archive.sh` | F-002 |
| `tests/test_headless_trace.py` | F-001 test |

## Clusters

- **C-001 (FOUNDATION):** substrate path resolution — `touches:` fleet_run.py,
  `CLOSES=[F-001]`