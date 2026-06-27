#!/usr/bin/env bash
# Non-busy WAIT helper for daemonless adapters (Grok, Codex).
# Poll a ledger file until a task row matches --expect or timeout.
#
# Usage:
#   ./scripts/poll-ledger.sh --ledger docs/foo-progress.md \
#     --task TASK-1 --expect 'MERGED=t' --timeout 3600 --interval 30
#
# Exit 0 when the pattern matches; 1 on timeout; 2 on usage error.
set -euo pipefail

LEDGER=""
TASK=""
EXPECT=""
TIMEOUT=3600
INTERVAL=30

usage() {
  cat <<'USAGE'
Usage: poll-ledger.sh --ledger <path> --task <id> --expect <regex> [options]

Options:
  --ledger <path>     Progress ledger (docs/<mission>-progress.md)
  --task <id>         Task row identifier to scope the search
  --expect <regex>    Extended-regex pattern that must match the task row
  --timeout <sec>     Max wait (default: 3600)
  --interval <sec>    Poll interval (default: 30)
  -h, --help          Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ledger)   LEDGER="$2"; shift 2 ;;
    --task)     TASK="$2"; shift 2 ;;
    --expect)   EXPECT="$2"; shift 2 ;;
    --timeout)  TIMEOUT="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *)          echo "poll-ledger: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$LEDGER" || -z "$TASK" || -z "$EXPECT" ]]; then
  echo "poll-ledger: --ledger, --task, and --expect are required" >&2
  usage >&2
  exit 2
fi
if [[ ! -f "$LEDGER" ]]; then
  echo "poll-ledger: ledger not found: $LEDGER" >&2
  exit 2
fi

deadline=$(( $(date +%s) + TIMEOUT ))
while [[ $(date +%s) -lt $deadline ]]; do
  row="$(awk -v task="$TASK" '
    $0 ~ task { found=1 }
    found { print; if ($0 ~ /^- / && $0 !~ task) exit }
  ' "$LEDGER" 2>/dev/null || true)"
  if echo "$row" | grep -Eq "$EXPECT"; then
    echo "poll-ledger: matched --expect on task $TASK in $LEDGER"
    exit 0
  fi
  sleep "$INTERVAL"
done

echo "poll-ledger: timeout after ${TIMEOUT}s waiting for $EXPECT on task $TASK" >&2
exit 1