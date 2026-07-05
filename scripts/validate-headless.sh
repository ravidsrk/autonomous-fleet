#!/usr/bin/env bash
# Mechanical headless-path validation — no runtime CLI auth required.
# Exercises campaign dry-runs and run-mission-headless.sh --dry-run for every
# shipped mission × supported runtime. Live agent invocation still needs
# runtime auth (grok login, etc.); this gate proves the wiring only.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ACTIVE_PRESETS=(repo-health ship-with-proof quality-gate audit-gated)
# audit-gated ships a LIVE conditional edge (`if: findings_open == 0` / `> 0`), so it is the
# only preset whose failure/blocked branch is reachable. Probe it twice: the benign all-zero
# pass exercises the clean branch, and --probe-fail forces failure-shaped metrics so the
# blocked branch is reachability-checked too (finding 56). The `if: always` presets only have
# one branch, so the benign pass is sufficient for them.
GATED_PRESETS=(audit-gated)
SHIPPED_MISSIONS=(doc-sync test-coverage adversarial-review-and-fix)
RUNTIMES=(grok claude codex)

echo "== validate-headless: campaign presets (grok dry-run) =="
for preset in "${ACTIVE_PRESETS[@]}"; do
  echo "  preset: $preset"
  ./scripts/run-campaign.sh grok --preset "$preset" --dry-run >/dev/null
done

echo "== validate-headless: conditional-gate failure branch (--probe-fail) =="
for preset in "${GATED_PRESETS[@]}"; do
  echo "  preset: $preset (probe-fail)"
  PROBE_OUT="$(./scripts/run-campaign.sh grok --preset "$preset" --dry-run --probe-fail 2>&1)"
  # The failure branch must route somewhere OTHER than the benign target, proving the
  # `findings_open > 0` edge is statically reachable (not a dead branch).
  echo "$PROBE_OUT" | grep -q "node=remediate" || {
    echo "validate-headless: --probe-fail did not reach the gated failure branch for $preset" >&2
    echo "$PROBE_OUT" >&2
    exit 1
  }
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

echo "== validate-headless: community preflight hints (isolated probe home) =="
COMMUNITY_PROBE_HOME="$(mktemp -d "${TMPDIR:-/tmp}/fleet-community-probe-XXXXXX")"
cleanup_probe_home() {
  if [[ -n "${COMMUNITY_PROBE_HOME:-}" && -d "$COMMUNITY_PROBE_HOME" ]]; then
    rm -rf "$COMMUNITY_PROBE_HOME"
  fi
}
trap cleanup_probe_home EXIT
export COMMUNITY_PROBE_HOME

COMMUNITY_OUT="$(./scripts/preflight-community.sh browser-qa-fix --dry-run 2>&1)"
echo "$COMMUNITY_OUT"
echo "$COMMUNITY_OUT" | grep -q "recommended community bundle" || {
  echo "validate-headless: preflight-community must print recommended bundle" >&2
  exit 1
}
echo "$COMMUNITY_OUT" | grep -q "install-community.sh" || {
  echo "validate-headless: preflight-community must print install-community hint" >&2
  exit 1
}
echo "$COMMUNITY_OUT" | grep -q "^WARN" || {
  echo "validate-headless: preflight-community must WARN when skills missing under isolated home" >&2
  exit 1
}

echo "  gstack mission: browser-qa-fix (community hints)"
GSTACK_HEADLESS_OUT="$(./scripts/run-mission-headless.sh grok browser-qa-fix --dry-run --repo "$ROOT" 2>&1)"
echo "$GSTACK_HEADLESS_OUT"
echo "$GSTACK_HEADLESS_OUT" | grep -q "install-community.sh" || {
  echo "validate-headless: gstack mission dry-run must surface install-community hint" >&2
  exit 1
}
cleanup_probe_home
trap - EXIT
unset COMMUNITY_PROBE_HOME

echo "== validate-headless: trace emission (lib + shell entry points) =="
ARCHIVE=""
cleanup_archive() {
  if [[ -n "${ARCHIVE:-}" && -d "$ARCHIVE" ]]; then
    rm -rf "$ARCHIVE"
  fi
}
trap cleanup_archive EXIT

# 1) Direct lib CLI (validates before run-mission-headless cleanup)
EMIT_OUT="$("$ROOT/.venv/bin/python" "$ROOT/scripts/emit_headless_dryrun_trace.py" \
  --mission doc-sync --repo "$ROOT" --runtime grok --fleet-root "$ROOT" 2>&1)"
echo "$EMIT_OUT" | grep -q "primitives (11):" || {
  echo "validate-headless: expected 11 primitives from emit_headless_dryrun_trace" >&2
  echo "$EMIT_OUT" >&2
  exit 1
}
ARCHIVE="$(echo "$EMIT_OUT" | sed -n 's/^emit_headless_dryrun_trace: archive=//p' | head -1)"
if [[ -z "$ARCHIVE" || ! -d "$ARCHIVE" ]]; then
  echo "validate-headless: could not resolve archive path from emit output" >&2
  echo "$EMIT_OUT" >&2
  exit 1
fi
if ! "$ROOT/.venv/bin/python" "$ROOT/scripts/emit_trace.py" validate "$ARCHIVE/trace.jsonl"; then
  exit 1
fi
if ! "$ROOT/.venv/bin/python" "$ROOT/scripts/validate_run_archive.py" "$ARCHIVE" --quiet; then
  exit 1
fi
ARCHIVE=""
trap - EXIT

# 2) Shell entry point invokes emitter then cleans up (no archive left behind)
HEADLESS_OUT="$("$ROOT/scripts/run-mission-headless.sh" grok doc-sync --dry-run --repo "$ROOT" 2>&1)"
echo "$HEADLESS_OUT" | grep -q "primitives (11):" || {
  echo "validate-headless: run-mission-headless --dry-run must emit 11 primitives" >&2
  echo "$HEADLESS_OUT" >&2
  exit 1
}

echo "validate-headless: all mechanical checks passed"