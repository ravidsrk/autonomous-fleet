#!/usr/bin/env python3
"""Regenerate the canonical example-fixture run-archive.

Usage: ``python scripts/_build_example_fixture.py``

The fixture lives at ``.fleet/runs/example-fixture/`` and is the canonical
input that every validator exercises in ``validate-all.sh``. The directory
name intentionally does NOT match the strict ``run_id`` regex; it is the
**fixture** for the validators, not a real run. The manifest's ``run_id``
field IS a regex-valid id (``20260623T000000Z-example-fixture-000001``) so
the manifest validator's cross-checks succeed.

Run this whenever the schemas or layer libraries change shape, then commit
the resulting fixture verbatim. The script is idempotent: it overwrites
everything under the fixture directory but never touches anything else.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

FIXTURE_DIR = REPO_ROOT / ".fleet" / "runs" / "example-fixture"
# run_id's mission slug must literally equal MISSION (the manifest validator
# cross-checks). The fixture pretends to be an adversarial-review-and-fix run.
RUN_ID = "20260623T000000Z-adversarial-review-and-fix-000001"
MISSION = "adversarial-review-and-fix"

# Deterministic, repeatable timestamps. All UTC.
# Invariant order:
#   T_CREATED <= every file mtime
#   T_BLIND_FIX_* < T_FINDINGS  (anti-anchoring)
#   T_VERIFY_SUMMARY > T_FINDINGS  (stale-audit guard)
#   T_READINESS = max(all)  (no post-readiness edits)
T_CREATED = "2026-06-23T00:00:00Z"
T_BLIND_FIX_F001 = "2026-06-23T00:01:00Z"  # BEFORE findings (Layer 3 invariant)
T_BLIND_FIX_F002 = "2026-06-23T00:01:30Z"  # BEFORE findings
T_FINDINGS = "2026-06-23T00:05:00Z"
T_VERIFY_SUMMARY = "2026-06-23T00:06:00Z"  # AFTER findings
T_ATTESTATION = "2026-06-23T00:07:00Z"
T_TRACE = "2026-06-23T00:08:00Z"
T_README = "2026-06-23T00:09:00Z"  # other; ignored by ordering
T_READINESS = "2026-06-23T00:10:00Z"  # latest (no post-readiness edits)


def _iso_to_epoch(iso: str) -> float:
    """Parse an ISO-8601 ``Z`` timestamp to a unix epoch."""
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write(path: Path, content: bytes, mtime_iso: str) -> None:
    path.write_bytes(content)
    epoch = _iso_to_epoch(mtime_iso)
    os.utime(path, (epoch, epoch))


# ── Layer 1 findings doc ────────────────────────────────────────────────
# Finding F-001: verified=true. Quotes a real line in scripts/coupling-graph.py
# (line 107). The verifier whitespace-tolerantly greps and finds it, so
# verify_findings exits 0 with unverified_findings: 0 over this fixture.
#
# Finding F-002: verified=false. Cites a real file but quotes a string that
# does NOT exist there. verify_reason explains the simulated hallucination
# for the docs reader; verify_findings would set the same flag at runtime.
FINDINGS_DOC = {
    "schema_version": "1.0",
    "mission": MISSION,
    "review_id": "example-fixture-r1-claude",
    "reviewer": {
        "vendor": "anthropic",
        "model": "claude-opus-4.5",
        "role": "build-blind-reviewer",
    },
    "round": 1,
    "findings": [
        {
            "id": "F-001",
            "severity": "medium",
            "category": "bug",
            "claim": (
                "ImportFrom with explicit relative level is dropped from the "
                "coupling graph; level==0 absolute-only check skips PEP-328 "
                "relative imports entirely on the first pass."
            ),
            "evidence": {
                "file_path": "scripts/coupling-graph.py",
                "line_number": 107,
                "quoted_line": "            if node.level == 0:",
            },
            "fix_alternatives": [
                {
                    "label": "A",
                    "description": (
                        "Drop the level==0 gate; reconstruct the relative "
                        "dotted name in the same branch and feed it to the "
                        "suffix index."
                    ),
                    "effort": "minimal",
                    "recommended": True,
                },
                {
                    "label": "B",
                    "description": (
                        "Add an `else` branch that defers to the existing "
                        "PEP-328 reconstruction path."
                    ),
                    "effort": "moderate",
                },
            ],
            "confidence": 88,
            "fix_strategy": "auto",
            "trigger": "Repos that use `from .x import y` heavily.",
            "verified": True,
            "blind_fix_chain": {
                "path": "reviewer-blind-fix-F-001.md",
                "reviewer_quote_sha": "abc1234",
                "fixer_draft_sha": "def5678",
            },
        },
        {
            "id": "F-002",
            "severity": "low",
            "category": "style",
            "claim": (
                "Simulated hallucination: the quoted_line below is NOT in the "
                "cited file. Used to exercise verify_findings's hallucination "
                "downgrade path on the fixture."
            ),
            "evidence": {
                "file_path": "scripts/coupling-graph.py",
                "line_number": 9999,
                "quoted_line": "    raise NotImplementedError('this is not in the file')",
            },
            "fix_alternatives": [
                {
                    "label": "A",
                    "description": "Drop the finding; it's a hallucination.",
                    "effort": "minimal",
                    "recommended": True,
                },
            ],
            "confidence": 35,
            "fix_strategy": "ask",
            "verified": False,
            "verify_reason": (
                "quoted_line not found in cited file — simulated hallucination "
                "for fixture coverage of the Layer 1 downgrade path."
            ),
        },
    ],
    "verdict": {
        "decision": "request_changes",
        "reasoning": (
            "One verified finding (F-001) with a real defect; one simulated "
            "hallucination (F-002) marked verified=false. Fixture exercises "
            "the substrate end-to-end."
        ),
    },
}

# ── Layer 3 blind-fix files ─────────────────────────────────────────────
# Both mtimes precede T_FINDINGS so the anti-anchoring ordering invariant
# holds. Body contains the 4 required ingredients: point-of-creation
# (file:symbol:line), 80+ chars of substantive content, no diff markers,
# no stub patterns, and a confidence between 0 and 100.
BLIND_FIX_F001 = """---
finding_id: F-001
reviewer: claude-opus-4.5
---

