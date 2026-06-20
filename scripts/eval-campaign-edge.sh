#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# shellcheck source=lib/venv-bootstrap.sh
source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

exec "$VENV_PYTHON" "$ROOT/scripts/eval-campaign-edge.py" "$@"