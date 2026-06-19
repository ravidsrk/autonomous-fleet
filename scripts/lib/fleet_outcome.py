"""Parse and validate fleet-outcome YAML frontmatter from readiness docs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP = frozenset({"mission", "status", "repo", "base_branch", "prs_merged"})

MISSION_METRICS: dict[str, frozenset[str]] = {
    "doc-sync": frozenset({"drift_open", "code_bug_findings"}),
    "test-coverage": frozenset({"gaps_open", "coverage_regressed"}),
    "dependency-update": frozenset({"advisories_open", "majors_deferred"}),
    "cleanup": frozenset({"cleanup_items_open"}),
    "bug-batch": frozenset({"bugs_open", "bugs_skipped"}),
    "adversarial-review-and-fix": frozenset(
        {"p0_open", "p1_open", "findings_open", "ops_queue_count"}
    ),
    "targeted-migration": frozenset({"migration_items_open", "old_axis_removed"}),
    "design-integration": frozenset({"parity_items_open", "regressions"}),
    "landing-page-convergence": frozenset({"divergences_open"}),
    "legacy-rebuild": frozenset({"units_open", "floor_preserved"}),
    "take-product-to-completion": frozenset(
        {"in_items_open", "roadmap_count", "stubs_remaining"}
    ),
}


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    fm = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    return fm, body


def parse_readiness(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm, _body = split_frontmatter(text)
    if not fm:
        raise ValueError(f"{path}: missing YAML frontmatter")
    data = yaml.safe_load(fm)
    if not isinstance(data, dict) or "fleet-outcome" not in data:
        raise ValueError(f"{path}: frontmatter must contain fleet-outcome key")
    outcome = data["fleet-outcome"]
    if not isinstance(outcome, dict):
        raise ValueError(f"{path}: fleet-outcome must be a mapping")
    return outcome


def validate_outcome(outcome: dict[str, Any], path: Path | None = None) -> list[str]:
    errors: list[str] = []
    prefix = str(path) if path else "fleet-outcome"

    for key in REQUIRED_TOP:
        if key not in outcome:
            errors.append(f"{prefix}: missing required field '{key}'")

    mission = outcome.get("mission")
    if isinstance(mission, str) and mission in MISSION_METRICS:
        metrics = outcome.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{prefix}: mission '{mission}' requires metrics mapping")
        else:
            for mkey in MISSION_METRICS[mission]:
                if mkey not in metrics:
                    errors.append(f"{prefix}: metrics missing '{mkey}' for {mission}")

    deferred = outcome.get("deferred_missions")
    if deferred is not None and not isinstance(deferred, list):
        errors.append(f"{prefix}: deferred_missions must be a list")

    return errors


def _metric_value(outcome: dict[str, Any], name: str) -> Any:
    metrics = outcome.get("metrics") or {}
    if name in metrics:
        return metrics[name]
    if name in outcome:
        return outcome[name]
    return None


def eval_edge(expr: str, outcome: dict[str, Any]) -> bool:
    expr = expr.strip()
    if expr == "always":
        return True

    if expr.startswith("status =="):
        want = expr.split("==", 1)[1].strip()
        return str(outcome.get("status")) == want

    m = re.match(r"deferred_missions\s+contains\s+([\w-]+)", expr)
    if m:
        target = m.group(1)
        for item in outcome.get("deferred_missions") or []:
            if isinstance(item, dict) and item.get("id") == target:
                return True
        return False

    m = re.match(r"([\w_]+)\s*(==|!=|>=|<=|>|<)\s*(.+)", expr)
    if m:
        key, op, raw = m.group(1), m.group(2), m.group(3).strip()
        left = _metric_value(outcome, key)
        if raw in ("true", "false"):
            right: Any = raw == "true"
        elif raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
            right = int(raw)
        else:
            right = raw.strip("\"'")
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        if left is None:
            return False
        return bool(ops[op](left, right))

    raise ValueError(f"unsupported expression: {expr!r}")


def pick_next_node(
    campaign: dict[str, Any], current_node: str, outcome: dict[str, Any]
) -> str | None:
    edges = (campaign.get("edges") or {}).get(current_node) or []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        expr = edge.get("if", "always")
        if eval_edge(str(expr), outcome):
            return edge.get("to")
    return None