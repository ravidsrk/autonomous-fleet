#!/usr/bin/env bash
# Install autonomous-fleet skills using the npx skills CLI (agentskills.io standard).
#
# Usage:
#   ./scripts/install-skills.sh              # starter set (umbrella + program + core + grok + doc-sync)
#   ./scripts/install-skills.sh --all        # install all 21 fleet skills
#   ./scripts/install-skills.sh doc-sync bug-batch   # install named skills
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT"

if [[ "${1:-}" == "--all" ]]; then
  exec npx skills add "$SOURCE" --skill '*' -y -p
fi

if [[ $# -gt 0 ]]; then
  exec npx skills add "$SOURCE" --skill "$@" -y -p
fi

# Default starter set for Grok-based runs
exec npx skills add "$SOURCE" \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet \
  --skill fleet-program \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-grok \
  --skill doc-sync \
  -y -p