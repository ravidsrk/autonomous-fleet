#!/usr/bin/env bash
# Generate an exploratory-mission banner per AGENTS.md.
#
# Preferred: Nano Banana via agent-skills generate.sh when OPENROUTER_API_KEY is set.
# Fallback: normalize an existing schematic source image with sniff_and_normalize_banner.sh.
#
# usage: generate_exploratory_banner.sh <mission-slug> [source-image]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SLUG="${1:?mission slug required}"
SRC="${2:-}"
OUT="$ROOT/docs/exploratory/missions/$SLUG/assets/banner.png"
PROMPT="$ROOT/docs/exploratory/missions/$SLUG/assets/banner-prompt.txt"
GENERATE="${GENERATE_SH:-$HOME/.claude/skills/agent-skills/skills/terminal-poster/scripts/generate.sh}"
SNIFF="$ROOT/scripts/banner/sniff_and_normalize_banner.sh"

if [[ ! -f "$PROMPT" ]]; then
  echo "generate_exploratory_banner.sh: missing $PROMPT" >&2
  exit 2
fi

mkdir -p "$(dirname "$OUT")"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

if [[ -n "${OPENROUTER_API_KEY:-}" && -f "$GENERATE" ]]; then
  echo "generate_exploratory_banner.sh: OpenRouter generate.sh" >&2
  bash "$GENERATE" "$PROMPT" "$WORKDIR/raw.png"
  "$SNIFF" "$WORKDIR/raw.png" "$OUT"
elif [[ -n "$SRC" && -f "$SRC" ]]; then
  echo "generate_exploratory_banner.sh: normalize provided source" >&2
  "$SNIFF" "$SRC" "$OUT"
else
  echo "generate_exploratory_banner.sh: need OPENROUTER_API_KEY+generate.sh or a source image arg" >&2
  exit 2
fi

echo "generate_exploratory_banner.sh: done -> $OUT" >&2