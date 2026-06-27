#!/usr/bin/env bash
# Install autonomous-fleet skills using the npx skills CLI (agentskills.io standard).
#
# Usage:
#   ./scripts/install-skills.sh              # starter set (umbrella + program + core + grok + doc-sync)
#   ./scripts/install-skills.sh --all        # install all 12 fleet skills
#   ./scripts/install-skills.sh doc-sync bug-batch   # install named skills
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT"

# Pin the skills CLI for supply-chain integrity. An unpinned `npx skills` fetches and runs
# whatever the latest published release happens to be. Bump deliberately.
SKILLS_CLI="skills@1.5.12"

if [[ "${1:-}" == "--all" ]]; then
  exec npx "$SKILLS_CLI" add "$SOURCE" --skill '*' -y -p
fi

if [[ $# -gt 0 ]]; then
  exec npx "$SKILLS_CLI" add "$SOURCE" --skill "$@" -y -p
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
exec npx "$SKILLS_CLI" add "$SOURCE" \
  --skill setup-autonomous-fleet \
  --skill autonomous-fleet \
  --skill fleet-program \
  --skill autonomous-fleet-core \
  --skill autonomous-fleet-adapter-grok \
  --skill doc-sync \
  -y -p