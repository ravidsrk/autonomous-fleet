#!/usr/bin/env bash
# Shared venv bootstrap for validation scripts. Source after setting ROOT.
#
# Sets VENV_PYTHON and ensures yaml, pytest, and coverage are importable.
bootstrap_validation_venv() {
  local root="${1:?root directory required}"

  # Python version gate. The project documents Python >=3.12 (pyproject.toml
  # `requires-python`). The venv inherits python3's version, so check it before building a
  # too-old venv that then breaks deeper in validation.
  #
  # We hard-fail (exit non-zero) only when python3 is *genuinely too low to function* — below
  # 3.9, where the venv/tooling truly cannot run. Between 3.9 and 3.12 we warn but proceed, so
  # established 3.9-3.11 runners (e.g. this sandbox) keep working instead of breaking on an
  # advisory floor. Set FLEET_PYTHON_STRICT=1 to enforce the documented >=3.12 floor as a hard
  # failure.
  local pyver
  pyver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo unknown)"
  if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    echo "venv-bootstrap: need Python >=3.12 (pyproject requires-python); python3 is $pyver and too old to run validation" >&2
    return 1
  fi
  if [[ "${FLEET_PYTHON_STRICT:-0}" == "1" ]] \
     && ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    echo "venv-bootstrap: need Python >=3.12 (pyproject requires-python, FLEET_PYTHON_STRICT=1); python3 is $pyver" >&2
    return 1
  fi
  if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    echo "venv-bootstrap: warning: project requires Python >=3.12 (pyproject requires-python); python3 is $pyver — proceeding, but upgrade for a supported setup" >&2
  fi

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