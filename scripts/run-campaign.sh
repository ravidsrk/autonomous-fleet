#!/usr/bin/env bash
# Mechanical campaign driver: validate outcomes between nodes, invoke headless missions.
#
# Usage:
#   ./scripts/run-campaign.sh grok --preset repo-health [--dry-run]
#   ./scripts/run-campaign.sh grok --campaign docs/composition-e2e-campaign.yaml
#   ./scripts/run-campaign.sh claude --preset repo-health --max-turns 60
#   ./scripts/run-campaign.sh grok --preset ship-with-proof --repo /tmp/gemoji
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUNTIME=""
CAMPAIGN_FILE=""
PRESET=""
REPO_ROOT=""
DRY_RUN=0
MAX_TURNS=50
YOLO=1

usage() {
  cat <<'EOF'
Usage: run-campaign.sh <grok|claude|codex> (--preset NAME | --campaign PATH) [options]

Options:
  --preset NAME       Built-in under scripts/campaigns/<NAME>.yaml
  --campaign PATH     Campaign YAML file
  --repo PATH         Target git repo for missions (default: autonomous-fleet clone)
  --dry-run           Print plan only; do not invoke agents
  --max-turns N       Per-node turn budget (default: 50)
  --no-yolo           Pass --no-yolo to run-mission-headless (Grok)
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

RUNTIME="$1"
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset)
      PRESET="${2:?}"
      shift 2
      ;;
    --campaign)
      CAMPAIGN_FILE="${2:?}"
      shift 2
      ;;
    --repo)
      REPO_ROOT="${2:?}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --max-turns)
      MAX_TURNS="${2:?}"
      shift 2
      ;;
    --no-yolo)
      YOLO=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -n "$PRESET" ]]; then
  CAMPAIGN_FILE="$ROOT/scripts/campaigns/${PRESET}.yaml"
fi

if [[ -z "$CAMPAIGN_FILE" || ! -f "$CAMPAIGN_FILE" ]]; then
  echo "error: campaign file not found (use --preset or --campaign)" >&2
  exit 1
fi

if [[ -n "$REPO_ROOT" ]]; then
  REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
else
  REPO_ROOT="$ROOT"
fi

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "error: --repo '$REPO_ROOT' is not a git repository" >&2
  exit 1
fi

VENV_PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  python3 -m venv "$ROOT/.venv"
  "$VENV_PYTHON" -m pip install -q pyyaml pytest
fi

CAMPAIGN_INFO="$("$VENV_PYTHON" - <<'PY' "$CAMPAIGN_FILE"
import sys, yaml
from pathlib import Path
data = yaml.safe_load(Path(sys.argv[1]).read_text())
print(data["start"])
for node, spec in data.get("nodes", {}).items():
    print(f"{node}\t{spec['mission']}")
PY
)"

START="$(echo "$CAMPAIGN_INFO" | head -1)"

mission_for_node() {
  local nid="$1"
  echo "$CAMPAIGN_INFO" | awk -F'\t' -v n="$nid" 'NF>=2 && $1==n {print $2; exit}'
}

echo "== run-campaign =="
echo "runtime:  $RUNTIME"
echo "repo:     $REPO_ROOT"
echo "campaign: $CAMPAIGN_FILE"
echo "start:    $START"
echo "dry-run:  $DRY_RUN"
echo ""

CURRENT="$START"
STEP=0
VISITED=""

while [[ -n "$CURRENT" ]]; do
  STEP=$((STEP + 1))
  MISSION="$(mission_for_node "$CURRENT")"
  if [[ -z "$MISSION" ]]; then
    echo "error: unknown node '$CURRENT'" >&2
    exit 1
  fi

  READINESS="$("$VENV_PYTHON" -c "import sys; sys.path.insert(0,'$ROOT/scripts'); from lib.mission_registry import readiness_path; print(readiness_path('$MISSION'))")"

  echo "--- step $STEP: node=$CURRENT mission=$MISSION ---"

  READINESS_ABS="$REPO_ROOT/$READINESS"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  would run: run-mission-headless.sh $RUNTIME $MISSION --repo $REPO_ROOT --max-turns $MAX_TURNS"
    echo "  expect:    $READINESS_ABS with fleet-outcome.status done"
  else
    EXTRA=(--repo "$REPO_ROOT")
    [[ "$YOLO" -eq 0 ]] && EXTRA+=(--no-yolo)
    "$ROOT/scripts/run-mission-headless.sh" "$RUNTIME" "$MISSION" --max-turns "$MAX_TURNS" "${EXTRA[@]}"
    if [[ -f "$READINESS_ABS" ]]; then
      ./scripts/validate-fleet-outcome.sh "$READINESS_ABS"
    else
      echo "warn: $READINESS_ABS not found after node $CURRENT" >&2
    fi
  fi

  VISITED="${VISITED:+$VISITED }$CURRENT"

  if [[ "$DRY_RUN" -eq 1 && ! -f "$READINESS_ABS" ]]; then
    echo "  next:     (dry-run stops — no readiness at $READINESS_ABS)"
    break
  fi

  if [[ "$DRY_RUN" -eq 0 && ! -f "$READINESS_ABS" ]]; then
    echo "error: cannot pick next node without $READINESS_ABS" >&2
    exit 1
  fi

  if [[ -f "$READINESS_ABS" ]]; then
    NEXT_JSON="$(./scripts/eval-campaign-edge.sh --readiness "$READINESS_ABS" --campaign "$CAMPAIGN_FILE" --current-node "$CURRENT")"
    NEXT="$(echo "$NEXT_JSON" | "$VENV_PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('next') or '')")"
    echo "  next:     ${NEXT:-<campaign done>}"
    CURRENT="$NEXT"
  else
    break
  fi

  if [[ "$STEP" -gt 20 ]]; then
    echo "error: campaign step limit exceeded (cycle?)" >&2
    exit 1
  fi
done

echo ""
echo "Campaign ${DRY_RUN:+dry-run }complete. Nodes visited: ${VISITED:-none}"