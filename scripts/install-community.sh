#!/usr/bin/env bash
# Install documented community skill bundles (opt-in; no surprise execution without --execute).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: install-community.sh <bundle|gstack|agent-skills|mattpocock> [options]

Bundles (gstack subsets):
  gstack-browser    browse, qa, qa-only, health
  gstack-framing    office-hours, autoplan, plan-* reviews
  gstack-security   cso, investigate
  gstack-devex      plan-devex-review, devex-review
  gstack-ship       ship, review, document-release, health
  gstack            full gstack clone + ./setup

Other catalogs:
  agent-skills      Claude Code plugin marketplace install (documented commands)
  mattpocock        npx skills add mattpocock/skills

Options:
  --host HOST       gstack setup host (cursor|claude|grok|codex); default: grok
  --dry-run         Print install commands only (default)
  --execute         Run install commands (requires explicit opt-in)
  --record PATH     Append install record to fleet-config-style markdown
  -h, --help        Show this help

Examples:
  ./scripts/install-community.sh gstack-browser --dry-run
  ./scripts/install-community.sh gstack --host grok --execute
  ./scripts/install-skills.sh --all --with-community gstack-browser --execute
EOF
}

BUNDLE=""
HOST="grok"
DRY_RUN=1
EXECUTE=0
RECORD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:?}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      EXECUTE=0
      shift
      ;;
    --execute)
      DRY_RUN=0
      EXECUTE=1
      shift
      ;;
    --record)
      RECORD="${2:?}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "install-community: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -z "$BUNDLE" ]]; then
        BUNDLE="$1"
      else
        echo "install-community: unexpected argument: $1" >&2
        exit 2
      fi
      shift
      ;;
  esac
done

if [[ -z "$BUNDLE" ]]; then
  usage >&2
  exit 2
fi

GSTACK_CLONE_DIR="${GSTACK_SKILLS_DIR:-$HOME/.claude/skills/gstack}"
GSTACK_REPO="${GSTACK_REPO_URL:-https://github.com/garrytan/gstack.git}"

declare -a COMMANDS=()
declare -a SKILL_IDS=()

append_gstack_full() {
  COMMANDS+=("git clone --single-branch --depth 1 ${GSTACK_REPO} ${GSTACK_CLONE_DIR}")
  COMMANDS+=("cd ${GSTACK_CLONE_DIR} && ./setup --host ${HOST}")
  SKILL_IDS+=(browse qa qa-only health office-hours autoplan cso investigate ship review)
}

case "$BUNDLE" in
  gstack)
    append_gstack_full
    ;;
  gstack-browser)
    append_gstack_full
    SKILL_IDS=(browse qa qa-only health)
    ;;
  gstack-framing)
    append_gstack_full
    SKILL_IDS=(office-hours autoplan plan-ceo-review plan-eng-review plan-design-review)
    ;;
  gstack-security)
    append_gstack_full
    SKILL_IDS=(cso investigate)
    ;;
  gstack-devex)
    append_gstack_full
    SKILL_IDS=(plan-devex-review devex-review)
    ;;
  gstack-ship)
    append_gstack_full
    SKILL_IDS=(ship review document-release health)
    ;;
  agent-skills)
    COMMANDS+=("plugin marketplace add https://github.com/addyosmani/agent-skills.git")
    COMMANDS+=("plugin install agent-skills@addy-agent-skills")
    SKILL_IDS=(planning-and-task-breakdown test-driven-development incremental-implementation)
    ;;
  mattpocock)
    COMMANDS+=("npx skills@latest add mattpocock/skills")
    COMMANDS+=("# then run /setup-matt-pocock-skills in your agent host")
    SKILL_IDS=(grill-with-docs grill-me domain-modeling)
    ;;
  *)
    echo "install-community: unknown bundle: $BUNDLE" >&2
    echo "Known bundles: gstack gstack-browser gstack-framing gstack-security gstack-devex gstack-ship agent-skills mattpocock" >&2
    exit 2
    ;;
esac

echo "== install-community =="
echo "bundle:  $BUNDLE"
echo "host:    $HOST"
echo "mode:    $([[ "$EXECUTE" -eq 1 ]] && echo execute || echo dry-run)"
echo "skills:  ${SKILL_IDS[*]}"
echo ""

for cmd in "${COMMANDS[@]}"; do
  echo "$cmd"
done

if [[ "$EXECUTE" -eq 1 ]]; then
  for cmd in "${COMMANDS[@]}"; do
    case "$cmd" in
      \#*) continue ;;
      *)
        echo ">> $cmd"
        eval "$cmd"
        ;;
    esac
  done
  echo "install-community: executed bundle $BUNDLE"
else
  echo ""
  echo "install-community: dry-run only — pass --execute to run commands"
fi

if [[ -n "$RECORD" ]]; then
  {
    echo ""
    echo "| Bundle | Installed | Host | Date |"
    echo "|--------|-----------|------|------|"
    echo "| $BUNDLE | $([[ "$EXECUTE" -eq 1 ]] && echo yes || echo planned) | $HOST | $(date -u +%Y-%m-%d) |"
  } >>"$RECORD"
  echo "install-community: recorded to $RECORD"
fi