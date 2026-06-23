#!/usr/bin/env bash
# Standing mutation gate: assert every manifest mutation is caught by its guard tests.
# See scripts/mutation_check.py + tests/mutations.yaml.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Best-effort venv bootstrap; mutation_check.py runs against ${VENV_PYTHON:-...} regardless.
if source "$ROOT/scripts/lib/venv-bootstrap.sh" 2>/dev/null; then
  bootstrap_validation_venv "$ROOT" 2>/dev/null || true
fi
VENV_PYTHON="${VENV_PYTHON:-$ROOT/.venv/bin/python}"
exec "$VENV_PYTHON" "$ROOT/scripts/mutation_check.py" "$@"
