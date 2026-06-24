#!/usr/bin/env bash
# Run an adapter SKILL.md requires-block preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

usage() {
  echo "usage: scripts/preflight.sh <adapter|adapter-dir> [--scm]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

adapter="$1"
shift
scm=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scm)
      scm=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      echo "preflight: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$adapter" == */* ]]; then
  if [[ "$adapter" = /* ]]; then
    adapter_dir="$adapter"
  else
    adapter_dir="$ROOT/$adapter"
  fi
elif [[ -d "$ROOT/skills/autonomous-fleet-adapter-$adapter" ]]; then
  adapter_dir="$ROOT/skills/autonomous-fleet-adapter-$adapter"
elif [[ -d "$ROOT/skills/$adapter" ]]; then
  adapter_dir="$ROOT/skills/$adapter"
else
  echo "preflight: adapter not found: $adapter" >&2
  exit 2
fi

# shellcheck source=lib/venv-bootstrap.sh
source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

"$VENV_PYTHON" - "$adapter_dir" "$scm" <<'PY'
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")

from lib.adapter_preflight import Intent, check, load_requires

adapter_dir = sys.argv[1]
intent = Intent(scm=sys.argv[2] == "1")
failures = check(load_requires(adapter_dir), intent)

if failures:
    print(f"preflight: {len(failures)} failure(s)", file=sys.stderr)
    for failure in failures:
        print(f"FAIL  {failure}", file=sys.stderr)
    raise SystemExit(1)

print("preflight: ok")
PY
