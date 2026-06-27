"""Starlight guide sync script."""

from __future__ import annotations

import re
import runpy
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


def test_rewrite_md_href_preserves_external_links() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    assert mod._rewrite_md_href("https://example.com/doc.md") == "https://example.com/doc.md"
    assert mod._rewrite_md_href("/already/starlight/") == "/already/starlight/"
    assert mod._rewrite_md_href("page.MD") == "page.MD"


def test_convert_file_rewrites_internal_md_links(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    src = tmp_path / "02-installation.md"
    src.write_text(
        "<!-- title: Install | description: Setup | sidebar_order: 2 -->\n\n"
        "See [Quickstart](01-quickstart.md) and [Index](README.md).\n",
        encoding="utf-8",
    )
    dest = tmp_path / "out.md"
    mod.convert_file(src, dest)
    text = dest.read_text(encoding="utf-8")
    assert "[Quickstart](/01-quickstart/)" in text
    assert "[Index](/)" in text
    assert ".md)" not in text


def test_sync_guide_starlight_output_has_no_md_hrefs_in_body() -> None:
    subprocess.run([sys.executable, str(SYNC)], cwd=ROOT, check=True)
    install = OUT / "02-installation.md"
    body = install.read_text(encoding="utf-8").split("---\n", 2)[-1]
    for match in re.finditer(r"\]\(([^)]+)\)", body):
        href = match.group(1)
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        assert not href.endswith(".md"), f"internal link still .md: {href!r}"


def test_sync_guide_starlight_dunder_main() -> None:
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(SYNC), run_name="__main__")
    assert exc.value.code == 0


def test_convert_file_rejects_missing_frontmatter(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    src = tmp_path / "bad.md"
    src.write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing guide frontmatter"):
        mod.convert_file(src, tmp_path / "out.md")


def test_render_file_returns_text_without_writing(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    src = tmp_path / "01-quickstart.md"
    src.write_text(
        "<!-- title: Quickstart | description: Start here | sidebar_order: 1 -->\n\n# Body\n",
        encoding="utf-8",
    )
    rendered = mod.render_file(src)
    assert rendered.startswith("---\n")
    assert 'title: "Quickstart"' in rendered
    # render_file is pure: it must not create any sibling output file.
    assert list(tmp_path.iterdir()) == [src]


def test_check_mode_passes_when_in_sync() -> None:
    """The committed docs-site copy is kept in sync, so --check exits 0."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    # Materialize the canonical copy first so the committed tree is current,
    # then assert --check agrees (read-only, no mutation).
    assert mod.main([]) == 0
    assert mod.main(["--check"]) == 0


def test_check_mode_passes_via_default_argv(monkeypatch) -> None:
    """argv=None falls back to sys.argv[1:]; inject --check there."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    assert mod.main([]) == 0
    monkeypatch.setattr(sys, "argv", [str(SYNC), "--check"])
    assert mod.main() == 0


def test_check_mode_reports_drift_for_modified_copy(tmp_path: Path, monkeypatch, capsys) -> None:
    """A stale committed copy (different content) makes --check exit 1."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    out = tmp_path / "docs"
    out.mkdir()
    # Seed every expected dest from the real render, then corrupt one so the
    # diff is exactly one drifted file (exercises the content-differs branch).
    first = True
    for src in sorted(mod.GUIDE.glob("*.md")):
        name = "index.md" if src.name == "README.md" else src.name
        rendered = mod.render_file(src)
        if first:
            rendered += "DRIFT\n"
            first = False
        (out / name).write_text(rendered, encoding="utf-8")
    monkeypatch.setattr(mod, "OUT", out)

    assert mod.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "stale" in err
    assert "drift:" in err


def test_check_mode_reports_drift_for_missing_copy(tmp_path: Path, monkeypatch, capsys) -> None:
    """A missing committed dest (current is None) counts as drift -> exit 1."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    out = tmp_path / "empty-docs"
    out.mkdir()
    monkeypatch.setattr(mod, "OUT", out)

    assert mod.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "drift:" in err


def test_check_mode_missing_guide_returns_two(tmp_path: Path, monkeypatch) -> None:
    """--check still honors the missing-guide guard (exit 2)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_guide_starlight as mod

    monkeypatch.setattr(mod, "GUIDE", tmp_path / "missing")
    assert mod.main(["--check"]) == 2