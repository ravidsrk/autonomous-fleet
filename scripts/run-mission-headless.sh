#!/usr/bin/env bash
# Unattended mission or campaign run via headless agent + goal condition.
#
# Usage:
#   ./scripts/run-mission-headless.sh grok doc-sync [--max-turns 50] [--handoff docs/handoff.md]
#   ./scripts/run-mission-headless.sh claude fleet-program --max-turns 80
#   ./scripts/run-mission-headless.sh codex test-coverage --max-turns 60
#
# Requires: grok or claude CLI on PATH; git repo with autonomous-fleet skills installed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUNTIME="${1:-}"
MISSION="${2:-}"
MAX_TURNS=50
HANDOFF=""
YOLO=1

usage() {
  cat <<'EOF'
Usage: run-mission-headless.sh <grok|claude|codex> <mission-or-fleet-program> [options]

Options:
  --max-turns N     Agent turn budget (default: 50)
  --handoff PATH    Prompt file (default: generated minimal handoff)
  --no-yolo         Do not auto-approve tools (Grok only: omit --yolo)

Examples:
  ./scripts/run-mission-headless.sh grok doc-sync --max-turns 50
  ./scripts/run-mission-headless.sh claude fleet-program --max-turns 80
EOF
}

if [[ -z "$RUNTIME" || -z "$MISSION" ]]; then
  usage
  exit 1
fi

shift 2 || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-turns)
      MAX_TURNS="${2:?}"
      shift 2
      ;;
    --handoff)
      HANDOFF="${2:?}"
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

if [[ -n "$HANDOFF" && -f "$HANDOFF" ]]; then
  PROMPT="$(cat "$HANDOFF")"
else
  if [[ "$MISSION" == "fleet-program" ]]; then
    GOAL_COND="Campaign DONE: docs/fleet-program-progress.md PHASE is DONE, every node DONE or SKIPPED, each readiness doc has valid fleet-outcome YAML."
    PROMPT="Activate fleet-program, autonomous-fleet-core, and the installed runtime adapter. Run the repo-health campaign (or campaign in docs/fleet-program-progress.md if present). /goal ${GOAL_COND}"
  else
    VENV_PY="$ROOT/.venv/bin/python"
    [[ -x "$VENV_PY" ]] || VENV_PY=python3
    PROGRESS="$("$VENV_PY" -c "import sys; sys.path.insert(0,'$ROOT/scripts'); from lib.mission_registry import progress_path; print(progress_path('$MISSION'))")"
    READINESS="$("$VENV_PY" -c "import sys; sys.path.insert(0,'$ROOT/scripts'); from lib.mission_registry import readiness_path; print(readiness_path('$MISSION'))")"
    GOAL_COND="Mission ${MISSION} DONE: ${PROGRESS} all task flags true, ${READINESS} with fleet-outcome.status done, all PRs merged into BASE."
    PROMPT="Activate mission skill ${MISSION}, autonomous-fleet-core, and the installed runtime adapter. Follow engine.md and runtime-goals.md. /goal ${GOAL_COND}"
  fi
fi

echo "== run-mission-headless =="
echo "runtime:  $RUNTIME"
echo "mission:  $MISSION"
echo "turns:    $MAX_TURNS"
echo ""

case "$RUNTIME" in
  grok)
    CMD=(grok -p "$PROMPT" --max-turns "$MAX_TURNS" --output-format json --cwd "$ROOT")
    [[ "$YOLO" -eq 1 ]] && CMD+=(--yolo)
    "${CMD[@]}"
    ;;
  claude)
    # Claude /goal in non-interactive prompt (v2.1.139+)
    claude -p "$PROMPT" --cwd "$ROOT"
    ;;
  codex)
    # Codex: pass goal in thread prompt; non-interactive per local Codex CLI if available
    if command -v codex >/dev/null 2>&1; then
      codex -p "$PROMPT" 2>/dev/null || codex "$PROMPT"
    else
      echo "error: codex CLI not found on PATH; run interactively in Codex app with:" >&2
      echo "  /goal ${GOAL_COND:-<see prompt above>}" >&2
      exit 1
    fi
    ;;
  *)
    echo "error: unsupported runtime '$RUNTIME' (use grok, claude, or codex)" >&2
    exit 1
    ;;
esac