"""Cost-analysis library — aggregate fleet-outcome cost telemetry.

Reads readiness docs (``docs/*-readiness.md``) and totals the optional
``fleet-outcome.cost_estimate`` field. Missing costs are counted as a
measurement gap instead of failing the analysis.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.fleet_outcome import parse_readiness, validate_outcome


def _cost_estimate(outcome: dict[str, Any], errors: list[str]) -> float | None:
    if "cost_estimate" not in outcome:
        return None
    if any("cost_estimate" in error for error in errors):
        return None
    return float(outcome["cost_estimate"])


def per_run(paths: list[Path]) -> list[dict[str, Any]]:
    """Return one cost row per readiness doc."""
    rows: list[dict[str, Any]] = []
    for path in paths:
        path = Path(path)
        outcome = parse_readiness(path)
        errors = validate_outcome(outcome, path)
        rows.append(
            {
                "source": str(path),
                "mission": outcome.get("mission"),
                "cost_estimate": _cost_estimate(outcome, errors),
                "status": outcome.get("status"),
            }
        )
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate cost rows across readiness docs."""
    total_cost = 0.0
    by_mission: dict[str, float] = {}
    missing_cost = 0

    for row in rows:
        cost = row.get("cost_estimate")
        if cost is None:
            missing_cost += 1
            continue
        try:
            cost_float = float(cost)
        except (TypeError, ValueError):
            missing_cost += 1
            continue
        mission = str(row.get("mission") or "unknown")
        total_cost += cost_float
        by_mission[mission] = by_mission.get(mission, 0.0) + cost_float

    return {
        "total_cost": total_cost,
        "by_mission": dict(sorted(by_mission.items())),
        "runs": len(rows),
        "missing_cost": missing_cost,
    }


def discover_readiness(docs_root: Path) -> list[Path]:
    """Return all readiness docs under docs_root."""
    docs_root = Path(docs_root)
    if not docs_root.is_dir():
        return []
    return sorted(docs_root.glob("*-readiness.md"))
