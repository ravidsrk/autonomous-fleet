#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  python3 -m venv "$ROOT/.venv"
  "$VENV_PYTHON" -m pip install -q pyyaml pytest
fi
exec "$VENV_PYTHON" "$ROOT/scripts/eval-campaign-edge.py" "$@"