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


def test_single_session_adapters_carry_buildblind_caveat() -> None:
    """Issue #88: every single-session adapter must state in its own file that
    build-blindness there is instructed, not mechanical."""
    for name in (
        "autonomous-fleet-adapter-claude-code",
        "autonomous-fleet-adapter-codex",
        "autonomous-fleet-adapter-grok",
    ):
        text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "single-vendor caveat" in text, name
        assert "reviewer_mode: same-vendor-instructed" in text, name


def test_shipped_mission_metrics_have_operational_definitions() -> None:
    """Issue #99: every metric a shipped mission must report is defined
    operationally in fleet-outcome.md — an edge that branches on an undefined
    metric is incantatory."""
    from lib.fleet_outcome import MISSION_METRICS

    doc = (ROOT / "skills/autonomous-fleet-core/references/fleet-outcome.md").read_text(encoding="utf-8")
    assert "## Metric definitions" in doc
    # Scope the check to the definitions SECTION (codex on #121: a doc-wide
    # backtick match was satisfied by the metrics table, so deleting the
    # definitions still passed).
    section = doc.split("## Metric definitions", 1)[1].split("\n## ", 1)[0]
    for mission in ("doc-sync", "test-coverage", "adversarial-review-and-fix"):
        for metric in MISSION_METRICS[mission]:
            assert f"`{metric}`" in section, f"{mission}:{metric} lacks a definition"
            # A definition is a dash-led entry with prose, not a bare mention.
            assert any(
                (s := line.strip()).startswith("- `")
                and len(s) > 40
                and (
                    s.startswith(f"- `{metric}`")
                    or f" / `{metric}`" in s.split(" — ", 1)[0]
                )
                for line in section.splitlines()
            ), f"{mission}:{metric} entry is not a definition"


def test_tier1_missions_carry_pr_sizing_heuristics() -> None:
    """Issue #100: the two Tier-1 workhorses must give a concrete PR unit and
    size bound, not one sentence of vibes."""
    for mission in ("doc-sync", "test-coverage"):
        text = (ROOT / "skills" / mission / "SKILL.md").read_text(encoding="utf-8")
        assert "PR sizing" in text, mission
        assert "400" in text, mission


def test_ledger_dir_env_override(monkeypatch) -> None:
    """Issue #101: mission ledger paths resolve through FLEET_LEDGER_DIR so
    docs-site repos can relocate fleet files out of the published tree."""
    from lib import mission_registry as mr

    monkeypatch.delenv("FLEET_LEDGER_DIR", raising=False)
    assert mr.progress_path("doc-sync").startswith("docs/")
    monkeypatch.setenv("FLEET_LEDGER_DIR", ".fleet/docs/")
    assert mr.progress_path("doc-sync") == ".fleet/docs/doc-sync-progress.md"
    assert mr.readiness_path("doc-sync") == ".fleet/docs/doc-sync-readiness.md"
    monkeypatch.setenv("FLEET_LEDGER_DIR", "")
    assert mr.progress_path("doc-sync").startswith("docs/")


def test_stop_verify_globs_follow_ledger_dir(monkeypatch) -> None:
    """#123 review: strict-mode evidence scans must follow the relocated
    ledger dir or evidence is silently missed."""
    import importlib
    from lib import stop_verify as sv

    monkeypatch.setenv("FLEET_LEDGER_DIR", ".fleet/docs")
    cfg = sv.StopVerifyConfig()
    assert cfg.progress_glob == ".fleet/docs/*-progress.md"
    monkeypatch.delenv("FLEET_LEDGER_DIR")
    cfg = sv.StopVerifyConfig()
    assert cfg.progress_glob == "docs/*-progress.md"


def test_validate_fleet_outcome_collects_relocated_readiness(tmp_path, monkeypatch) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "vfo", ROOT / "scripts" / "validate_fleet_outcome.py"
    )
    vfo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vfo)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a-readiness.md").write_text("x", encoding="utf-8")
    (tmp_path / ".fleet" / "docs").mkdir(parents=True)
    (tmp_path / ".fleet" / "docs" / "b-readiness.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("FLEET_LEDGER_DIR", ".fleet/docs")
    names = sorted(p.name for p in vfo.collect_readiness_paths(tmp_path))
    assert names == ["a-readiness.md", "b-readiness.md"]


def test_adapters_carry_honest_primitive_matrix() -> None:
    """Issue #93: every adapter states per-primitive real/degraded/absent
    status; the two hosts without ASK/REPLY must say 'absent', not present a
    fallback as the primitive."""
    for name in ("orca", "claude-code", "grok", "codex", "template"):
        text = (ROOT / "skills" / f"autonomous-fleet-adapter-{name}" / "SKILL.md").read_text(encoding="utf-8")
        assert "PRIMITIVE SUPPORT MATRIX" in text, name
    for name in ("grok", "codex"):
        text = (ROOT / "skills" / f"autonomous-fleet-adapter-{name}" / "SKILL.md").read_text(encoding="utf-8")
        assert "**absent**" in text, name
        assert "not the engine primitive" in text, name


def test_run_short_keys_ledger_filenames(monkeypatch) -> None:
    """Issue #96: FLEET_RUN_SHORT keys ledger names per run while keeping the
    *-progress.md shape every validator globs."""
    from lib import mission_registry as mr

    monkeypatch.delenv("FLEET_RUN_SHORT", raising=False)
    monkeypatch.delenv("FLEET_LEDGER_DIR", raising=False)
    base = mr.progress_path("doc-sync")
    monkeypatch.setenv("FLEET_RUN_SHORT", "3e8173")
    keyed = mr.progress_path("doc-sync")
    assert keyed == "docs/doc-sync-3e8173-progress.md"
    assert keyed.endswith("-progress.md")
    assert mr.readiness_path("doc-sync") == "docs/doc-sync-3e8173-readiness.md"
    monkeypatch.setenv("FLEET_RUN_SHORT", "NOT-HEX")
    assert mr.progress_path("doc-sync") == base


def test_resolve_readiness_prefers_newest_keyed_file(tmp_path, monkeypatch) -> None:
    """#129 round-2: campaign drivers must find the run-keyed readiness a run
    actually wrote, not the unkeyed path predicted pre-run."""
    import os as _os
    import time as _time
    from lib import mission_registry as mr

    monkeypatch.delenv("FLEET_RUN_SHORT", raising=False)
    monkeypatch.delenv("FLEET_LEDGER_DIR", raising=False)
    docs = tmp_path / "docs"
    docs.mkdir()
    assert mr.resolve_readiness_file("doc-sync", str(tmp_path)) == "docs/doc-sync-readiness.md"
    (docs / "doc-sync-readiness.md").write_text("old", encoding="utf-8")
    keyed = docs / "doc-sync-abc123-readiness.md"
    keyed.write_text("new", encoding="utf-8")
    _os.utime(keyed, (_time.time() + 5, _time.time() + 5))
    assert mr.resolve_readiness_file("doc-sync", str(tmp_path)) == "docs/doc-sync-abc123-readiness.md"
