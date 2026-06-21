# Research notes (doc-sync dogfood, 2026-06-21)

Per engine.md RESEARCH DISCIPLINE: every external fact the build relies on, logged with a source and
a verified/unverified flag. This mission documents new capabilities, so each claim the doc edits
assert was verified before writing.

| unknown | source | finding | status |
|---------|--------|---------|--------|
| container-use is a real, current tool worth documenting | monid `exa /search` -> github.com/dagger/container-use, dagger.io/blog/agent-container-use; local `container-use version` | MCP server, isolated container + git branch per agent; v0.4.2 installed | verified |
| the new scripts exist as the README will claim | repo `ls scripts/` | run-sandboxed.sh, coupling-graph.py, render-dashboard.py all present and executable | verified |
| the merge-rate dataset the tier docs cite is real | re-confirmed (orchestration-landscape.md) arXiv 2601.15195, MSR AIDev 33,596 PRs | real and cited correctly; not re-asserting a number, just referencing | verified |
| the new fleet-outcome fields validate as documented | repo `scripts/lib/fleet_outcome.py` + pytest | unverified_assumptions / sources_logged / cost_estimate accepted as optional, validated | verified |

unverified_assumptions: 0 (no doc edit asserts an external fact without a logged source above).
