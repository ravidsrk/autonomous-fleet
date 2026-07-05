"""Instruction-budget gate (issue #87): composed surface vs recorded cap."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_instruction_budget as cib  # noqa: E402


def _budget(*, max_bytes: int = 999_999, max_engine_core_lines: int = 300, refs: list[str] | None = None) -> dict:
    return {
        "max_bytes": max_bytes,
        "max_engine_core_lines": max_engine_core_lines,
        "trigger_loaded_references": list(refs if refs is not None else cib.ENGINE_TRIGGER_REFERENCES),
    }


def test_composed_surface_lists_mandatory_docs() -> None:
    surface = cib.composed_surface()
    assert "skills/autonomous-fleet-core/references/engine.md" in surface
    assert any("adapter" in k for k in surface)
    assert any(k.startswith("skills/") and k.endswith("SKILL.md") for k in surface)
    assert all(size > 0 for size in surface.values())


def test_engine_trigger_refs_are_registered_but_not_mandatory_surface() -> None:
    budget = json.loads(cib.BUDGET_FILE.read_text(encoding="utf-8"))
    refs = cib.trigger_loaded_references(budget)
    surface = cib.composed_surface()
    assert refs == cib.ENGINE_TRIGGER_REFERENCES
    assert cib.missing_registered_references(refs) == ()
    assert all(ref not in surface for ref in refs)


def test_trigger_loaded_references_rejects_malformed_budget() -> None:
    with pytest.raises(ValueError, match="trigger_loaded_references"):
        cib.trigger_loaded_references({"trigger_loaded_references": "not-a-list"})

def test_trigger_loaded_references_rejects_empty_budget_list() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        cib.trigger_loaded_references({"trigger_loaded_references": []})



def test_check_passes_within_recorded_budget(capsys) -> None:
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 0
    out = capsys.readouterr().out
    assert "composed surface" in out
    assert "engine.md" in out
    assert "registered trigger-loaded engine refs 4" in out


def test_check_fails_over_budget(tmp_path, monkeypatch, capsys) -> None:
    budget = tmp_path / "instruction-budget.json"
    budget.write_text(json.dumps(_budget(max_bytes=1)), encoding="utf-8")
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 1
    assert "OVER BUDGET" in capsys.readouterr().err


def test_check_fails_when_engine_core_regrows_past_line_cap(tmp_path, monkeypatch, capsys) -> None:
    budget = tmp_path / "instruction-budget.json"
    budget.write_text(json.dumps(_budget(max_engine_core_lines=1)), encoding="utf-8")
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 1
    assert "ENGINE CORE OVER LINE CAP" in capsys.readouterr().err


def test_check_fails_for_missing_registered_reference(tmp_path, monkeypatch, capsys) -> None:
    budget = tmp_path / "instruction-budget.json"
    budget.write_text(json.dumps(_budget(refs=["skills/autonomous-fleet-core/references/missing.md"])), encoding="utf-8")
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 1
    err = capsys.readouterr().err
    assert "registered trigger-loaded references missing" in err
    assert "missing.md" in err


def test_unreadable_budget_fails(tmp_path, monkeypatch, capsys) -> None:
    budget = tmp_path / "instruction-budget.json"
    budget.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 1
    assert "unreadable" in capsys.readouterr().err
    budget.unlink()
    assert cib.main() == 1


def test_non_object_budget_fails(tmp_path, monkeypatch, capsys) -> None:
    budget = tmp_path / "instruction-budget.json"
    budget.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 1
    assert "budget JSON must be an object" in capsys.readouterr().err


def test_update_records_current_plus_headroom_and_preserves_line_cap_and_refs(tmp_path, monkeypatch) -> None:
    budget = tmp_path / "instruction-budget.json"
    budget.write_text(
        json.dumps(
            _budget(
                max_engine_core_lines=275,
                refs=["skills/autonomous-fleet-core/references/custom-trigger.md"],
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py", "--update"]
    assert cib.main() == 0
    data = json.loads(budget.read_text(encoding="utf-8"))
    total = sum(cib.composed_surface().values())
    assert data["max_bytes"] == int(total * cib.UPDATE_HEADROOM)
    assert data["max_engine_core_lines"] == 275
    assert data["trigger_loaded_references"] == ["skills/autonomous-fleet-core/references/custom-trigger.md"]


def test_update_uses_defaults_for_non_object_or_malformed_existing_budget(tmp_path, monkeypatch) -> None:
    budget = tmp_path / "instruction-budget.json"
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)

    budget.write_text("[]", encoding="utf-8")
    sys.argv = ["check_instruction_budget.py", "--update"]
    assert cib.main() == 0
    data = json.loads(budget.read_text(encoding="utf-8"))
    assert data["max_engine_core_lines"] == cib.DEFAULT_ENGINE_CORE_MAX_LINES
    assert data["trigger_loaded_references"] == list(cib.ENGINE_TRIGGER_REFERENCES)

    # Malformed JSON (ValueError) — the except branch must fall back to defaults.
    budget.write_text("{not json", encoding="utf-8")
    sys.argv = ["check_instruction_budget.py", "--update"]
    assert cib.main() == 0
    data = json.loads(budget.read_text(encoding="utf-8"))
    assert data["max_engine_core_lines"] == cib.DEFAULT_ENGINE_CORE_MAX_LINES
    assert data["trigger_loaded_references"] == list(cib.ENGINE_TRIGGER_REFERENCES)

    # Absent file (OSError) — same fallback.
    budget.unlink()
    sys.argv = ["check_instruction_budget.py", "--update"]
    assert cib.main() == 0
    data = json.loads(budget.read_text(encoding="utf-8"))
    assert data["max_engine_core_lines"] == cib.DEFAULT_ENGINE_CORE_MAX_LINES

    assert cib._update_reference_list({"trigger_loaded_references": "bad"}) == list(cib.ENGINE_TRIGGER_REFERENCES)
    assert cib._update_reference_list({"trigger_loaded_references": []}) == list(cib.ENGINE_TRIGGER_REFERENCES)


def test_missing_adapter_or_mission_groups_are_skipped(tmp_path, monkeypatch) -> None:
    """Covers the empty-group branch: a tree with only the core docs composes
    without adapters/missions rather than crashing."""
    for rel in cib.CORE_MANDATORY:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x" * 10, encoding="utf-8")
    monkeypatch.setattr(cib, "ROOT", tmp_path)
    surface = cib.composed_surface()
    assert set(surface) == set(cib.CORE_MANDATORY)
    assert all(v == 10 for v in surface.values())
