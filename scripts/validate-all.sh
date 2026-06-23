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
echo "== validate-run-archive =="
# Run-archive scheme (engine.md ARCHIVE_ENABLED). Default scan looks under
# .fleet/runs/ for any run_id-shaped directories. No archives = exit 0 (the
# discipline is gated on artifact production, not on a directory existing).
"$VENV_PYTHON" scripts/validate_run_archive.py

echo ""
echo "== pytest + coverage (100% gate) =="
"$VENV_PYTHON" -m coverage run --source=scripts -m pytest tests/ -q
"$VENV_PYTHON" -m coverage report --fail-under=100

echo ""
echo "All checks passed."