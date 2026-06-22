"""Regression test for P0-1 (fleet-audit-2): duplicated SHA-PIN block.

The engine document organizes invariants by named blocks of the form
``NAME-WITH-HYPHENS — …`` (em-dash, U+2014). If the same block header
reappears, the engine has duplicated content — a class of drift the
existing structural tests do not catch (they assert presence of an
invariant, not uniqueness).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "skills" / "autonomous-fleet-core" / "references" / "engine.md"

# Anchors look like ``SHA-PIN (…) …``, ``DURABLE-TASK — …``,
# ``BUILD-BLIND-REVIEW: …`` etc., introduced at the start of a list
# item or paragraph as a hyphenated caps token followed by a separator
# (em-dash, colon, or opening parenthesis). Require at least one hyphen
# in the anchor so single-token prose words don't get counted.
ANCHOR_RE = re.compile(
    r"(?m)^[ \t\-]*\*?\*?([A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+)\s*[\u2014:(]"
)


def test_no_engine_block_anchor_appears_twice() -> None:
    text = ENGINE.read_text(encoding="utf-8")
    anchors = ANCHOR_RE.findall(text)
    counts = Counter(anchors)
    duplicates = {name: n for name, n in counts.items() if n > 1}
    assert not duplicates, (
        "engine.md has duplicated block anchors (each named invariant should "
        f"appear once): {duplicates}"
    )
