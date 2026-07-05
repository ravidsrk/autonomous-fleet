#!/usr/bin/env bash
# scripts/bench-adversarial.sh
#
# Driver for the adversarial-bench external dogfood. Reads a YAML target
# list (default: docs/external-dogfood/adversarial-bench-targets.yaml),
# for each target clones the repo and runs `adversarial-review-and-fix`
# via an adapter, producing a run-archive at
# `<clone>/.fleet/runs/<run_id>/`.
#
# Two modes per target (the falsifiable comparator from plan §3 Commit C):
#   --substrate on    Layer 1/2/3/4 all active
#   --substrate off   Substrate disabled via FLEET_DISABLE_* env vars
# The delta between the two modes IS the value the substrate must defend.
#
# Lineage: docs/plans/way-ahead-2026-06-23.md §3 Commit C.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

usage() {
  cat <<'USAGE'
Usage: bench-adversarial.sh [options]

Options:
  --targets <file>        YAML target list. Default:
                          docs/external-dogfood/adversarial-bench-targets.yaml
  --target <name>         Run a single named target (else all).
  --adapter <name>        Adapter to drive the mission (default: grok).
                          Must match a skills/autonomous-fleet-adapter-* dir.
  --substrate {on|off}    Substrate mode. Required when not --both.
  --both                  Run each target twice (off, then on). Default if
                          --substrate not provided.
  --runs-root <path>      Archive root hint (archives land under each clone's
                          .fleet/runs/). Default: .fleet/runs/
  --scratch <path>        Where to clone bench repos. Default: /tmp/fleet-bench/
  --max-turns N           Turn budget per mission (default: 80).
  --timeout SECONDS       Kill runtime after SECONDS (default: 5400; 0 disables).
  --handoff PATH          Handoff prompt file (default: docs/handoff-adversarial-bench.md).
  --skip-install          Skip fleet skill install into the cloned target.
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
ADAPTER="grok"
SUBSTRATE=""
BOTH=0
RUNS_ROOT=".fleet/runs"
SCRATCH="/tmp/fleet-bench"
DRY_RUN=0
MAX_TURNS=80
TIMEOUT_SECS=5400
HANDOFF="docs/handoff-adversarial-bench.md"
SKIP_INSTALL=0
SUMMARY_FILE="/tmp/bench-run-summary.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --targets)    TARGETS_FILE="$2"; shift 2 ;;
    --target)     TARGET_NAME="$2"; shift 2 ;;
    --adapter)    ADAPTER="$2"; shift 2 ;;
    --substrate)  SUBSTRATE="$2"; shift 2 ;;
    --both)       BOTH=1; shift ;;
    --runs-root)  RUNS_ROOT="$2"; shift 2 ;;
    --scratch)    SCRATCH="$2"; shift 2 ;;
    --max-turns)  MAX_TURNS="$2"; shift 2 ;;
    --timeout)    TIMEOUT_SECS="$2"; shift 2 ;;
    --handoff)    HANDOFF="$2"; shift 2 ;;
    --skip-install) SKIP_INSTALL=1; shift ;;
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

runtime_for_adapter() {
  case "$1" in
    grok|claude|codex) echo "$1" ;;
    claude-code) echo "claude" ;;
    autonomous-fleet-adapter-grok) echo "grok" ;;
    autonomous-fleet-adapter-claude-code) echo "claude" ;;
    autonomous-fleet-adapter-codex) echo "codex" ;;
    *)
      echo "bench-adversarial: unknown adapter '$1' (use grok, claude-code, or codex)" >&2
      exit 2
      ;;
  esac
}

RUNTIME="$(runtime_for_adapter "$ADAPTER")"

