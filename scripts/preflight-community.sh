#!/usr/bin/env bash
# Warn-tier preflight for mission community-recommends blocks.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage: preflight-community.sh <mission> [--dry-run]

Checks community-recommends on the mission SKILL.md. Under mode: warn, prints install
hints and exits 0. Under mode: fail, exits 1 when recommended skills are absent.
EOF
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi

mission="$1"
shift
dry=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|--dry)
      dry=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      echo "preflight-community: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

# shellcheck source=lib/venv-bootstrap.sh
source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

"$VENV_PYTHON" - "$ROOT" "$mission" "$dry" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "scripts")

from lib.community_preflight import check, load_recommends, mission_skill_path

repo = Path(sys.argv[1])
mission = sys.argv[2]
dry = sys.argv[3] == "1"

skill_dir = mission_skill_path(repo, mission)
if skill_dir is None:
    print(f"preflight-community: no SKILL.md for mission {mission!r} (skip)")
    raise SystemExit(0)

try:
    recommends = load_recommends(skill_dir)
except ValueError as exc:
    print(f"preflight-community: {exc}", file=sys.stderr)
    raise SystemExit(2) from exc

if recommends is None:
    print("preflight-community: ok (no community-recommends)")
    raise SystemExit(0)

import os

probe_home = os.environ.get("COMMUNITY_PROBE_HOME", "").strip() or None
result = check(recommends, home=probe_home)
if dry:
    print(f"preflight-community: dry-run mode={result.mode} bundle={result.bundle}")

if result.recommended_line:
    print(result.recommended_line)
if result.install_hint:
    print(result.install_hint)

for warning in result.warnings:
    print(f"WARN  {warning}")
    print("       recommended community skills accelerate this mission; TASK fallbacks still apply")

for failure in result.failures:
    print(f"FAIL  {failure}", file=sys.stderr)

if result.failures:
    raise SystemExit(1)

print("preflight-community: ok")
PY