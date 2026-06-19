#!/usr/bin/env bash
# Validate all skills using skill-creator's quick_validate (agentskills.io spec).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_DIR="$ROOT/skills"
VALIDATOR="$ROOT/.agents/skills/skill-creator/scripts/quick_validate.py"
VENV_PYTHON="$ROOT/.venv/bin/python"

if [[ ! -d "$SKILLS_DIR" ]]; then
  echo "error: skills directory not found at $SKILLS_DIR" >&2
  exit 1
fi

if [[ ! -f "$VALIDATOR" ]]; then
  echo "error: skill-creator not installed. Run:" >&2
  echo "  npx skills add https://github.com/anthropics/skills --skill skill-creator -y -p" >&2
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Setting up validation venv..."
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -q pyyaml
fi

ERRORS=0
for skill in "$SKILLS_DIR"/*/; do
  name="$(basename "$skill")"
  if ! output="$("$VENV_PYTHON" "$VALIDATOR" "$skill" 2>&1)"; then
    echo "FAIL $name: $output"
    ERRORS=$((ERRORS + 1))
  else
    echo "OK   $name"
  fi
done

echo ""
if [[ "$ERRORS" -gt 0 ]]; then
  echo "$ERRORS skill(s) failed validation."
  exit 1
fi

echo "All $(find "$SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ') skills passed validation."