#!/usr/bin/env bash
# Install autonomous-fleet skills using the npx skills CLI (agentskills.io standard).
#
# Usage:
#   ./scripts/install-skills.sh              # starter set (umbrella + program + core + orca + doc-sync)
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
  # Default: Orca reference-runtime starter set (matches README quickstart adapter).
  # Companion Orca skills (orchestration, orca-cli) ship with the Orca app — not this repo.
  # `-p` installs into the project so a clone's local skills win.
  npx "$SKILLS_CLI" add "$SOURCE" \
    --skill setup-autonomous-fleet \
    --skill autonomous-fleet \
    --skill fleet-program \
    --skill autonomous-fleet-core \
    --skill autonomous-fleet-adapter-orca \
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