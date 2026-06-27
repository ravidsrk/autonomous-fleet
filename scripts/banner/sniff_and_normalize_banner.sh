#!/usr/bin/env bash
# Sniff banner magic bytes, convert JPEG-as-PNG to real PNG, enforce 2:1 (1200x600).
# AGENTS.md: Nano Banana often returns JPEG when written to .png — sniff and fix.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: sniff_and_normalize_banner.sh <input-image> <output.png>" >&2
  exit 2
fi

INPUT="$1"
OUTPUT="$2"

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
  sips -s format png "$INPUT" --out "$SRC" >/dev/null
elif [[ "$MAGIC" == 89504e47 ]]; then
  echo "sniff: PNG detected" >&2
  cp "$INPUT" "$WORKDIR/intermediate.png"
  SRC="$WORKDIR/intermediate.png"
else
  echo "sniff_and_normalize_banner.sh: unsupported magic $MAGIC" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"
# 2:1 banner per AGENTS.md (~1200x600): height 600, width 1200
sips -z 600 1200 "$SRC" --out "$OUTPUT" >/dev/null

OUT_MAGIC="$(xxd -l 4 -p "$OUTPUT" | tr '[:upper:]' '[:lower:]')"
if [[ "$OUT_MAGIC" != 89504e47 ]]; then
  echo "sniff_and_normalize_banner.sh: output is not PNG ($OUT_MAGIC)" >&2
  exit 1
fi

W="$(sips -g pixelWidth "$OUTPUT" 2>/dev/null | awk '/pixelWidth/ {print $2}')"
H="$(sips -g pixelHeight "$OUTPUT" 2>/dev/null | awk '/pixelHeight/ {print $2}')"
echo "sniff_and_normalize_banner.sh: wrote $OUTPUT (${W}x${H}, PNG)" >&2