# Blind fix for F-001

The point of creation is `scripts/coupling-graph.py:_iter_imports:107` — the
walker reads each `ast.ImportFrom` node and only records the dotted name
when `node.level == 0`, which drops every PEP-328 relative import on the
first pass even though the suffix index later in the file can resolve them.

The shape of the fix is to drop the level-gate in this branch and let the
existing relative-import reconstruction at the bottom of the same function
handle both axes. Pre-commit confidence: 78/100.
"""

BLIND_FIX_F002 = """---
finding_id: F-002
reviewer: claude-opus-4.5
---

# Blind fix for F-002

The point of creation is `scripts/coupling-graph.py:_iter_imports:9999` —
the line cited by the reviewer was a guess; on re-inspection the file ends
well before line 9999, so this blind fix records the reviewer's pre-commit
reasoning anyway so the audit trail is complete.

The shape of the fix is to withdraw the finding; nothing in the cited file
matches the quoted_line. Pre-commit confidence: 30/100.
"""

# ── Layer 2 stop-verify decision log ────────────────────────────────────
STOP_VERIFY_LOG = "\n".join(
    json.dumps(row, sort_keys=True)
    for row in [
        {
            "ts": "2026-06-23T00:04:00Z",
            "worker": "reviewer-1",
            "decision": "block",
            "reason": "unverified findings present",
        },
        {
            "ts": "2026-06-23T00:06:30Z",
            "worker": "reviewer-1",
            "decision": "allow",
            "reason": "all findings verified or downgraded",
        },
    ]
) + "\n"

# ── Layer 4 p1 fix attestation for F-001 ────────────────────────────────
P1_ATTESTATION = {
    "schema_version": "1.0",
    "mission": MISSION,
    "run_id": RUN_ID,
    "finding_id": "F-001",
    "fix_landed": True,
    "blind_fix_chain": {
        "blind_fix_path": "reviewer-blind-fix-F-001.md",
        "reviewer_quote_sha": "abc1234",
        "fixer_draft_sha": "def5678",
        "integration_sha": "0123abc",
    },
    "attested_by": "fixer-codex",
    "attested_at": T_ATTESTATION,
}

# ── verify_summary stub (Layer 1 output, AFTER findings) ────────────────
VERIFY_SUMMARY = {
    "schema_version": "1.0",
    "run_id": RUN_ID,
    "findings_doc": "p0-review-findings.json",
    "total_findings": 2,
    "verified_findings": 1,
    "unverified_findings": 1,
    "unverified_ids": ["F-002"],
}

# ── Trace events (Commit E schema) ──────────────────────────────────────
TRACE_EVENTS = [
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:00:10Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "DISPATCH",
        "role": "COORDINATOR",
        "status": "started",
        "task_id": "task-example-1",
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:00:30Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "SPAWN_WORKER",
        "role": "COORDINATOR",
        "status": "started",
        "task_id": "task-example-1",
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:01:00Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "WAIT",
        "role": "COORDINATOR",
        "status": "started",
        "task_id": "task-example-1",
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:02:00Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "GOAL_BLOCKED",
        "role": "COORDINATOR",
        "status": "skipped",
        "task_id": "task-example-1",
        "details": {"reason": "goal probe passed (fixture)"},
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:05:00Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "INSPECT",
        "role": "REVIEWER",
        "status": "succeeded",
        "task_id": "task-example-1",
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:05:30Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "SYNC",
        "role": "COORDINATOR",
        "status": "succeeded",
        "task_id": "task-example-1",
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:06:00Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "MERGE",
        "role": "INTEGRATOR",
        "status": "succeeded",
        "task_id": "task-example-1",
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:06:30Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "FREEZE",
        "role": "COORDINATOR",
        "status": "succeeded",
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:07:30Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "COMMIT",
        "role": "FIXER",
        "status": "succeeded",
        "task_id": "task-example-1",
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:07:45Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "ABORT",
        "role": "COORDINATOR",
        "status": "skipped",
        "task_id": "task-example-1",
        "details": {"reason": "compensation not taken (fixture)"},
    },
    {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:08:00Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "T-FINAL",
        "role": "INTEGRATOR",
        "status": "succeeded",
        "details": {"manifest": "manifest.json", "files": 9},
    },
]


def _deterministic_event_id_factory():
    next_id = 1

    def factory() -> str:
        nonlocal next_id
        event_id = f"evt-{next_id:04d}"
        next_id += 1
        return event_id

    return factory


def _trace_events_with_ids() -> list[dict]:
    id_factory = _deterministic_event_id_factory()
    events: list[dict] = []
    spawn_id_by_task: dict[str, str] = {}
    dispatch_id_by_task: dict[str, str] = {}
    for event in TRACE_EVENTS:
        row = dict(event)
        row["id"] = id_factory()
        task_id = row.get("task_id")
        if row["primitive"] == "DISPATCH" and isinstance(task_id, str):
            dispatch_id_by_task[task_id] = row["id"]
        if row["primitive"] == "SPAWN_WORKER" and isinstance(task_id, str):
            spawn_id_by_task[task_id] = row["id"]
            parent = dispatch_id_by_task.get(task_id)
            if parent is not None:
                row["parent_event"] = parent
        if row["primitive"] in ("INSPECT", "COMMIT") and isinstance(task_id, str):
            parent_event = spawn_id_by_task.get(task_id)
            if parent_event is not None:
                row["parent_event"] = parent_event
        events.append(row)
    return events


# ── fleet-outcome.yaml (T-FINAL) ────────────────────────────────────────
FLEET_OUTCOME_YAML = """---
fleet-outcome:
  mission: adversarial-review-and-fix
  status: partial
  repo: ravidsrk/autonomous-fleet
  base_branch: roadmap/post-substrate-impl
  prs_merged: 0
  archive_enabled: true
  run_id: 20260623T000000Z-adversarial-review-and-fix-000001
  cost_estimate: 0
  tasks:
    - id: task-example-1
      built: true
      pr_open: true
      reviewed: true
      merged: true
      wt_clean: true
  metrics:
    p0_open: 0
    p1_open: 0
    findings_open: 0
    ops_queue_count: 0
    unverified_findings: 1
    e2e_verified: true
  run:
    duration_min: 0
    note: canonical example fixture — exercises every validator
