#!/usr/bin/env bash
# Install documented community skill bundles (opt-in; no surprise execution without --execute).
# Commands are executed as discrete argv arrays — never via eval or shell-string interpolation.
set -euo pipefail

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
EXECUTE=0
RECORD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:?}"
      shift 2
      ;;
    --dry-run)
      EXECUTE=0
      shift
      ;;
    --execute)
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

# HOST must match the documented allowlist before any use (including dry-run display).
case "$HOST" in
  cursor|claude|grok|codex) ;;
  *)
    echo "install-community: invalid --host: ${HOST@Q} (allowed: cursor|claude|grok|codex)" >&2
    exit 2
    ;;
esac

GSTACK_CLONE_DIR="${GSTACK_SKILLS_DIR:-$HOME/.claude/skills/gstack}"
GSTACK_REPO="${GSTACK_REPO_URL:-https://github.com/garrytan/gstack.git}"

# Reject shell metacharacters in path/URL overrides so they cannot be smuggled into
# any future string context. Values are always passed as discrete argv, never eval'd.
_reject_shell_meta() {
  local name="$1" value="$2"
  case "$value" in
    *[\`\$\;\|\&\<\>\(\)\{\}\[\]\!\#\*\?\~\"]* | *"'"* | *\\* | *$'\n'* | *$'\r'* | *$'\t'*)
      echo "install-community: $name contains disallowed shell metacharacters" >&2
      exit 2
      ;;
  esac
}

declare -a SKILL_IDS=()
declare -a DISPLAY_LINES=()
IS_GSTACK=0
IS_MATTPOCOCK=0
IS_AGENT_SKILLS=0

# Human-readable dry-run line. Args are either fixed literals, allowlisted HOST,
# or GSTACK_* values that already passed _reject_shell_meta — safe to print joined.
_print_cmd() {
  printf '%s\n' "$*"
}

_note() {
  DISPLAY_LINES+=("$*")
}

_queue_display() {
  DISPLAY_LINES+=("$(_print_cmd "$@")")
}

_plan_gstack() {
  IS_GSTACK=1
  _reject_shell_meta "GSTACK_REPO_URL" "$GSTACK_REPO"
  _reject_shell_meta "GSTACK_SKILLS_DIR" "$GSTACK_CLONE_DIR"
  _queue_display git clone --single-branch --depth 1 "$GSTACK_REPO" "$GSTACK_CLONE_DIR"
  # Display the setup step as a subshell for readability; execute uses discrete argv.
  DISPLAY_LINES+=("(cd $GSTACK_CLONE_DIR && ./setup --host $HOST)")
  SKILL_IDS+=(browse qa qa-only health office-hours autoplan cso investigate ship review)
}

_run_gstack() {
  git clone --single-branch --depth 1 "$GSTACK_REPO" "$GSTACK_CLONE_DIR"
  # Discrete argv: no shell string, no eval. HOST already allowlisted.
  (
    cd -- "$GSTACK_CLONE_DIR"
    ./setup --host "$HOST"
  )
}

_plan_mattpocock() {
  IS_MATTPOCOCK=1
  # Pin skills CLI (SEC-008): never use @latest in an install path.
  _queue_display npx "skills@1.5.12" add mattpocock/skills
  _note "# then run /setup-matt-pocock-skills in your agent host"
  SKILL_IDS=(grill-with-docs grill-me domain-modeling)
}

_run_mattpocock() {
  npx "skills@1.5.12" add mattpocock/skills
}

case "$BUNDLE" in
  gstack)
    _plan_gstack
    ;;
  gstack-browser)
    _plan_gstack
    SKILL_IDS=(browse qa qa-only health)
    ;;
  gstack-framing)
    _plan_gstack
    SKILL_IDS=(office-hours autoplan plan-ceo-review plan-eng-review plan-design-review)
    ;;
  gstack-security)
    _plan_gstack
    SKILL_IDS=(cso investigate)
    ;;
  gstack-devex)
    _plan_gstack
    SKILL_IDS=(plan-devex-review devex-review)
    ;;
  gstack-ship)
    _plan_gstack
    SKILL_IDS=(ship review document-release health)
    ;;
  agent-skills)
    IS_AGENT_SKILLS=1
    _queue_display plugin marketplace add https://github.com/addyosmani/agent-skills.git
    _queue_display plugin install agent-skills@addy-agent-skills
    SKILL_IDS=(planning-and-task-breakdown test-driven-development incremental-implementation)
    ;;
  mattpocock)
    _plan_mattpocock
    ;;
  *)
    echo "install-community: unknown bundle: $BUNDLE" >&2
    echo "Known bundles: gstack gstack-browser gstack-framing gstack-security gstack-devex gstack-ship agent-skills mattpocock" >&2
    exit 2
    ;;
esac

if [[ "$EXECUTE" -eq 1 && "$IS_AGENT_SKILLS" -eq 1 ]]; then
  echo "install-community: agent-skills uses Claude Code slash commands (/plugin marketplace add, /plugin install)" >&2
  echo "  Run those commands inside Claude Code; shell --execute is not supported for this bundle." >&2
  exit 2
fi

echo "== install-community =="
echo "bundle:  $BUNDLE"
echo "host:    $HOST"
echo "mode:    $([[ "$EXECUTE" -eq 1 ]] && echo execute || echo dry-run)"
echo "skills:  ${SKILL_IDS[*]}"
echo ""

for line in "${DISPLAY_LINES[@]}"; do
  echo "$line"
done

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ "$IS_GSTACK" -eq 1 ]]; then
    echo ">> git clone --single-branch --depth 1 $GSTACK_REPO $GSTACK_CLONE_DIR"
    echo ">> (cd $GSTACK_CLONE_DIR && ./setup --host $HOST)"
    _run_gstack
  elif [[ "$IS_MATTPOCOCK" -eq 1 ]]; then
    echo ">> npx skills@1.5.12 add mattpocock/skills"
    _run_mattpocock
  else
    echo "install-community: no executable steps for bundle $BUNDLE" >&2
    exit 2
  fi
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
