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
    banner = ROOT / "docs/exploratory/missions/product-framing/assets/banner.png"
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

    banner = ROOT / "docs/exploratory/missions/product-framing/assets/banner.png"
    assert _main(["dimensions", str(banner)]) == 0
    assert capsys.readouterr().out.strip() == "1200 600"


def test_png_banner_dunder_main() -> None:
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(PNG_PY), run_name="__main__")
    assert exc.value.code == 2