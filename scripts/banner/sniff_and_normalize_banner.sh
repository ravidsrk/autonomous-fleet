#!/usr/bin/env bash
# Sniff banner magic bytes, convert JPEG-as-PNG to real PNG, enforce 2:1 (1200x600).
# AGENTS.md: Nano Banana often returns JPEG when written to .png — sniff and fix.
# Dimension checks use scripts/lib/png_banner.py (stdlib); sips is optional macOS resize only.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: sniff_and_normalize_banner.sh <input-image> <output.png>" >&2
  exit 2
fi

INPUT="$1"
OUTPUT="$2"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PNG_PY="$ROOT/scripts/lib/png_banner.py"

if [[ ! -f "$INPUT" ]]; then
  echo "sniff_and_normalize_banner.sh: missing input $INPUT" >&2
  exit 2
fi

MAGIC="$(xxd -l 4 -p "$INPUT" | tr '[:upper:]' '[:lower:]')"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

SRC="$INPUT"
if [[ "$MAGIC" == ffd8ff* ]]; then
  echo "sniff: JPEG detected — converting to PNG" >&2
  SRC="$WORKDIR/intermediate.png"
  if command -v sips >/dev/null 2>&1; then
    sips -s format png "$INPUT" --out "$SRC" >/dev/null
  else
    echo "sniff_and_normalize_banner.sh: JPEG input requires sips (macOS) or pre-convert to PNG" >&2
    exit 1
  fi
elif [[ "$MAGIC" == 89504e47 ]]; then
  echo "sniff: PNG detected" >&2
  cp "$INPUT" "$WORKDIR/intermediate.png"
  SRC="$WORKDIR/intermediate.png"
else
  echo "sniff_and_normalize_banner.sh: unsupported magic $MAGIC" >&2
  exit 1
fi

read -r W H < <(python3 "$PNG_PY" dimensions "$SRC")
TARGET_W=1200
TARGET_H=600

mkdir -p "$(dirname "$OUTPUT")"
if [[ "$W" == "$TARGET_W" && "$H" == "$TARGET_H" ]]; then
  cp "$SRC" "$OUTPUT"
elif command -v sips >/dev/null 2>&1; then
  sips -z "$TARGET_H" "$TARGET_W" "$SRC" --out "$OUTPUT" >/dev/null
else
  echo "sniff_and_normalize_banner.sh: need resize (${W}x${H} -> ${TARGET_W}x${TARGET_H}) but sips unavailable" >&2
  exit 1
fi

OUT_MAGIC="$(xxd -l 4 -p "$OUTPUT" | tr '[:upper:]' '[:lower:]')"
if [[ "$OUT_MAGIC" != 89504e47 ]]; then
  echo "sniff_and_normalize_banner.sh: output is not PNG ($OUT_MAGIC)" >&2
  exit 1
fi

read -r OW OH < <(python3 "$PNG_PY" dimensions "$OUTPUT")
echo "sniff_and_normalize_banner.sh: wrote $OUTPUT (${OW}x${OH}, PNG)" >&2