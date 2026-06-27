"""Starlight guide sync script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "sync_guide_starlight.py"
OUT = ROOT / "docs-site" / "src" / "content" / "docs"


def test_sync_guide_starlight_writes_starlight_frontmatter() -> None:
    r = subprocess.run(
        [sys.executable, str(SYNC)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    index = OUT / "index.md"
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "title: Quickstart" in text or "title:" in text
    assert "sidebar:" in text


def test_sync_main_missing_guide(tmp_path: Path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    monkeypatch.setattr(mod, "GUIDE", tmp_path / "missing")
    assert mod.main() == 2


def test_sync_main_happy_import() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    assert mod.main() == 0


def test_convert_file_quotes_yaml_special_chars(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    src = tmp_path / "colon.md"
    src.write_text(
        "<!-- title: Mental model | description: What a run is: frozen plan | sidebar_order: 4 -->\n\n# Body\n",
        encoding="utf-8",
    )
    dest = tmp_path / "out.md"
    mod.convert_file(src, dest)
    text = dest.read_text(encoding="utf-8")
    assert 'description: "What a run is: frozen plan"' in text


def test_convert_file_rejects_missing_frontmatter(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    src = tmp_path / "bad.md"
    src.write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing guide frontmatter"):
        mod.convert_file(src, tmp_path / "out.md")