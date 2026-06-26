#!/usr/bin/env bash
# Validate a real adversarial-review-and-fix run archive (Lane 1 gate).
# Usage: ./scripts/validate-first-substrate-archive.sh <run_id>
#    or: ./scripts/validate-first-substrate-archive.sh .fleet/runs/<run_id>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

RUN_ID="${1:-}"
if [[ -z "$RUN_ID" ]]; then
  echo "usage: validate-first-substrate-archive.sh <run_id-or-archive-path>" >&2
  exit 2
fi

if [[ -d "$RUN_ID" ]]; then
  ARCHIVE="$(cd "$RUN_ID" && pwd)"
else
  ARCHIVE="$ROOT/.fleet/runs/$RUN_ID"
fi

if [[ ! -d "$ARCHIVE" ]]; then
  echo "validate-first-substrate-archive: archive not found: $ARCHIVE" >&2
  exit 1
fi

echo "== validate-first-substrate-archive: $ARCHIVE =="

echo "  Layer 4: validate_run_archive"
"$VENV_PYTHON" "$ROOT/scripts/validate_run_archive.py" "$ARCHIVE" --quiet

echo "  Layer 1: verify_findings"
if [[ -f "$ARCHIVE/p0-review-findings.json" ]]; then
  "$VENV_PYTHON" "$ROOT/scripts/verify_findings.py" \
    "$ARCHIVE/p0-review-findings.json" --repo "$ROOT" \
    --summary-out "$ARCHIVE/p0-verify-summary.json"
else
  echo "validate-first-substrate-archive: missing p0-review-findings.json" >&2
  exit 1
fi

echo "  Layer 3: verify_blind_fix"
"$VENV_PYTHON" "$ROOT/scripts/verify_blind_fix.py" "$ARCHIVE"

echo "  Trace: emit_trace validate"
if [[ -f "$ARCHIVE/trace.jsonl" ]]; then
  "$VENV_PYTHON" "$ROOT/scripts/emit_trace.py" validate "$ARCHIVE/trace.jsonl"
else
  echo "validate-first-substrate-archive: missing trace.jsonl" >&2
  exit 1
fi

echo "  Manifest cross-check (fleet_run)"
"$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '$ROOT/scripts')
from pathlib import Path
from lib.fleet_run import load_and_validate_manifest
_, errs = load_and_validate_manifest(Path('$ARCHIVE'))
if errs:
    for e in errs:
        print(e, file=sys.stderr)
    sys.exit(1)
"

echo "  analyze_seat rollup"
"$VENV_PYTHON" "$ROOT/scripts/analyze_seat.py" "$ARCHIVE" 2>/dev/null || true

echo "validate-first-substrate-archive: all checks passed for $(basename "$ARCHIVE")"