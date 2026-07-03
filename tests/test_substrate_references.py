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

AGENT_FACING_DOCS = (
    "skills/autonomous-fleet-core/references/engine.md",
    "skills/autonomous-fleet-core/references/composition.md",
    "skills/autonomous-fleet-core/references/review-findings.md",
    "skills/autonomous-fleet-core/references/strict-mode.md",
    "skills/autonomous-fleet-core/references/run-archive.md",
    "skills/autonomous-fleet-core/references/runtime-goals.md",
    "skills/autonomous-fleet-core/references/blind-fix.md",
    "skills/autonomous-fleet-core/SKILL.md",
    "skills/doc-sync/SKILL.md",
    "skills/test-coverage/SKILL.md",
    "skills/adversarial-review-and-fix/SKILL.md",
    "skills/fleet-program/SKILL.md",
)

# scripts/<bundled CLI> or scripts/lib/<module> — the traveling set.
_BUNDLED_REF = re.compile(
    r"scripts/(?:lib/[a-z_]+\.py|(?:%s))" % "|".join(re.escape(n) for n in CLI_ALLOWLIST)
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
