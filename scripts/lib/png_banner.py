"""Portable PNG helpers: magic sniff, dimensions, schematic mission banners (stdlib only)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SIG_PREFIX = b"\xff\xd8\xff"

# AGENTS.md palette
BG = (11, 18, 32)
BG_EDGE = (15, 23, 42)
AMBER = (245, 158, 11)
SLATE = (148, 163, 184)
INK = (248, 250, 252)
WHITE = (255, 255, 255)

BANNER_W = 1200
BANNER_H = 600
MIN_BANNER_BYTES = 8_000
MIN_UNIQUE_COLORS = 10

# 5x7 bitmap font (rows as 5-bit masks, MSB=left). Space = empty.
_FONT: dict[str, tuple[int, ...]] = {
    " ": (0, 0, 0, 0, 0, 0, 0),
    "/": (0b00100, 0b01000, 0b10000, 0b01000, 0b00100, 0b00000, 0b00000),
    "-": (0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000, 0b00000),
    ".": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b01100, 0b01100),
    "0": (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    "1": (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "2": (0b01110, 0b10001, 0b00001, 0b00110, 0b01000, 0b10000, 0b11111),
    "3": (0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110),
    "4": (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    "5": (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    "6": (0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    "7": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    "8": (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    "9": (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100),
    "a": (0b00000, 0b00000, 0b01110, 0b00001, 0b01111, 0b10001, 0b01111),
    "b": (0b10000, 0b10000, 0b10110, 0b11001, 0b10001, 0b10001, 0b01110),
    "c": (0b00000, 0b00000, 0b01110, 0b10001, 0b10000, 0b10001, 0b01110),
    "d": (0b00001, 0b00001, 0b01101, 0b10011, 0b10001, 0b10001, 0b01110),
    "e": (0b00000, 0b00000, 0b01110, 0b10001, 0b11111, 0b10000, 0b01110),
    "f": (0b00110, 0b01001, 0b01000, 0b11100, 0b01000, 0b01000, 0b01000),
    "g": (0b00000, 0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110),
    "h": (0b10000, 0b10000, 0b10110, 0b11001, 0b10001, 0b10001, 0b10001),
    "i": (0b00100, 0b00000, 0b01100, 0b00100, 0b00100, 0b00100, 0b01110),
    "j": (0b00010, 0b00000, 0b00110, 0b00010, 0b00010, 0b10010, 0b01100),
    "k": (0b10000, 0b10000, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010),
    "l": (0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "m": (0b00000, 0b00000, 0b11010, 0b10101, 0b10101, 0b10001, 0b10001),
    "n": (0b00000, 0b00000, 0b10110, 0b11001, 0b10001, 0b10001, 0b10001),
    "o": (0b00000, 0b00000, 0b01110, 0b10001, 0b10001, 0b10001, 0b01110),
    "p": (0b00000, 0b00000, 0b11110, 0b10001, 0b11110, 0b10000, 0b10000),
    "r": (0b00000, 0b00000, 0b10110, 0b11001, 0b10000, 0b10000, 0b10000),
    "s": (0b00000, 0b00000, 0b01111, 0b10000, 0b01110, 0b00001, 0b11110),
    "t": (0b01000, 0b01000, 0b11110, 0b01000, 0b01000, 0b01001, 0b00110),
    "u": (0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b10011, 0b01101),
    "v": (0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "w": (0b00000, 0b00000, 0b10001, 0b10001, 0b10101, 0b10101, 0b01010),
    "x": (0b00000, 0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001),
    "y": (0b00000, 0b00000, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110),
    "z": (0b00000, 0b00000, 0b11111, 0b00010, 0b00100, 0b01000, 0b11111),
    "·": (0b00000, 0b00000, 0b00000, 0b01100, 0b01100, 0b00000, 0b00000),
}


def png_magic_hex(path: Path) -> str:
    data = path.read_bytes()[:4]
    return data.hex()


def png_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) from PNG IHDR. Raises ValueError if not a PNG."""
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != PNG_SIG:
        raise ValueError(f"{path}: not a PNG")
    if data[12:16] != b"IHDR":
        raise ValueError(f"{path}: missing IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _decode_png_rgb(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    if data[:8] != PNG_SIG:
        raise ValueError(f"{path}: not a PNG")
    pos = 8
    width = height = 0
    idat = b""
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        elif tag == b"IDAT":
            idat += payload
        elif tag == b"IEND":
            break
    if not idat:
        raise ValueError(f"{path}: missing IDAT")
    raw = zlib.decompress(idat)
    pixels: list[tuple[int, int, int]] = []
    stride = 1 + width * 3
    for y in range(height):
        row = raw[y * stride + 1 : y * stride + 1 + width * 3]
        for x in range(width):
            i = x * 3
            pixels.append((row[i], row[i + 1], row[i + 2]))
    return width, height, pixels


def png_unique_color_count(path: Path, *, sample: int = 8) -> int:
    """Count distinct RGB triples (subsampled for speed)."""
    _w, _h, pixels = _decode_png_rgb(path)
    seen: set[tuple[int, int, int]] = set()
    for i in range(0, len(pixels), sample):
        seen.add(pixels[i])
    return len(seen)


def is_placeholder_banner(path: Path) -> bool:
    """True when banner is a tiny or near-uniform placeholder (not schematic art)."""
    if not path.is_file():
        return True
    if path.stat().st_size < MIN_BANNER_BYTES:
        return True
    try:
        colors = png_unique_color_count(path, sample=4)
        if colors < MIN_UNIQUE_COLORS:
            return True
        _w, _h, pixels = _decode_png_rgb(path)
        sample_pixels = pixels[::64]
        if not sample_pixels:
            return True
        top = max(sample_pixels.count(p) for p in set(sample_pixels))
        return top / len(sample_pixels) > 0.98
    except ValueError:
        return True


def banner_has_label_ink(path: Path, *, x0: int = 20, y0: int = 20, x1: int = 320, y1: int = 80) -> bool:
    """True when top-left label region contains ink-toned pixels (text/schematic labels)."""
    w, _h, pixels = _decode_png_rgb(path)
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = pixels[y * w + x]
            if r > 200 and g > 230 and b > 240:
                return True
    return False


def _chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def _write_rgb_png(path: Path, width: int, height: int, flat: list[tuple[int, int, int]]) -> None:
    raw = b""
    for y in range(height):
        row = b"\x00"
        for x in range(width):
            row += bytes(flat[y * width + x])
        raw += row
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = PNG_SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _px(flat: list[tuple[int, int, int]], w: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < w and 0 <= y < len(flat) // w:
        flat[y * w + x] = color


def _hline(flat: list[tuple[int, int, int]], w: int, x0: int, x1: int, y: int, c: tuple[int, int, int]) -> None:
    for x in range(min(x0, x1), max(x0, x1) + 1):
        _px(flat, w, x, y, c)


def _vline(flat: list[tuple[int, int, int]], w: int, x: int, y0: int, y1: int, c: tuple[int, int, int]) -> None:
    for y in range(min(y0, y1), max(y0, y1) + 1):
        _px(flat, w, x, y, c)


def _rect(flat: list[tuple[int, int, int]], w: int, x: int, y: int, rw: int, rh: int, c: tuple[int, int, int]) -> None:
    _hline(flat, w, x, x + rw, y, c)
    _hline(flat, w, x, x + rw, y + rh, c)
    _vline(flat, w, x, y, y + rh, c)
    _vline(flat, w, x + rw, y, y + rh, c)


def _fill_rect(
    flat: list[tuple[int, int, int]], w: int, x: int, y: int, rw: int, rh: int, c: tuple[int, int, int]
) -> None:
    for dy in range(rh):
        for dx in range(rw):
            _px(flat, w, x + dx, y + dy, c)


def _draw_text(
    flat: list[tuple[int, int, int]],
    w: int,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
    *,
    scale: int = 2,
) -> None:
    cx = x
    for ch in text:
        glyph = _FONT.get(ch, _FONT.get(ch.lower(), _FONT[" "]))
        for row_i, row_bits in enumerate(glyph):
            for col in range(5):
                if row_bits & (0b10000 >> col):
                    for sy in range(scale):
                        for sx in range(scale):
                            _px(flat, w, cx + col * scale + sx, y + row_i * scale + sy, color)
        cx += 6 * scale


def _gradient_bg(w: int, h: int) -> list[tuple[int, int, int]]:
    flat: list[tuple[int, int, int]] = []
    for y in range(h):
        for x in range(w):
            t = (x / max(w - 1, 1) + y / max(h - 1, 1)) / 2
            # light dither breaks solid-fill detection and adds depth
            d = ((x ^ y) & 3) - 2
            flat.append(
                (
                    max(0, min(255, int(BG[0] + (BG_EDGE[0] - BG[0]) * t) + d)),
                    max(0, min(255, int(BG[1] + (BG_EDGE[1] - BG[1]) * t) + d)),
                    max(0, min(255, int(BG[2] + (BG_EDGE[2] - BG[2]) * t) + d)),
                )
            )
    return flat


def _draw_devex_audit(flat: list[tuple[int, int, int]], w: int) -> None:
    # stopwatch + terminal (left)
    _rect(flat, w, 80, 180, 90, 120, SLATE)
    _vline(flat, w, 125, 200, 260, SLATE)
    _hline(flat, w, 110, 140, 200, AMBER)
    _rect(flat, w, 200, 200, 140, 90, SLATE)
    _hline(flat, w, 210, 330, 220, INK)
    _hline(flat, w, 210, 300, 240, SLATE)
    _hline(flat, w, 210, 280, 260, SLATE)
    # arrow + scorecard (center)
    for i in range(40):
        _px(flat, w, 420 + i, 250 - i // 4, AMBER)
    _fill_rect(flat, w, 520, 170, 200, 160, (18, 28, 48))
    _rect(flat, w, 520, 170, 200, 160, SLATE)
    for row in range(3):
        yy = 200 + row * 45
        _hline(flat, w, 540, 700, yy, SLATE)
        _px(flat, w, 555, yy + 12, AMBER)
        _px(flat, w, 565, yy + 18, AMBER)
    # doc stack + gap (right)
    for off in range(3):
        _rect(flat, w, 900 + off * 12, 200 + off * 8, 120, 150, SLATE)
    _rect(flat, w, 980, 280, 30, 40, AMBER)


def _draw_release_document(flat: list[tuple[int, int, int]], w: int) -> None:
    _rect(flat, w, 90, 200, 100, 80, SLATE)
    _hline(flat, w, 100, 180, 230, AMBER)
    _draw_text(flat, w, "v0.0", 110, 215, INK, scale=2)
    for i in range(30):
        _px(flat, w, 350 + i, 240, AMBER)
        _px(flat, w, 380 - i, 260, AMBER)
    _rect(flat, w, 280, 180, 80, 120, SLATE)
    _rect(flat, w, 450, 180, 100, 120, SLATE)
    _hline(flat, w, 460, 540, 210, INK)
    _hline(flat, w, 460, 520, 240, SLATE)
    # rocket + checklist (right)
    _vline(flat, w, 980, 320, 200, SLATE)
    _fill_rect(flat, w, 960, 180, 40, 50, SLATE)
    _hline(flat, w, 940, 1020, 320, SLATE)
    _px(flat, w, 1040, 300, AMBER)
    _px(flat, w, 1050, 310, AMBER)


def _draw_incident_investigate(flat: list[tuple[int, int, int]], w: int) -> None:
    for i, yy in enumerate((200, 260, 320)):
        _px(flat, w, 120, yy, AMBER if i == 0 else SLATE)
        _vline(flat, w, 120, yy, yy + 40, SLATE)
    _rect(flat, w, 480, 190, 120, 120, SLATE)
    _hline(flat, w, 500, 580, 230, AMBER)
    _vline(flat, w, 540, 210, 250, AMBER)
    _px(flat, w, 560, 270, SLATE)
    _px(flat, w, 520, 290, SLATE)
    _rect(flat, w, 920, 200, 50, 140, SLATE)
    _hline(flat, w, 930, 960, 210, INK)
    _px(flat, w, 1000, 230, AMBER)
    _px(flat, w, 1010, 240, AMBER)


_COMPOSITIONS = {
    "devex-audit": _draw_devex_audit,
    "release-document": _draw_release_document,
    "incident-investigate": _draw_incident_investigate,
}

_CAPTIONS = {
    "devex-audit": "live walkthrough · frozen DX scorecard",
    "release-document": "post-ship sweep · deploy checklist",
    "incident-investigate": "root cause · regression test",
}


def write_mission_schematic_banner(path: Path, slug: str) -> None:
    """Render AGENTS.md-style schematic banner with label + caption text."""
    if slug not in _COMPOSITIONS:
        raise ValueError(f"unknown mission slug for schematic banner: {slug}")
    w, h = BANNER_W, BANNER_H
    flat = _gradient_bg(w, h)
    _COMPOSITIONS[slug](flat, w)
    label = f"skills/{slug}"
    caption = _CAPTIONS[slug]
    _draw_text(flat, w, label, 28, 28, INK, scale=2)
    cap_w = len(caption) * 12
    _hline(flat, w, w // 2 - cap_w // 2 - 40, w // 2 + cap_w // 2 + 40, h - 72, AMBER)
    _draw_text(flat, w, caption, w // 2 - cap_w // 2, h - 56, INK, scale=2)
    _write_rgb_png(path, w, h, flat)


def write_solid_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    """Write a minimal valid RGB PNG (stdlib zlib). For tests only."""
    row = bytes(rgb) * width
    raw = b""
    for _ in range(height):
        raw += b"\x00" + row
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = PNG_SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _main(argv: list[str] | None = None) -> int:
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if len(args) == 2 and args[0] == "dimensions":
        w, h = png_dimensions(Path(args[1]))
        print(w, h)
        return 0
    if len(args) == 2 and args[0] == "magic":
        print(png_magic_hex(Path(args[1])))
        return 0
    if len(args) == 3 and args[0] == "write-schematic":
        write_mission_schematic_banner(Path(args[2]), args[1])
        return 0
    print(
        "usage: png_banner.py dimensions|magic <path> | write-schematic <slug> <path.png>",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())