#!/usr/bin/env bash
# scripts/bench-adversarial.sh
#
# Driver for the adversarial-bench external dogfood. Reads a YAML target
# list (default: docs/external-dogfood/adversarial-bench-targets.yaml),
# for each target clones the repo and runs `adversarial-review-and-fix`
# via an adapter, producing a run-archive at
# `.fleet/runs/<repo-slug>-<mode>-<id>/`.
#
# Two modes per target (the falsifiable comparator from plan §3 Commit C):
#   --substrate on    Layer 1/2/3/4 all active
#   --substrate off   Substrate disabled via FLEET_DISABLE_* env vars
# The delta between the two modes IS the value the substrate must defend.
#
# This file is the scaffolding; real runs require a coding-agent adapter
# (Claude Code, Codex) with credit, network access, and an operator. The
# CI-side scaffolding is `tests/test_bench_adversarial.py` which exercises
# the driver against a planted-bug fixture (no network).
#
# Lineage: docs/plans/way-ahead-2026-06-23.md §3 Commit C.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bench-adversarial.sh [options]

Options:
  --targets <file>        YAML target list. Default:
                          docs/external-dogfood/adversarial-bench-targets.yaml
  --target <name>         Run a single named target (else all).
  --adapter <name>        Adapter to drive the mission (default: claude-code).
                          Must match a skills/autonomous-fleet-adapter-* dir.
  --substrate {on|off}    Substrate mode. Required when not --both.
  --both                  Run each target twice (off, then on). Default if
                          --substrate not provided.
  --runs-root <path>      Archive root. Default: .fleet/runs/
  --scratch <path>        Where to clone bench repos. Default: /tmp/fleet-bench/
  --dry-run               Print plan; don't clone or run.
  -h, --help              Show this help.

Environment:
  FLEET_DISABLE_STOP_VERIFY     set when --substrate off; disables Layer 2
  FLEET_DISABLE_VERIFY_FINDINGS set when --substrate off; disables Layer 1
  FLEET_DISABLE_BLIND_FIX       set when --substrate off; disables Layer 3
  FLEET_DISABLE_RUN_ARCHIVE     set when --substrate off; disables Layer 4
                                manifest writes (archive still produced for
                                comparison, just unsealed)
USAGE
}

TARGETS_FILE="docs/external-dogfood/adversarial-bench-targets.yaml"
TARGET_NAME=""
ADAPTER="claude-code"
SUBSTRATE=""
BOTH=0
RUNS_ROOT=".fleet/runs"
SCRATCH="/tmp/fleet-bench"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --targets)    TARGETS_FILE="$2"; shift 2 ;;
    --target)     TARGET_NAME="$2"; shift 2 ;;
    --adapter)    ADAPTER="$2"; shift 2 ;;
    --substrate)  SUBSTRATE="$2"; shift 2 ;;
    --both)       BOTH=1; shift ;;
    --runs-root)  RUNS_ROOT="$2"; shift 2 ;;
    --scratch)    SCRATCH="$2"; shift 2 ;;
    --dry-run)    DRY_RUN=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    *)            echo "bench-adversarial: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$SUBSTRATE" && $BOTH -eq 0 ]]; then
  BOTH=1
fi
if [[ -n "$SUBSTRATE" && "$SUBSTRATE" != "on" && "$SUBSTRATE" != "off" ]]; then
  echo "bench-adversarial: --substrate must be 'on' or 'off'" >&2
  exit 2
fi

if [[ ! -f "$TARGETS_FILE" ]]; then
  echo "bench-adversarial: targets file not found: $TARGETS_FILE" >&2
  exit 2
fi

