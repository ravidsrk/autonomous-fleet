"""Pure verifier for the review round-budget circuit breaker.

The trace stream is the source of truth for review-round exhaustion: once a
task has more than ``MAX_ROUNDS`` failed reviewer events, it must finish as
``GOAL_BLOCKED``/``blocked`` and must not ship through a successful merge.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

MAX_ROUNDS = 3


def verify_round_budget(
    events: Iterable[Mapping[str, Any]],
    *,
    max_rounds: int = MAX_ROUNDS,
) -> dict[str, Any]:
    """Return a summary of review round-budget violations for parsed events."""
    task_states: dict[str, dict[str, Any]] = {}
    for event in events:
        task_id = event.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            continue

        state = task_states.setdefault(
            task_id,
            {"failed_rounds": 0, "merge_succeeded": False, "terminal": None},
        )
        if event.get("role") == "REVIEWER" and event.get("status") == "failed":
            state["failed_rounds"] += 1

        primitive = event.get("primitive")
        status = event.get("status")
        if primitive in {"GOAL_BLOCKED", "MERGE"} and status in {"blocked", "succeeded"}:
            state["terminal"] = (primitive, status)
            if primitive == "MERGE" and status == "succeeded":
                state["merge_succeeded"] = True

    violations = []
    tasks = {}
    for task_id, state in sorted(task_states.items()):
        rounds = state["failed_rounds"]
        tasks[task_id] = {
            "failed_rounds": rounds,
            "merge_succeeded": state["merge_succeeded"],
            "terminal": state["terminal"],
        }
        if rounds <= max_rounds:
            continue
        if state["merge_succeeded"]:
            message = f"{task_id} ran {rounds} review rounds then MERGED without BLOCKED"
            violations.append({"task_id": task_id, "rounds": rounds, "message": message})
            continue
        if state["terminal"] == ("GOAL_BLOCKED", "blocked"):
            continue
        message = f"{task_id} ran {rounds} review rounds without terminal BLOCKED"
        violations.append({"task_id": task_id, "rounds": rounds, "message": message})

    return {
        "ok": not violations,
        "max_rounds": max_rounds,
        "checked_tasks": len(task_states),
        "tasks": tasks,
        "violations": violations,
    }
