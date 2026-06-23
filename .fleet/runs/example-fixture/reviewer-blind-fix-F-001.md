---
finding_id: F-001
reviewer: claude-opus-4.5
---

# Blind fix for F-001

The point of creation is `scripts/coupling-graph.py:_iter_imports:107` — the
walker reads each `ast.ImportFrom` node and only records the dotted name
when `node.level == 0`, which drops every PEP-328 relative import on the
first pass even though the suffix index later in the file can resolve them.

The shape of the fix is to drop the level-gate in this branch and let the
existing relative-import reconstruction at the bottom of the same function
handle both axes. Pre-commit confidence: 78/100.
