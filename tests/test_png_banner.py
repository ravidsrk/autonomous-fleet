"""Portable PNG banner helper (stdlib only)."""

from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PNG_PY = ROOT / "scripts" / "lib" / "png_banner.py"


def test_write_solid_png_and_dimensions_roundtrip(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import png_dimensions, write_solid_png

    out = tmp_path / "banner.png"
    write_solid_png(out, 1200, 600, (11, 18, 32))
    assert out.read_bytes()[:4] == b"\x89PNG"
    assert png_dimensions(out) == (1200, 600)


def test_png_dimensions_rejects_non_png(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import png_dimensions

    bad = tmp_path / "not.png"
    bad.write_bytes(b"not a png file")
    with pytest.raises(ValueError, match="not a PNG"):
        png_dimensions(bad)


def test_png_dimensions_rejects_missing_ihdr(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import png_dimensions

    bad = tmp_path / "bad.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    with pytest.raises(ValueError, match="missing IHDR"):
        png_dimensions(bad)


def test_png_banner_cli_dimensions() -> None:
    banner = ROOT / "docs/exploratory/missions/archive/product-framing/assets/banner.png"
    r = subprocess.run(
        [sys.executable, str(PNG_PY), "dimensions", str(banner)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "1200 600"


def test_png_banner_cli_usage_error() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import _main

    assert _main([]) == 2


def test_png_banner_main_dimensions_inprocess(capsys) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import _main

    banner = ROOT / "docs/exploratory/missions/archive/product-framing/assets/banner.png"
    assert _main(["dimensions", str(banner)]) == 0
    assert capsys.readouterr().out.strip() == "1200 600"


def test_png_banner_dunder_main() -> None:
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(PNG_PY), run_name="__main__")
    assert exc.value.code == 2


def test_png_magic_hex() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import png_magic_hex

    banner = ROOT / "docs/exploratory/missions/archive/devex-audit/assets/banner.png"
    assert png_magic_hex(banner) == "89504e47"


def test_write_mission_schematic_banner(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import (
        banner_has_label_ink,
        is_placeholder_banner,
        png_dimensions,
        write_mission_schematic_banner,
    )

    out = tmp_path / "banner.png"
    write_mission_schematic_banner(out, "devex-audit")
    assert png_dimensions(out) == (1200, 600)
    assert not is_placeholder_banner(out)
    assert banner_has_label_ink(out)


def test_is_placeholder_detects_solid_png(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import is_placeholder_banner, write_solid_png

    tiny = tmp_path / "solid.png"
    write_solid_png(tiny, 1200, 600, (11, 18, 32))
    assert is_placeholder_banner(tiny)


@pytest.mark.parametrize("slug", ["release-document", "incident-investigate"])
def test_write_all_schematic_banners(slug: str, tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import banner_has_label_ink, is_placeholder_banner, write_mission_schematic_banner

    out = tmp_path / f"{slug}.png"
    write_mission_schematic_banner(out, slug)
    assert not is_placeholder_banner(out)
    assert banner_has_label_ink(out)


def test_write_schematic_unknown_slug(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import write_mission_schematic_banner

    with pytest.raises(ValueError, match="unknown mission slug"):
        write_mission_schematic_banner(tmp_path / "x.png", "not-a-mission")


def test_png_dimensions_errors(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import png_dimensions, png_unique_color_count

    bad = tmp_path / "nope.bin"
    bad.write_bytes(b"junk")
    with pytest.raises(ValueError):
        png_dimensions(bad)
    with pytest.raises(ValueError):
        png_unique_color_count(bad)


def test_png_banner_magic_cli() -> None:
    banner = ROOT / "docs/exploratory/missions/archive/devex-audit/assets/banner.png"
    r = subprocess.run(
        [sys.executable, str(PNG_PY), "magic", str(banner)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert r.stdout.strip() == "89504e47"


def test_png_banner_write_schematic_cli(tmp_path: Path) -> None:
    out = tmp_path / "banner.png"
    r = subprocess.run(
        [
            sys.executable,
            str(PNG_PY),
            "write-schematic",
            "devex-audit",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert out.stat().st_size > 8000


def test_is_placeholder_missing_file(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import is_placeholder_banner

    assert is_placeholder_banner(tmp_path / "missing.png")


def test_banner_has_label_ink_false_on_blank(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import banner_has_label_ink, write_solid_png

    blank = tmp_path / "blank.png"
    write_solid_png(blank, 120, 80, (11, 18, 32))
    assert not banner_has_label_ink(blank, x1=40, y1=40)


def test_main_magic_inprocess(capsys) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import _main

    banner = ROOT / "docs/exploratory/missions/archive/devex-audit/assets/banner.png"
    assert _main(["magic", str(banner)]) == 0
    assert capsys.readouterr().out.strip() == "89504e47"


def test_main_write_schematic_inprocess(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import _main

    out = tmp_path / "banner.png"
    assert _main(["write-schematic", "devex-audit", str(out)]) == 0
    assert out.stat().st_size > 8000


def test_is_placeholder_few_colors(monkeypatch, tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import lib.png_banner as mod

    banner = tmp_path / "banner.png"
    banner.write_bytes(b"\x89PNG" + b"\x00" * 9000)
    monkeypatch.setattr(mod, "png_unique_color_count", lambda *a, **k: 3)
    assert mod.is_placeholder_banner(banner)


def test_is_placeholder_empty_pixel_sample(monkeypatch, tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import lib.png_banner as mod

    banner = tmp_path / "banner.png"
    banner.write_bytes(b"\x89PNG" + b"\x00" * 9000)
    monkeypatch.setattr(mod, "png_unique_color_count", lambda *a, **k: 20)
    monkeypatch.setattr(mod, "_decode_png_rgb", lambda _p: (1, 1, []))
    assert mod.is_placeholder_banner(banner)


def test_is_placeholder_corrupt_large_file(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import is_placeholder_banner

    bad = tmp_path / "bad.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 12_000)
    assert is_placeholder_banner(bad)


def test_decode_png_missing_idat(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.png_banner import _decode_png_rgb

    import struct
    import zlib

    ihdr = struct.pack(">IIBBBBB", 10, 10, 8, 2, 0, 0, 0)
    def chunk(tag, payload):
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")
    path = tmp_path / "noidat.png"
    path.write_bytes(png)
    with pytest.raises(ValueError, match="missing IDAT"):
        _decode_png_rgb(path)