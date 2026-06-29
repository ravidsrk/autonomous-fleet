"""Orca reference-runtime coverage — adapter must subsume fleet-relevant orchestration skill cases."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "skills" / "autonomous-fleet-adapter-orca" / "SKILL.md"
PLATFORM = ROOT / "skills" / "autonomous-fleet-adapter-orca" / "references" / "orca-platform.md"


def read_adapter() -> str:
    return ADAPTER.read_text(encoding="utf-8")


def read_platform() -> str:
    return PLATFORM.read_text(encoding="utf-8")


def test_orca_is_declared_reference_runtime() -> None:
    text = read_adapter()
    assert "reference runtime" in text.lower()
    assert "reference-runtime" in text or "reference runtime" in text
    assert "structural" in text.lower() or "build-blind" in text.lower()


def test_orca_routes_full_handoff_to_orca_cli() -> None:
    text = read_adapter() + read_platform()
    assert "orca-cli" in text
    assert "hand off" in text.lower() or "handoff" in text.lower()
    assert "no" in text.lower() and "task-create" in text
    assert "dispatch --inject" in text or "dispatch --inject" in text


def test_orca_supervised_path_uses_interactive_agents_not_codex_exec() -> None:
    text = read_adapter()
    assert "codex exec" in text
    assert "Do **not** use `codex exec`" in text or "not" in text.lower() and "codex exec" in text
    assert "`codex`" in text or "codex" in text
    assert "tui-idle" in text


def test_orca_wait_includes_merge_ready_and_checkpoint_discipline() -> None:
    text = read_adapter()
    assert "merge_ready" in text
    assert "checkpoint" in text.lower()
    assert "never kill a live worker" in text.lower()


def test_orca_documents_review_only_worker_done() -> None:
    text = read_adapter()
    assert "Review-only" in text or "review-only" in text
    assert "does **not** authorize" in text or "not authorize" in text.lower()


def test_orca_platform_covers_custom_codex_model_handoff() -> None:
    text = read_platform()
    assert "model_reasoning_effort" in text or "model" in text
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