---

# example-fixture readiness

This is the **canonical example fixture** for the run-archive validators. It
is not a real run; it is the input every validator in `validate-all.sh`
exercises so a future schema or library drift fails CI loudly rather than
silently. Do not delete it without replacing it.
"""

README_BODY = """# example-fixture — canonical run-archive

Do not delete; the example is exercised by `validate-all.sh` (every layer's
validator runs against this directory in CI).

## Files

| File | Purpose | Reference |
|---|---|---|
| `manifest.json` | Layer 4 audit-trail manifest (sha256 + mtime ordering). | `skills/autonomous-fleet-core/assets/fleet-run-manifest.schema.json` |
| `p0-review-findings.json` | Layer 1 reviewer findings (F-001 verified, F-002 simulated hallucination). | `skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json` |
| `reviewer-blind-fix-F-001.md` | Layer 3 anti-anchoring blind-fix for F-001. | `skills/autonomous-fleet-core/references/blind-fix.md` |
| `reviewer-blind-fix-F-002.md` | Layer 3 anti-anchoring blind-fix for F-002. | `skills/autonomous-fleet-core/references/blind-fix.md` |
| `p0-verify-summary.json` | Layer 1 verifier output (verified=1, unverified=1). | `scripts/verify_findings.py` |
| `stop-verify-decisions.log` | Layer 2 stop-verify decision log (one `block`, one `allow`). | `scripts/stop_verify.py` |
| `p1-fix-attestation.json` | Fix-landed attestation with the blind-fix chain populated. | `references/blind-fix.md` |
| `fleet-outcome.yaml` | T-FINAL outcome doc (`archive_enabled: true`, `cost_estimate: 0`). | `scripts/lib/fleet_outcome.py` |
| `trace.jsonl` | Layer-agnostic dashboard contract stream (SPAWN → INSPECT → FREEZE → COMMIT). | `skills/autonomous-fleet-core/assets/fleet-trace.schema.json` |

