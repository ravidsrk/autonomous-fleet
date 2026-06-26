#!/usr/bin/env bash
# Mechanical headless-path validation — no runtime CLI auth required.
# Exercises campaign dry-runs and run-mission-headless.sh --dry-run for every
# shipped mission × supported runtime. Live agent invocation still needs
# runtime auth (grok login, etc.); this gate proves the wiring only.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ACTIVE_PRESETS=(repo-health ship-with-proof quality-gate)
SHIPPED_MISSIONS=(doc-sync test-coverage adversarial-review-and-fix)
RUNTIMES=(grok claude codex)

echo "== validate-headless: campaign presets (grok dry-run) =="
for preset in "${ACTIVE_PRESETS[@]}"; do
  echo "  preset: $preset"
  ./scripts/run-campaign.sh grok --preset "$preset" --dry-run >/dev/null
done

echo "== validate-headless: runtime guard =="
if ./scripts/run-campaign.sh banana --preset repo-health --dry-run >/dev/null 2>&1; then
  echo "validate-headless: expected banana runtime to be rejected" >&2
  exit 1
fi

echo "== validate-headless: mission headless dry-run =="
for mission in "${SHIPPED_MISSIONS[@]}"; do
  for runtime in "${RUNTIMES[@]}"; do
    echo "  $runtime $mission"
    ./scripts/run-mission-headless.sh "$runtime" "$mission" --dry-run >/dev/null
  done
done

echo "== validate-headless: trace emission (lib + shell entry points) =="
# 1) Direct lib CLI (validates before run-mission-headless cleanup)
EMIT_OUT="$("$ROOT/.venv/bin/python" "$ROOT/scripts/emit_headless_dryrun_trace.py" \
  --mission doc-sync --repo "$ROOT" --runtime grok --fleet-root "$ROOT" 2>&1)"
echo "$EMIT_OUT" | grep -q "primitives (11):" || {
  echo "validate-headless: expected 11 primitives from emit_headless_dryrun_trace" >&2
  echo "$EMIT_OUT" >&2
  exit 1
}
RUN_ID="$(echo "$EMIT_OUT" | sed -n 's/^  run_id: //p' | head -1)"
ARCHIVE="$ROOT/.fleet/runs/$RUN_ID"
"$ROOT/.venv/bin/python" "$ROOT/scripts/emit_trace.py" validate "$ARCHIVE/trace.jsonl"
"$ROOT/.venv/bin/python" -c "import sys; sys.path.insert(0, '$ROOT/scripts'); from lib.fleet_run import load_and_validate_manifest; from pathlib import Path; _, errs = load_and_validate_manifest(Path('$ARCHIVE')); sys.exit(1 if errs else 0)"
rm -rf "$ARCHIVE"
# 2) Shell entry point invokes emitter then cleans up (no archive left behind)
HEADLESS_OUT="$("$ROOT/scripts/run-mission-headless.sh" grok doc-sync --dry-run --repo "$ROOT" 2>&1)"
echo "$HEADLESS_OUT" | grep -q "primitives (11):" || {
  echo "validate-headless: run-mission-headless --dry-run must emit 11 primitives" >&2
  echo "$HEADLESS_OUT" >&2
  exit 1
}

echo "validate-headless: all mechanical checks passed"