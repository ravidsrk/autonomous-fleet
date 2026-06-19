#!/usr/bin/env bash
# Install autonomous-fleet skills into an Agent Skills-compatible directory.
# Usage: ./scripts/install-skills.sh [target-dir]
# Default target: ~/.grok/skills (Grok Build user skills)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/skills"
TARGET="${1:-$HOME/.grok/skills}"

if [[ ! -d "$SOURCE" ]]; then
  echo "error: skills source not found at $SOURCE" >&2
  exit 1
fi

mkdir -p "$TARGET"

for skill in "$SOURCE"/*/; do
  name="$(basename "$skill")"
  dest="$TARGET/$name"
  if [[ -e "$dest" && ! -L "$dest" ]]; then
    echo "skip $name (already exists at $dest — remove manually to reinstall)"
    continue
  fi
  ln -sfn "$skill" "$dest"
  echo "linked $name -> $dest"
done

echo ""
echo "Installed to $TARGET"
echo "Validate with: $ROOT/scripts/validate-skills.sh"