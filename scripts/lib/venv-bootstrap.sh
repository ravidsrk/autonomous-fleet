#!/usr/bin/env bash
# Shared venv bootstrap for validation scripts. Source after setting ROOT.
#
# Sets VENV_PYTHON and ensures yaml + pytest are importable.
bootstrap_validation_venv() {
  local root="${1:?root directory required}"
  VENV_PYTHON="$root/.venv/bin/python"
  if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Setting up validation venv..."
    python3 -m venv "$root/.venv"
  fi
  if ! "$VENV_PYTHON" -c 'import yaml, pytest' 2>/dev/null; then
    "$VENV_PYTHON" -m pip install -q -r "$root/requirements.txt"
  fi
}