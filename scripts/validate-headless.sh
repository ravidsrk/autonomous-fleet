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

echo "validate-headless: all mechanical checks passed"