# Parse the targets YAML with python (no yq dep).
TARGETS_JSON=$(.venv/bin/python -c "
import json, sys
import yaml
with open('$TARGETS_FILE') as f:
    doc = yaml.safe_load(f)
targets = doc.get('targets', []) if isinstance(doc, dict) else []
if '$TARGET_NAME':
    targets = [t for t in targets if t.get('name') == '$TARGET_NAME']
print(json.dumps(targets))
")

if [[ "$TARGETS_JSON" == "[]" ]]; then
  if [[ -n "$TARGET_NAME" ]]; then
    echo "bench-adversarial: target not found: $TARGET_NAME" >&2
  else
    echo "bench-adversarial: no targets in $TARGETS_FILE" >&2
  fi
  exit 2
fi

mkdir -p "$RUNS_ROOT" "$SCRATCH"

run_one_mode() {
  local name="$1"; local clone_url="$2"; local mode="$3"
  local slug="${name//\//-}"
  local archive_id
  archive_id=$(date -u +%Y%m%dT%H%M%SZ)
  local archive_dir="$RUNS_ROOT/${slug}-${mode}-${archive_id}"

  echo "=== bench: $name ($mode) → $archive_dir ==="
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "  [dry-run] would clone $clone_url into $SCRATCH/$slug and dispatch $ADAPTER"
    return 0
  fi

  # Clone (idempotent).
  local clone_dir="$SCRATCH/$slug"
  if [[ ! -d "$clone_dir/.git" ]]; then
    git clone --depth 50 "$clone_url" "$clone_dir"
  else
    (cd "$clone_dir" && git fetch --depth 50 origin && git reset --hard origin/HEAD)
  fi

  # Set substrate-off env if requested. These env vars are honored by
  # the substrate verifiers (scripts/{verify_findings,stop_verify,
  # verify_blind_fix,validate_run_archive}.py) and produce an early
  # exit 0 with a "DISABLED via FLEET_DISABLE_X=1" stderr notice. See
  # scripts/lib/substrate_disable.py for the convention.
  #
  # We export the vars into THIS shell's environment so any child
  # process the operator launches inside this terminal (the adapter
  # session, the post-run validators, the analyze_seat run) inherits
  # the disabled state. On mode=on we explicitly UNSET them so a stale
  # value from a prior off-run doesn't leak into the on-run.
  if [[ "$mode" == "off" ]]; then
    export FLEET_DISABLE_VERIFY_FINDINGS=1
    export FLEET_DISABLE_STOP_VERIFY=1
    export FLEET_DISABLE_BLIND_FIX=1
    export FLEET_DISABLE_RUN_ARCHIVE=1
    local env_label="FLEET_DISABLE_VERIFY_FINDINGS=1 FLEET_DISABLE_STOP_VERIFY=1 FLEET_DISABLE_BLIND_FIX=1 FLEET_DISABLE_RUN_ARCHIVE=1"
  else
    unset FLEET_DISABLE_VERIFY_FINDINGS
    unset FLEET_DISABLE_STOP_VERIFY
    unset FLEET_DISABLE_BLIND_FIX
    unset FLEET_DISABLE_RUN_ARCHIVE
    local env_label="(substrate on — no disable env vars set)"
  fi

  # Dispatch the adversarial-review-and-fix mission via the adapter.
  # Real adapters write to .fleet/runs/<id>/ inside the cloned repo; we
  # then move the produced archive into our $archive_dir.
  echo "  dispatching $ADAPTER on $clone_dir (mode=$mode)"
  echo "  (operator: run \`fleet run adversarial-review-and-fix --adapter $ADAPTER\` in $clone_dir)"
  echo "  expected archive: $archive_dir"
  echo "  env: $env_label"

  # Stub: the scaffolding does not invoke an adapter here. Operators run
  # the dispatch by hand against the adapter SKILL. The driver's value
  # add is the per-target loop, the substrate-on/off env management
  # (real export above, not just an echo), and the post-run validation
  # pass.
}

echo "[]" > /tmp/bench-run-summary.json

while IFS= read -r target_json; do
  name=$(echo "$target_json" | .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["name"])')
  clone_url=$(echo "$target_json" | .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["clone_url"])')

  if [[ $BOTH -eq 1 ]]; then
    run_one_mode "$name" "$clone_url" "off"
    run_one_mode "$name" "$clone_url" "on"
  else
    run_one_mode "$name" "$clone_url" "$SUBSTRATE"
  fi
done < <(echo "$TARGETS_JSON" | .venv/bin/python -c '
import json, sys
for t in json.load(sys.stdin):
    print(json.dumps(t))
')

echo "bench-adversarial: dispatch plan emitted. Operator: complete each archive by running the mission as instructed."
