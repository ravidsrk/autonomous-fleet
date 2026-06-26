#!/usr/bin/env bash
# One-command contributor bootstrap: venv + deps + full validation gate.
# Usage: ./scripts/bootstrap.sh [--skip-validate]
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap.sh [--skip-validate]

  Create or refresh .venv from requirements.txt, then run validate-all.sh.
  Pass --skip-validate to set up the venv only.
EOF
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/venv-bootstrap.sh
source "$ROOT/scripts/lib/venv-bootstrap.sh"

case "${1:-}" in
  --skip-validate) ;;
  "" ) ;;
  -h|--help) usage; exit 0 ;;
  *) echo "bootstrap: unknown argument: $1" >&2; usage >&2; exit 2 ;;
esac

bootstrap_validation_venv "$ROOT"

echo "bootstrap: venv ready at $ROOT/.venv ($( "$VENV_PYTHON" --version ))"

if [[ "${1:-}" == "--skip-validate" ]]; then
  echo "bootstrap: skipping validate-all (--skip-validate)"
  exit 0
fi

echo "bootstrap: running validate-all.sh..."
exec "$ROOT/scripts/validate-all.sh"