#!/usr/bin/env bash
# Validate autonomous-fleet skills against agentskills.io conventions.
# See https://agentskills.io/specification
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_DIR="$ROOT/skills"
ERRORS=0

name_re='^[a-z0-9]+(-[a-z0-9]+)*$'

check_skill() {
  local dir="$1"
  local name
  name="$(basename "$dir")"
  local skill_md="$dir/SKILL.md"

  if [[ ! -f "$skill_md" ]]; then
    echo "FAIL $name: missing SKILL.md"
    ERRORS=$((ERRORS + 1))
    return
  fi

  if [[ ! "$name" =~ $name_re ]]; then
    echo "FAIL $name: directory name must be lowercase alphanumeric with single hyphens"
    ERRORS=$((ERRORS + 1))
  fi

  local fm_name fm_desc
  fm_name="$(awk '/^---$/{n++; next} n==1 && /^name:/{sub(/^name:[[:space:]]*/,""); print; exit}' "$skill_md")"
  fm_desc="$(python3 - "$skill_md" <<'PY'
import sys, re
text = open(sys.argv[1]).read()
m = re.match(r'^---\n(.*?)\n---', text, re.S)
if not m:
    sys.exit(0)
front = m.group(1)
if 'description: >-' in front:
    block = front.split('description: >-', 1)[1].strip()
    lines = []
    for l in block.splitlines():
        s = l.strip()
        if s.startswith(('license:', 'compatibility:', 'metadata:', 'disable-model-invocation:')):
            break
        if l.startswith('  '):
            lines.append(l[2:].strip())
    print(' '.join(lines))
else:
    m2 = re.search(r'^description:\s*(.+)$', front, re.M)
    print(m2.group(1).strip() if m2 else '')
PY
)"

  if [[ -z "$fm_name" ]]; then
    echo "FAIL $name: missing frontmatter name"
    ERRORS=$((ERRORS + 1))
  elif [[ "$fm_name" != "$name" ]]; then
    echo "FAIL $name: frontmatter name '$fm_name' must match directory"
    ERRORS=$((ERRORS + 1))
  fi

  if [[ -z "$fm_desc" ]]; then
    echo "FAIL $name: missing description"
    ERRORS=$((ERRORS + 1))
  elif [[ ${#fm_desc} -gt 1024 ]]; then
    echo "FAIL $name: description length ${#fm_desc} exceeds 1024"
    ERRORS=$((ERRORS + 1))
    return
  fi

  local lines
  lines="$(wc -l < "$skill_md" | tr -d ' ')"
  if [[ "$lines" -gt 500 ]]; then
    echo "WARN $name: SKILL.md is $lines lines (agentskills recommends <500; use references/)"
  fi

  echo "OK   $name"
}

echo "Validating skills in $SKILLS_DIR"
for dir in "$SKILLS_DIR"/*/; do
  [[ -d "$dir" ]] || continue
  check_skill "$dir"
done

if [[ "$ERRORS" -gt 0 ]]; then
  echo ""
  echo "$ERRORS error(s)"
  exit 1
fi

echo ""
echo "All skills passed validation."