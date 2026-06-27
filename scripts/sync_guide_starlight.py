#!/usr/bin/env python3
"""Sync docs/guide/*.md into docs-site/src/content/docs/ for Starlight.

Converts HTML-comment frontmatter (Stage 1 guide format) into YAML
frontmatter Starlight expects.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "guide"
OUT = ROOT / "docs-site" / "src" / "content" / "docs"

_MD_LINK_RE = re.compile(r"\]\(([^)]+\.md)\)")


def _rewrite_md_href(href: str) -> str:
    if href.startswith(("http://", "https://", "mailto:", "/", "#")):
        return href
    if href == "README.md":
        return "/"
    if href.endswith(".md"):
        return f"/{href[:-3]}/"
    return href


def _rewrite_guide_links(body: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return f"]({_rewrite_md_href(match.group(1))})"

    return _MD_LINK_RE.sub(repl, body)


_FRONTMATTER_RE = re.compile(
    r"^<!--\s*title:\s*(?P<title>[^|]+?)\s*\|\s*"
    r"description:\s*(?P<desc>[^|]+?)\s*\|\s*"
    r"sidebar_order:\s*(?P<order>\d+)\s*-->\s*\n",
    re.MULTILINE,
)


def _yaml_scalar(value: str) -> str:
    """Emit a YAML-safe quoted scalar (handles colons, quotes, etc.)."""
    return json.dumps(value, ensure_ascii=False)


def _display_path(path: Path) -> str:
    """Render ``path`` relative to ROOT for messages (never raises)."""
    return os.path.relpath(path, ROOT)


def render_file(src: Path) -> str:
    """Convert a guide source into the Starlight document text (in-memory)."""
    text = src.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{src}: missing guide frontmatter comment")
    body = _rewrite_guide_links(text[m.end() :])
    front = (
        "---\n"
        f"title: {_yaml_scalar(m.group('title').strip())}\n"
        f"description: {_yaml_scalar(m.group('desc').strip())}\n"
        f"sidebar:\n  order: {m.group('order').strip()}\n"
        "---\n\n"
    )
    return front + body


def convert_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_file(src), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    if not GUIDE.is_dir():
        print(f"sync_guide_starlight: missing {GUIDE}", file=sys.stderr)
        return 2
    if check:
        drifted: list[str] = []
        expected_names = {
            "index.md" if src.name == "README.md" else src.name
            for src in GUIDE.glob("*.md")
        }
        for src in sorted(GUIDE.glob("*.md")):
            name = "index.md" if src.name == "README.md" else src.name
            dest = OUT / name
            rendered = render_file(src)
            current = dest.read_text(encoding="utf-8") if dest.is_file() else None
            if current != rendered:
                drifted.append(_display_path(dest))
        if OUT.is_dir():
            for dest in sorted(OUT.glob("*.md")):
                if dest.name not in expected_names:
                    drifted.append(_display_path(dest))
        if drifted:
            print(
                "sync_guide_starlight: committed docs-site copy is stale; "
                "run scripts/sync_guide_starlight.py and commit:",
                file=sys.stderr,
            )
            for path in drifted:
                print(f"  drift: {path}", file=sys.stderr)
            return 1
        print("sync_guide_starlight: docs-site copy is in sync")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for src in sorted(GUIDE.glob("*.md")):
        name = "index.md" if src.name == "README.md" else src.name
        convert_file(src, OUT / name)
        print(f"synced {src.name} -> {OUT / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())