## Mtime-ordering invariant

The fixture is generated by `scripts/_build_example_fixture.py`, which calls
`os.utime` to pin every file's mtime to a deterministic UTC instant. The
critical ordering is:

```
blind-fix (T+1m, T+1m30s)  <  findings (T+5m)  <  verify-summary (T+6m)
```

This encodes the anti-anchoring discipline from
`skills/autonomous-fleet-core/references/blind-fix.md`: the reviewer's blind
fix MUST be written before the reviewer sees the candidate patch (i.e.
before they file findings). A fixture that violated this ordering would
make the layer-3 mutation guards trivially passable.

## Why a strict run_id format AND a non-strict directory name

The directory is named `example-fixture` (not the `YYYYMMDDTHHMMSSZ-...`
form) so it is obviously not a real run. The manifest's `run_id` field IS
a regex-valid id (`20260623T000000Z-example-fixture-000001`) so the
manifest validator's cross-checks succeed without needing to special-case
the fixture.

## How to regenerate

```bash
python scripts/_build_example_fixture.py
```

The script is idempotent and overwrites everything under this directory.
Commit the resulting fixture verbatim.
"""


def _file_entry(
    path: Path,
    kind: str,
    producer: str,
    content: bytes,
    mtime_iso: str,
) -> dict:
    return {
        "path": path.name,
        "kind": kind,
        "sha256": _sha256_bytes(content),
        "mtime_utc": mtime_iso,
        "producer": producer,
        "bytes": len(content),
    }


def build_fixture() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # Materialise every file (UTF-8 bytes). Order them by mtime ASC so the
    # generated manifest reads in time order, which is what the audit log
    # wants.
    bf1_bytes = BLIND_FIX_F001.encode("utf-8")
    bf2_bytes = BLIND_FIX_F002.encode("utf-8")
    findings_bytes = (json.dumps(FINDINGS_DOC, indent=2) + "\n").encode("utf-8")
    verify_bytes = (json.dumps(VERIFY_SUMMARY, indent=2) + "\n").encode("utf-8")
    stop_bytes = STOP_VERIFY_LOG.encode("utf-8")
    p1_bytes = (json.dumps(P1_ATTESTATION, indent=2) + "\n").encode("utf-8")
    trace_bytes = (
        "\n".join(json.dumps(e, sort_keys=True) for e in _trace_events_with_ids())
        + "\n"
    ).encode("utf-8")
    outcome_bytes = FLEET_OUTCOME_YAML.encode("utf-8")
    readme_bytes = README_BODY.encode("utf-8")

    bf1_path = FIXTURE_DIR / "reviewer-blind-fix-F-001.md"
    bf2_path = FIXTURE_DIR / "reviewer-blind-fix-F-002.md"
    findings_path = FIXTURE_DIR / "p0-review-findings.json"
    verify_path = FIXTURE_DIR / "p0-verify-summary.json"
    stop_path = FIXTURE_DIR / "stop-verify-decisions.log"
    p1_path = FIXTURE_DIR / "p1-fix-attestation.json"
    trace_path = FIXTURE_DIR / "trace.jsonl"
    outcome_path = FIXTURE_DIR / "fleet-outcome.yaml"
    readme_path = FIXTURE_DIR / "README.md"

    _write(bf1_path, bf1_bytes, T_BLIND_FIX_F001)
    _write(bf2_path, bf2_bytes, T_BLIND_FIX_F002)
    _write(findings_path, findings_bytes, T_FINDINGS)
    _write(verify_path, verify_bytes, T_VERIFY_SUMMARY)
    _write(stop_path, stop_bytes, T_VERIFY_SUMMARY)
    _write(p1_path, p1_bytes, T_ATTESTATION)
    _write(trace_path, trace_bytes, T_TRACE)
    _write(outcome_path, outcome_bytes, T_READINESS)
    _write(readme_path, readme_bytes, T_README)

    # Build the manifest. Only first-class kinds participate in the
    # ordering invariants; the stop-verify log, attestation, trace,
    # fleet-outcome, and README map to `other`.
    file_entries = [
        _file_entry(bf1_path, "blind_fix", "p0-reviewer-claude", bf1_bytes, T_BLIND_FIX_F001),
        _file_entry(bf2_path, "blind_fix", "p0-reviewer-claude", bf2_bytes, T_BLIND_FIX_F002),
        _file_entry(findings_path, "findings", "p0-reviewer-claude", findings_bytes, T_FINDINGS),
        _file_entry(verify_path, "verify_summary", "verifier", verify_bytes, T_VERIFY_SUMMARY),
        _file_entry(stop_path, "other", "stop-verify-hook", stop_bytes, T_VERIFY_SUMMARY),
        _file_entry(p1_path, "other", "fixer-codex", p1_bytes, T_ATTESTATION),
        _file_entry(trace_path, "other", "coordinator", trace_bytes, T_TRACE),
        _file_entry(outcome_path, "readiness", "t-final", outcome_bytes, T_READINESS),
        _file_entry(readme_path, "other", "human", readme_bytes, T_README),
    ]

    manifest = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "mission": MISSION,
        "coordinator": "example-coordinator",
        "base_branch": "roadmap/post-substrate-impl",
        "created_utc": T_CREATED,
        "files": file_entries,
        "notes": "Canonical example fixture — exercises every validator in validate-all.sh.",
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    manifest_path = FIXTURE_DIR / "manifest.json"
    _write(manifest_path, manifest_bytes, T_CREATED)


if __name__ == "__main__":
    build_fixture()
    print(f"wrote fixture to {FIXTURE_DIR}")
