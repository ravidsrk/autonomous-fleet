#!/usr/bin/env bash
# Shared venv bootstrap for validation scripts. Source after setting ROOT.
#
# Sets VENV_PYTHON and ensures yaml, pytest, and coverage are importable.
bootstrap_validation_venv() {
  local root="${1:?root directory required}"
  VENV_PYTHON="$root/.venv/bin/python"
  if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Setting up validation venv..."
    python3 -m venv "$root/.venv"
  fi
  if ! "$VENV_PYTHON" -c 'import yaml, pytest, coverage' 2>/dev/null; then
    "$VENV_PYTHON" -m pip install -q -r "$root/requirements.txt"
    if ! "$VENV_PYTHON" -c 'import yaml, pytest, coverage'; then
      echo "venv-bootstrap: pip install succeeded but yaml, pytest, or coverage still missing" >&2
      return 1
    fi
  fi
}