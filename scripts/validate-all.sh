#!/usr/bin/env bash
# Run all autonomous-fleet validators and tests.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=lib/venv-bootstrap.sh
source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

echo "== validate-skills =="
./scripts/validate-skills.sh

echo ""
echo "== validate-fleet-outcome =="
./scripts/validate-fleet-outcome.sh

echo ""
echo "== validate-goal-condition =="
./scripts/validate-goal-condition.sh --scan-docs

echo ""
echo "== pytest =="
"$VENV_PYTHON" -m pytest tests/ -q

echo ""
echo "All checks passed."