"""Instruction-budget gate (issue #87): composed surface vs recorded cap."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_instruction_budget as cib  # noqa: E402


def test_composed_surface_lists_mandatory_docs() -> None:
    surface = cib.composed_surface()
    assert "skills/autonomous-fleet-core/references/engine.md" in surface
    assert any("adapter" in k for k in surface)
    assert any(k.startswith("skills/") and k.endswith("SKILL.md") for k in surface)
    assert all(size > 0 for size in surface.values())


def test_check_passes_within_recorded_budget(capsys) -> None:
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 0
    out = capsys.readouterr().out
    assert "composed surface" in out


def test_check_fails_over_budget(tmp_path, monkeypatch, capsys) -> None:
    budget = tmp_path / "instruction-budget.json"
    budget.write_text(json.dumps({"max_bytes": 1}), encoding="utf-8")
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 1
    assert "OVER BUDGET" in capsys.readouterr().err


def test_unreadable_budget_fails(tmp_path, monkeypatch, capsys) -> None:
    budget = tmp_path / "instruction-budget.json"
    budget.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py"]
    assert cib.main() == 1
    assert "unreadable" in capsys.readouterr().err
    budget.unlink()
    assert cib.main() == 1


def test_update_records_current_plus_headroom(tmp_path, monkeypatch) -> None:
    budget = tmp_path / "instruction-budget.json"
    monkeypatch.setattr(cib, "BUDGET_FILE", budget)
    sys.argv = ["check_instruction_budget.py", "--update"]
    assert cib.main() == 0
    data = json.loads(budget.read_text(encoding="utf-8"))
    total = sum(cib.composed_surface().values())
    assert data["max_bytes"] == int(total * cib.UPDATE_HEADROOM)


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
