#!/usr/bin/env bash
# Install autonomous-fleet skills using the npx skills CLI (agentskills.io standard).
#
# Usage:
#   ./scripts/install-skills.sh              # starter set (umbrella + program + core + grok + doc-sync)
#   ./scripts/install-skills.sh --all        # install all 12 fleet skills
#   ./scripts/install-skills.sh doc-sync bug-batch   # install named skills
#   ./scripts/install-skills.sh --all --with-community gstack-browser [--execute]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT"

# Pin the skills CLI for supply-chain integrity. An unpinned `npx skills` fetches and runs
# whatever the latest published release happens to be. Bump deliberately.
SKILLS_CLI="skills@1.5.12"

usage() {
  cat <<'EOF'
Usage: install-skills.sh [--all | skill ...] [--with-community BUNDLE] [--execute]

  --with-community BUNDLE   After fleet install, run install-community.sh for BUNDLE
                              (default dry-run; pass --execute to run community install)
  --execute                   With --with-community, execute community install commands
  -h, --help                  Show this help
EOF
}

WITH_COMMUNITY=""
COMMUNITY_EXECUTE=0
ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-community)
      WITH_COMMUNITY="${2:?}"
      shift 2
      ;;
    --execute)
      COMMUNITY_EXECUTE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

set -- "${ARGS[@]}"

run_fleet_install() {
  if [[ "${1:-}" == "--all" ]]; then
    npx "$SKILLS_CLI" add "$SOURCE" --skill '*' -y -p
    return
  fi
  if [[ $# -gt 0 ]]; then
    npx "$SKILLS_CLI" add "$SOURCE" --skill "$@" -y -p
    return
  fi
  # Default: the "Grok starter set".
  #
  # This intentionally differs from the README's quickstart in two ways, and that is fine —
  # they target different defaults (the README agent calls out the difference):
  #   1. Adapter: this set installs `autonomous-fleet-adapter-grok`; the README quickstart
  #      installs `-claude-code`. Swap `-grok` below for your chosen runtime.
  #   2. `-p`: this set passes `-p` (install into the project, not the user-global skills dir),
  #      so a clone's local skills win; the README quickstart omits it for a fresh project.
  # Both install the same six-skill set from this repo and pin `skills@1.5.12`.
  npx "$SKILLS_CLI" add "$SOURCE" \
    --skill setup-autonomous-fleet \
    --skill autonomous-fleet \
    --skill fleet-program \
    --skill autonomous-fleet-core \
    --skill autonomous-fleet-adapter-grok \
    --skill doc-sync \
    -y -p
}

run_fleet_install "$@"

if [[ -n "$WITH_COMMUNITY" ]]; then
  EXTRA=(--host grok)
  if [[ "$COMMUNITY_EXECUTE" -eq 1 ]]; then
    EXTRA+=(--execute)
  else
    EXTRA+=(--dry-run)
  fi
  "$ROOT/scripts/install-community.sh" "$WITH_COMMUNITY" "${EXTRA[@]}"
fi