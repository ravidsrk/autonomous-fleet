#!/usr/bin/env bash
# Run all autonomous-fleet validators and tests.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== validate-skills =="
./scripts/validate-skills.sh

echo ""
echo "== validate-fleet-outcome =="
./scripts/validate-fleet-outcome.sh

echo ""
echo "== pytest =="
VENV_PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  python3 -m venv "$ROOT/.venv"
  "$VENV_PYTHON" -m pip install -q pyyaml pytest
fi
"$VENV_PYTHON" -m pytest tests/ -q

echo ""
echo "All checks passed."