"""Portable PNG dimension probe (stdlib only)."""

from __future__ import annotations

import struct
from pathlib import Path


def png_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) from PNG IHDR. Raises ValueError if not a PNG."""
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    if data[12:16] != b"IHDR":
        raise ValueError(f"{path}: missing IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def write_solid_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    """Write a minimal valid RGB PNG (stdlib zlib). For placeholder banners."""
    import zlib

    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _main(argv: list[str] | None = None) -> int:
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if len(args) == 2 and args[0] == "dimensions":
        w, h = png_dimensions(Path(args[1]))
        print(w, h)
        return 0
    print("usage: png_banner.py dimensions <path.png>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())