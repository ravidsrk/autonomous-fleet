"""Agent-facing docs must reference bundled validators via <SUBSTRATE> (issue #81).

engine.md and the mission SKILL.mds are executed by coordinators on
skills-install repos where `scripts/` does not exist. Any bundled tool
referenced as a bare `scripts/...` path is a dead path on the documented
install mode; it must use the engine's SUBSTRATE RESOLUTION notation
(`<SUBSTRATE>/tool.py`) or be explicitly tagged "(framework clone only)".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_substrate_assets import CLI_ALLOWLIST  # noqa: E402

# Every doc a coordinator or worker is told to read: ALL skill SKILL.mds and
# ALL core references (review finding on #112: adapters and fleet-outcome.md
# were the surfaces most likely to bit-rot and were not listed).
AGENT_FACING_DOCS = tuple(
    sorted(
        str(p.relative_to(ROOT))
        for pattern in ("skills/*/SKILL.md", "skills/*/references/*.md")
        for p in ROOT.glob(pattern)
    )
)

# scripts/<bundled CLI>, scripts/lib/<module>, or a shell wrapper whose
# substrate-aware replacement exists — the set that must never appear as a
# bare scripts/ path (untagged) in agent-facing docs.
_SHELL_WRAPPERS = ("validate-fleet-outcome.sh",)
_BUNDLED_REF = re.compile(
    r"scripts/(?:lib/[a-z_]+\.py|(?:%s))"
    % "|".join(re.escape(n) for n in CLI_ALLOWLIST + _SHELL_WRAPPERS)
)


def test_no_bare_scripts_paths_for_bundled_tools() -> None:
    offenders: list[str] = []
    for rel in AGENT_FACING_DOCS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            # The SUBSTRATE RESOLUTION block's clone-detection probe legitimately
            # names the clone path — that's the definition, not a dead reference.
            if "Framework clone" in line or "(framework clone only)" in line:
                continue
            if _BUNDLED_REF.search(line):
                offenders.append(f"{rel}:{i}: {line.strip()[:100]}")
    assert not offenders, (
        "bundled tools referenced as bare scripts/ paths (dead on skills-install; "
        "use <SUBSTRATE>/... per engine.md SUBSTRATE RESOLUTION):\n" + "\n".join(offenders)
    )


def test_engine_defines_substrate_resolution() -> None:
    engine = (ROOT / "skills/autonomous-fleet-core/references/engine.md").read_text(encoding="utf-8")
    assert "SUBSTRATE RESOLUTION" in engine
    assert ".agents/skills/autonomous-fleet-core/assets/substrate" in engine
    assert "substrate: none" in engine


def test_mission_goal_conditions_are_substrate_aware() -> None:
    for mission in ("doc-sync", "test-coverage", "adversarial-review-and-fix"):
        text = (ROOT / "skills" / mission / "SKILL.md").read_text(encoding="utf-8")
        assert "./scripts/validate-fleet-outcome.sh" not in text, mission
        assert "<SUBSTRATE>/validate_fleet_outcome.py" in text, mission
