#!/usr/bin/env bash
# Validate all skills using skill-creator's quick_validate (agentskills.io spec).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_DIR="$ROOT/skills"
# SKILL_CREATOR_DIR overrides the skill-creator location (default: installed under .agents).
# Lets tests force the validator-absent path deterministically regardless of what is installed.
VALIDATOR="${SKILL_CREATOR_DIR:-$ROOT/.agents/skills/skill-creator}/scripts/quick_validate.py"

# shellcheck source=lib/venv-bootstrap.sh
source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

if [[ ! -d "$SKILLS_DIR" ]]; then
  echo "error: skills directory not found at $SKILLS_DIR" >&2
  exit 1
fi

if [[ ! -f "$VALIDATOR" ]]; then
  if [[ "${VALIDATE_SKILLS_OPTIONAL:-0}" == "1" ]]; then
    echo "WARN skill-creator not installed; skipping skill validation (VALIDATE_SKILLS_OPTIONAL=1)." >&2
    echo "  To enable: npx skills add https://github.com/anthropics/skills --skill skill-creator -y -p" >&2
    exit 0
  fi
  echo "error: skill-creator validator not found at $VALIDATOR" >&2
  echo "  Install: npx skills add https://github.com/anthropics/skills --skill skill-creator -y -p" >&2
  echo "  Or set VALIDATE_SKILLS_OPTIONAL=1 to skip skill validation." >&2
  exit 1
fi

ERRORS=0
for skill in "$SKILLS_DIR"/*/; do
  name="$(basename "$skill")"
  if ! output="$("$VENV_PYTHON" "$VALIDATOR" "$skill" 2>&1)"; then
    echo "FAIL $name: $output"
    ERRORS=$((ERRORS + 1))
  elif ! output="$("$VENV_PYTHON" "$ROOT/scripts/lib/skill_lint.py" "$skill" 2>&1)"; then
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
