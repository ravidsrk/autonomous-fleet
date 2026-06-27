#!/usr/bin/env bash
# Sniff banner magic bytes, convert JPEG-as-PNG to real PNG, enforce 2:1 (1200x600).
# AGENTS.md: Nano Banana often returns JPEG when written to .png — sniff and fix.
# Magic + dimensions use scripts/lib/png_banner.py (stdlib).
#
# Portable image ops (JPEG->PNG, resize): prefer macOS "sips" when present, else
# fall back to ImageMagick "magick"/"convert" (available on Linux/CI). If neither
# is installed the script exits 1 with a clear message — so any contributor on
# macOS or Linux can regenerate/normalize banners without a macOS-only toolchain.
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

_read_magic() {
  python3 "$PNG_PY" magic "$1"
}

# Portable JPEG->PNG: $1 input, $2 output PNG. Prefers sips, else ImageMagick.
_to_png() {
  if command -v sips >/dev/null 2>&1; then
    sips -s format png "$1" --out "$2" >/dev/null
  elif command -v magick >/dev/null 2>&1; then
    magick "$1" "$2"
  elif command -v convert >/dev/null 2>&1; then
    convert "$1" "$2"
  else
    echo "sniff_and_normalize_banner.sh: JPEG input needs sips (macOS) or ImageMagick (magick/convert); install one or pre-convert to PNG" >&2
    exit 1
  fi
}

# Portable resize to exact WxH: $1 input, $2 output, $3 width, $4 height.
# sips -z takes HEIGHT WIDTH; ImageMagick -resize WxH! forces exact dimensions.
_resize_png() {
  if command -v sips >/dev/null 2>&1; then
    sips -z "$4" "$3" "$1" --out "$2" >/dev/null
  elif command -v magick >/dev/null 2>&1; then
    magick "$1" -resize "${3}x${4}!" "$2"
  elif command -v convert >/dev/null 2>&1; then
    convert "$1" -resize "${3}x${4}!" "$2"
  else
    echo "sniff_and_normalize_banner.sh: resize needs sips (macOS) or ImageMagick (magick/convert); install one" >&2
    exit 1
  fi
}

MAGIC="$(_read_magic "$INPUT")"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

SRC="$INPUT"
if [[ "$MAGIC" == ffd8ff* ]]; then
  echo "sniff: JPEG detected — converting to PNG" >&2
  SRC="$WORKDIR/intermediate.png"
  _to_png "$INPUT" "$SRC"
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
else
  echo "sniff: resizing ${W}x${H} -> ${TARGET_W}x${TARGET_H}" >&2
  _resize_png "$SRC" "$OUTPUT" "$TARGET_W" "$TARGET_H"
fi

OUT_MAGIC="$(_read_magic "$OUTPUT")"
if [[ "$OUT_MAGIC" != 89504e47 ]]; then
  echo "sniff_and_normalize_banner.sh: output is not PNG ($OUT_MAGIC)" >&2
  exit 1
fi

read -r OW OH < <(python3 "$PNG_PY" dimensions "$OUTPUT")
echo "sniff_and_normalize_banner.sh: wrote $OUTPUT (${OW}x${OH}, PNG)" >&2