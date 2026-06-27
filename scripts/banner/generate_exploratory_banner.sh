#!/usr/bin/env bash
# Generate an exploratory-mission banner per AGENTS.md.
#
# Preferred: Nano Banana via generate.sh when OPENROUTER_API_KEY is set.
# Fallback: normalize an existing schematic source image with sniff_and_normalize_banner.sh.
#
# Portable contract:
#   GENERATE_SH  — explicit path to terminal-poster/scripts/generate.sh (required for OpenRouter gen)
#   AGENT_SKILLS_ROOT — optional; if GENERATE_SH unset, tries $AGENT_SKILLS_ROOT/skills/terminal-poster/scripts/generate.sh
#
# usage: generate_exploratory_banner.sh <mission-slug> [source-image]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SLUG="${1:?mission slug required}"
SRC="${2:-}"
OUT="$ROOT/docs/exploratory/missions/$SLUG/assets/banner.png"
PROMPT="$ROOT/docs/exploratory/missions/$SLUG/assets/banner-prompt.txt"
SNIFF="$ROOT/scripts/banner/sniff_and_normalize_banner.sh"

GENERATE="${GENERATE_SH:-}"
if [[ -z "$GENERATE" && -n "${AGENT_SKILLS_ROOT:-}" ]]; then
  GENERATE="$AGENT_SKILLS_ROOT/skills/terminal-poster/scripts/generate.sh"
fi

if [[ ! -f "$PROMPT" ]]; then
  echo "generate_exploratory_banner.sh: missing $PROMPT" >&2
  exit 2
fi

mkdir -p "$(dirname "$OUT")"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

if [[ -n "${OPENROUTER_API_KEY:-}" && -n "$GENERATE" && -f "$GENERATE" ]]; then
  echo "generate_exploratory_banner.sh: OpenRouter generate.sh ($GENERATE)" >&2
  bash "$GENERATE" "$PROMPT" "$WORKDIR/raw.png"
  "$SNIFF" "$WORKDIR/raw.png" "$OUT"
elif [[ -n "$SRC" && -f "$SRC" ]]; then
  echo "generate_exploratory_banner.sh: normalize provided source" >&2
  "$SNIFF" "$SRC" "$OUT"
else
  echo "generate_exploratory_banner.sh: need OPENROUTER_API_KEY+GENERATE_SH (or AGENT_SKILLS_ROOT) or a source image arg" >&2
  exit 2
fi

echo "generate_exploratory_banner.sh: done -> $OUT" >&2