# Parse the targets YAML with python (no yq dep).
TARGETS_JSON=$("$VENV_PYTHON" -c "
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

archive_score() {
  local entry="$1"
  local score=0
  [[ -f "$entry/p0-review-findings.json" ]] && score=$((score + 100))
  [[ -f "$entry/p0-skeptic-findings.json" ]] && score=$((score + 50))
  [[ -f "$entry/fleet-outcome.yaml" || -f "$entry/arch-build-readiness.md" ]] && score=$((score + 25))
  [[ -f "$entry/manifest.json" ]] && score=$((score + 10))
  [[ -f "$entry/trace.jsonl" ]] && score=$((score + 5))
  [[ -f "$entry/headless-dryrun-progress.md" ]] && score=$((score - 40))
  echo "$score"
}

latest_archive_in() {
  local runs_dir="$1"
  [[ -d "$runs_dir" ]] || return 1
  local best=""
  local best_score=-1
  local entry score
  for entry in "$runs_dir"/*; do
    [[ -d "$entry" ]] || continue
    [[ -f "$entry/manifest.json" || -f "$entry/trace.jsonl" ]] || continue
    score="$(archive_score "$entry")"
    if [[ "$score" -gt "$best_score" || ( "$score" -eq "$best_score" && ( -z "$best" || "$entry" -nt "$best" ) ) ]]; then
      best="$entry"
      best_score="$score"
    fi
  done
  [[ -n "$best" ]] && echo "$best"
}

record_run_summary() {
  local target="$1"
  local mode="$2"
  local archive="$3"
  local validate_rc="$4"
  local blind_fix_rc="${5:-0}"
  "$VENV_PYTHON" -c "
import json, sys
from pathlib import Path
summary_path = Path(sys.argv[1])
target, mode, archive, validate_rc, blind_fix_rc = sys.argv[2:7]
row = {
    'target': target,
    'substrate_mode': mode,
    'archive': archive,
    'validate_rc': int(validate_rc),
    'blind_fix_rc': int(blind_fix_rc),
}
rows = []
if summary_path.is_file():
    try:
        rows = json.loads(summary_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        rows = []
rows.append(row)
summary_path.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
" "$SUMMARY_FILE" "$target" "$mode" "$archive" "$validate_rc" "$blind_fix_rc"
}

post_run_validate() {
  local name="$1"
  local mode="$2"
  local archive="$3"
  local validate_rc=0
  local blind_fix_rc=0

  echo "  post-run validate: $archive"
  "$VENV_PYTHON" "$ROOT/scripts/validate_run_archive.py" "$archive" || validate_rc=$?
  if [[ "$validate_rc" -ne 0 ]]; then
    echo "  warning: validate_run_archive.py failed (rc=$validate_rc)" >&2
  fi
  if [[ "$mode" == "on" ]]; then
    "$VENV_PYTHON" "$ROOT/scripts/verify_blind_fix.py" "$archive" || blind_fix_rc=$?
    if [[ "$blind_fix_rc" -ne 0 ]]; then
      echo "  warning: verify_blind_fix.py failed (rc=$blind_fix_rc)" >&2
    fi
  fi
  "$VENV_PYTHON" -c "
import json, sys
sys.path.insert(0, '$ROOT/scripts')
from lib.analyze_seat import analyze_run
from pathlib import Path
print(json.dumps(analyze_run(Path('$archive')), indent=2))
"
  record_run_summary "$name" "$mode" "$archive" "$validate_rc" "$blind_fix_rc"
}

adapter_skill_name() {
  case "$ADAPTER" in
    grok) echo "autonomous-fleet-adapter-grok" ;;
    claude|claude-code) echo "autonomous-fleet-adapter-claude-code" ;;
    codex) echo "autonomous-fleet-adapter-codex" ;;
    autonomous-fleet-adapter-*) echo "$ADAPTER" ;;
    *) echo "autonomous-fleet-adapter-grok" ;;
  esac
}

install_bench_skills() {
  local clone_dir="$1"
  local adapter_skill
  adapter_skill="$(adapter_skill_name)"
  echo "  installing fleet skills into $clone_dir (adapter=$adapter_skill)"
  (
    cd "$clone_dir"
    "$ROOT/scripts/install-skills.sh" \
      adversarial-review-and-fix \
      autonomous-fleet-core \
      "$adapter_skill"
  )
}

run_one_mode() {
  local name="$1"; local clone_url="$2"; local mode="$3"
  local slug="${name//\//-}"
  local archive_id
  archive_id=$(date -u +%Y%m%dT%H%M%SZ)
  local expected_label="${slug}-${mode}-${archive_id}"

  echo "=== bench: $name ($mode) → $expected_label ==="
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "  [dry-run] would clone $clone_url into $SCRATCH/$slug and dispatch $RUNTIME ($ADAPTER)"
    echo "  [dry-run] would run: $ROOT/scripts/run-mission-headless.sh $RUNTIME adversarial-review-and-fix \\"
    echo "    --repo $SCRATCH/$slug --max-turns $MAX_TURNS --timeout $TIMEOUT_SECS \\"
    echo "    --handoff $HANDOFF --yolo --yolo-untrusted-acknowledged"
    return 0
  fi

  local clone_dir="$SCRATCH/$slug"
  if [[ ! -d "$clone_dir/.git" ]]; then
    git clone --depth 50 "$clone_url" "$clone_dir"
  else
    (cd "$clone_dir" && git fetch --depth 50 origin && git reset --hard origin/HEAD)
  fi

  if [[ $SKIP_INSTALL -eq 0 ]]; then
    install_bench_skills "$clone_dir"
  fi

  local runs_before_id=""
  local runs_dir="$clone_dir/.fleet/runs"
  mkdir -p "$runs_dir"
  if [[ -n "$(latest_archive_in "$runs_dir" || true)" ]]; then
    local before_archive
    before_archive="$(latest_archive_in "$runs_dir")"
    runs_before_id="$(basename "$before_archive")"
  fi

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

  echo "  dispatching $RUNTIME on $clone_dir (mode=$mode)"
  echo "  env: $env_label"

  local dispatch_rc=0
  set +e
  "$ROOT/scripts/run-mission-headless.sh" "$RUNTIME" adversarial-review-and-fix \
    --repo "$clone_dir" \
    --max-turns "$MAX_TURNS" \
    --timeout "$TIMEOUT_SECS" \
    --handoff "$HANDOFF" \
    --yolo \
    --yolo-untrusted-acknowledged
  dispatch_rc=$?
  set -e
  if [[ "$dispatch_rc" -ne 0 ]]; then
    echo "  warning: run-mission-headless exited $dispatch_rc (archive may still exist)" >&2
  fi

  local archive=""
  archive="$(latest_archive_in "$runs_dir" || true)"
  if [[ -z "$archive" ]]; then
    echo "  error: no archive under $runs_dir" >&2
    record_run_summary "$name" "$mode" "" 1 1
    return 1
  fi
  if [[ -n "$runs_before_id" && "$(basename "$archive")" == "$runs_before_id" ]]; then
    # Prefer any non-dryrun archive with mission findings (not the prior run id).
    local candidate candidate_path
    shopt -s nullglob
    for candidate_path in "$runs_dir"/*/; do
      candidate="$(basename "$candidate_path")"
      [[ "$candidate" == "$runs_before_id" ]] && continue
      if [[ -f "$candidate_path/p0-review-findings.json" ]]; then
        archive="${candidate_path%/}"
        break
      fi
    done
    shopt -u nullglob
    if [[ "$(basename "$archive")" == "$runs_before_id" ]]; then
      echo "  error: no new mission archive under $runs_dir (only dryrun trace?)" >&2
      record_run_summary "$name" "$mode" "" 1 1
      return 1
    fi
  fi

  echo "  archive: $archive"
  post_run_validate "$name" "$mode" "$archive"
}

echo "[]" > "$SUMMARY_FILE"

while IFS= read -r target_json; do
  name=$(echo "$target_json" | "$VENV_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["name"])')
  clone_url=$(echo "$target_json" | "$VENV_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["clone_url"])')

  if [[ $BOTH -eq 1 ]]; then
    run_one_mode "$name" "$clone_url" "off"
    # Fresh checkout for substrate-on so both modes start from the same baseline.
    reset_slug="${name//\//-}"
    reset_clone_dir="$SCRATCH/$reset_slug"
    if [[ $DRY_RUN -eq 0 && -d "$reset_clone_dir/.git" ]]; then
      echo "bench: resetting $reset_clone_dir to origin/HEAD before substrate-on"
      (cd "$reset_clone_dir" && git fetch --depth 50 origin && git reset --hard origin/HEAD && git clean -fdx -e .agents -e .fleet)
    fi
    run_one_mode "$name" "$clone_url" "on"
  else
    run_one_mode "$name" "$clone_url" "$SUBSTRATE"
  fi
done < <(echo "$TARGETS_JSON" | "$VENV_PYTHON" -c '
import json, sys
for t in json.load(sys.stdin):
    print(json.dumps(t))
')

if [[ $DRY_RUN -eq 1 ]]; then
  echo "bench-adversarial: dry-run complete."
else
  echo "bench-adversarial: runs complete. Summary: $SUMMARY_FILE"
  if [[ -f "$SUMMARY_FILE" ]]; then
    cat "$SUMMARY_FILE"
  fi
  archives=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && archives+=("$line")
  done < <("$VENV_PYTHON" -c "
import json
from pathlib import Path
rows = json.loads(Path('$SUMMARY_FILE').read_text(encoding='utf-8'))
for r in rows:
    if r.get('archive'):
        print(r['archive'])
" 2>/dev/null || true)
  if [[ ${#archives[@]} -gt 0 ]]; then
    echo ""
    echo "== aggregate seat analysis =="
    "$VENV_PYTHON" -c "
import json, sys
sys.path.insert(0, '$ROOT/scripts')
from lib.analyze_seat import aggregate, analyze_run
from pathlib import Path
archives = sys.argv[1:]
rows = [analyze_run(Path(a)) for a in archives if a]
print(json.dumps(aggregate(rows), indent=2))
" "${archives[@]}" || true
  fi
fi