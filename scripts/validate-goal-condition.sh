#!/usr/bin/env bash
# Lint runtime goal conditions: must reference docs/ paths (file-ledger truth).
#
# Usage:
#   ./scripts/validate-goal-condition.sh --text "Mission doc-sync DONE: docs/doc-sync-progress.md ..."
#   ./scripts/validate-goal-condition.sh --ledger docs/fleet-program-progress.md
#   ./scripts/validate-goal-condition.sh --scan-docs
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage:
  validate-goal-condition.sh --text "<condition string>"
  validate-goal-condition.sh --ledger <path>
  validate-goal-condition.sh --scan-docs

Checks:
  - Condition contains docs/ (file-based truth)
  - Condition mentions progress or readiness (or fleet-program-progress)
  - Optional: recommends validate-fleet-outcome for mission/campaign goals
EOF
}

check_condition() {
  local text="$1"
  local label="${2:-condition}"

  if [[ -z "$text" ]]; then
    echo "FAIL $label: empty condition" >&2
    return 1
  fi

  local err=0

  # Accept the default docs/ layout, the relocated FLEET_LEDGER_DIR, or the
  # <LEDGER_DIR> template placeholder (issue #101) — the rule is "reference a
  # FILE-ledger path", so require an actual <dir>/<file>.md token, not a bare
  # substring (round-3 hardening: 'docs//' and dangling placeholders fail).
  ledger_re='(docs|<LEDGER_DIR>)/[A-Za-z0-9_<>./-]*[A-Za-z0-9_<>-]\.md'
  if [[ -n "${FLEET_LEDGER_DIR:-}" ]]; then
    esc_dir="$(printf '%s' "${FLEET_LEDGER_DIR%/}" | sed 's/[.[\*^$()+?{|]/\\&/g')"
    ledger_re="(docs|<LEDGER_DIR>|${esc_dir})/[A-Za-z0-9_<>./-]*[A-Za-z0-9_<>-]\.md"
  fi
  if ! printf '%s' "$text" | grep -qE "$ledger_re"; then
    echo "FAIL $label: must reference a ledger file path (docs/…​.md, <LEDGER_DIR>/….md, or \$FLEET_LEDGER_DIR/….md)" >&2
    err=1
  fi

  if [[ "$text" != *progress* && "$text" != *readiness* && "$text" != *fleet-program* ]]; then
    echo "FAIL $label: must reference progress, readiness, or fleet-program ledger" >&2
    err=1
  fi

  if [[ "$err" -eq 0 ]]; then
    echo "OK   $label"
  fi
  return "$err"
}

extract_ledger_condition() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "FAIL ledger file not found: $file" >&2
    return 1
  fi
  "${VENV_PYTHON:-python3}" - "$file" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
if "## Runtime goal" not in text:
    sys.exit(0)
block = text.split("## Runtime goal", 1)[1]
# stop at next ## section
if "\n## " in block:
    block = block.split("\n## ", 1)[0]
lines = block.splitlines()
capture = False
out = []
for line in lines:
    if line.startswith("CONDITION:"):
        capture = True
        rest = line.split("CONDITION:", 1)[1].strip()
        if rest == "|":
            continue
        if rest:
            out.append(rest)
        continue
    if capture:
        if line and not line.startswith((" ", "\t")):
            import re
            if re.match(r"^[A-Z_]+:", line):
                break
        if line.strip():
            out.append(line.strip())
print("\n".join(out))
PY
}

scan_docs_ledgers() {
  local err=0
  local found=0
  while IFS= read -r -d '' f; do
    if grep -q '^## Runtime goal' "$f" 2>/dev/null; then
      found=1
      cond="$(extract_ledger_condition "$f" || true)"
      if [[ -z "${cond:-}" ]]; then
        echo "FAIL $f: ## Runtime goal present but CONDITION empty" >&2
        err=1
        continue
      fi
      if ! check_condition "$cond" "$f"; then
        err=1
      fi
    fi
  done < <(find docs "${FLEET_LEDGER_DIR:-docs}" -maxdepth 1 -name '*-progress.md' -print0 2>/dev/null | sort -zu)

  if [[ "$found" -eq 0 ]]; then
    echo "OK   no ## Runtime goal sections in ledger *-progress.md (docs/ + FLEET_LEDGER_DIR; nothing to validate)"
  fi
  return "$err"
}

main() {
  local mode="${1:-}"
  case "$mode" in
    --text)
      shift
      check_condition "${*:-}"
      ;;
    --ledger)
      shift
      [[ $# -ge 1 ]] || { usage; exit 1; }
      cond="$(extract_ledger_condition "$1")"
      check_condition "$cond" "$1"
      ;;
    --scan-docs)
      scan_docs_ledgers
      ;;
    -h|--help|"")
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option $mode" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"