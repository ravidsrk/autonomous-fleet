"""Orca reference-runtime coverage — adapter must subsume fleet-relevant orchestration skill cases."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "skills" / "autonomous-fleet-adapter-orca" / "SKILL.md"
PLATFORM = ROOT / "skills" / "autonomous-fleet-adapter-orca" / "references" / "orca-platform.md"
README = ROOT / "README.md"
INSTALL_SCRIPT = ROOT / "scripts" / "install-skills.sh"


def read_adapter() -> str:
    return ADAPTER.read_text(encoding="utf-8")


def read_platform() -> str:
    return PLATFORM.read_text(encoding="utf-8")


def test_orca_is_declared_reference_runtime() -> None:
    text = read_adapter()
    assert "reference runtime" in text.lower()
    assert "reference-runtime" in text or "reference runtime" in text
    assert "structural" in text.lower() or "build-blind" in text.lower()


def test_orca_routes_full_handoff_to_orca_cli_without_lifecycle() -> None:
    text = read_adapter() + read_platform()
    assert "orca-cli" in text
    assert re.search(r"hand[\s-]?off", text, re.I)
    # Full handoff must explicitly forbid supervised lifecycle primitives.
    assert re.search(r"\*\*no\*\*.*`task-create`", text, re.I | re.S)
    assert re.search(r"\*\*no\*\*.*`dispatch --inject`", text, re.I | re.S)
    assert re.search(r"\*\*no\*\*.*`check --wait`", text, re.I | re.S)


def test_orca_supervised_path_uses_interactive_agents_not_codex_exec() -> None:
    text = read_adapter()
    assert "Do **not** use `codex exec`" in text
    assert "tui-idle" in text
    assert "`codex`" in text or "@codex" in text


def test_orca_wait_includes_merge_ready_and_checkpoint_discipline() -> None:
    text = read_adapter()
    assert "merge_ready" in text
    assert "checkpoint" in text.lower()
    assert "never kill a live worker" in text.lower()


def test_orca_documents_review_only_worker_done() -> None:
    text = read_adapter()
    assert re.search(r"review-only", text, re.I)
    assert re.search(r"does \*\*not\*\* authorize|not authorize", text, re.I)


def test_orca_platform_covers_custom_codex_model_handoff() -> None:
    text = read_platform()
    assert "model_reasoning_effort" in text
    assert "--no-parent" in text
    assert "--base-branch" in text or "base-branch" in text


def test_orca_platform_routing_table_covers_orchestration_skill_cases() -> None:
    text = read_platform()
    for phrase in (
        "orca-cli",
        "Computer Use",
        "supervised",
        "bare shell",
        "gate-create",
        "merge_ready",
    ):
        assert phrase in text, f"missing {phrase!r} in orca-platform.md"


def test_default_install_paths_ship_orca_adapter() -> None:
    readme = README.read_text(encoding="utf-8")
    install = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "autonomous-fleet-adapter-orca" in readme
    assert "autonomous-fleet-adapter-claude-code" not in readme.split("Step 1")[1].split("Step 2")[0]
    assert "autonomous-fleet-adapter-orca" in install
    assert "autonomous-fleet-adapter-grok" not in install or "Default: Orca" in install