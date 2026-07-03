"""Cost-analysis library — aggregate operator-DECLARED cost estimates.

Reads readiness docs (``docs/*-readiness.md``) and totals the optional
``fleet-outcome.cost_estimate`` field. That field is an operator-typed
DECLARED ESTIMATE — there is no token/price model behind it, so the
aggregate is an estimate-aggregation, NOT a measured dollar spend. Output
labels carry an ``_estimate`` qualifier and a ``basis`` marker to keep that
distinction honest. Missing costs are counted as a declaration gap instead
of failing the analysis.

A non-zero ``cost_estimate`` may carry optional provenance fields
(``cost_estimate_source`` and ``cost_estimate_date``). Non-zero estimates
that lack both are tracked as ``estimates_without_provenance`` so the gap
is visible rather than silently treated as authoritative.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.fleet_outcome import parse_readiness, validate_outcome

#: Marks the aggregate as a sum of operator-declared estimates, not a
#: measured/metered dollar spend.
DECLARED_ESTIMATE_BASIS = "declared-estimate"


def _cost_estimate(outcome: dict[str, Any], errors: list[str]) -> float | None:
    if "cost_estimate" not in outcome:
        return None
    if any("cost_estimate" in error for error in errors):
        return None
    return float(outcome["cost_estimate"])


def per_run(paths: list[Path]) -> list[dict[str, Any]]:
    """Return one declared-estimate row per readiness doc."""
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
                "cost_estimate_source": outcome.get("cost_estimate_source"),
                "cost_estimate_date": outcome.get("cost_estimate_date"),
                "status": outcome.get("status"),
            }
        )
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate operator-declared cost estimates across readiness docs.

    The result is a sum of declared estimates (``basis`` =
    ``declared-estimate``), not a measured spend.
    """
    total_cost = 0.0
    by_mission: dict[str, float] = {}
    missing_cost = 0
    estimates_without_provenance = 0

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
        if cost_float > 0.0 and not (
            row.get("cost_estimate_source") or row.get("cost_estimate_date")
        ):
            estimates_without_provenance += 1

    # NOTE: output keys carry the ``_estimate`` qualifier (and a ``basis``
    # marker) so the result reads as a DECLARED-ESTIMATE aggregation, not a
    # measured spend. The internal accumulator names stay ``total_cost`` /
    # ``by_mission`` to keep the pinning mutation (analyze-cost-total-sum-off)
    # matching.
    return {
        "basis": DECLARED_ESTIMATE_BASIS,
        "total_cost_estimate": total_cost,
        "by_mission_estimate": dict(sorted(by_mission.items())),
        "runs": len(rows),
        "missing_cost": missing_cost,
        "estimates_without_provenance": estimates_without_provenance,
    }


def discover_readiness(docs_root: Path) -> list[Path]:
    """Return all readiness docs under docs_root."""
    docs_root = Path(docs_root)
    if not docs_root.is_dir():
        return []
    return sorted(docs_root.glob("*-readiness.md"))
