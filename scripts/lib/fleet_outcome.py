"""Parse and validate fleet-outcome YAML frontmatter from readiness docs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP = frozenset({"mission", "status", "repo", "base_branch", "prs_merged"})
VALID_STATUSES = frozenset({"done", "partial", "blocked"})

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
    "scaffold-align": frozenset(
        {"align_items_open", "check_green", "seam_frozen", "scaffold_ok"}
    ),
    "contract-first-build": frozenset(
        {"in_items_open", "roadmap_count", "stubs_remaining", "ops_queue_count"}
    ),
    "agents-layer": frozenset(
        {
            "migration_items_open",
            "seam_unwired_open",
            "old_axis_removed",
            "evals_passing",
            "deploy_pending_ops",
        }
    ),
}


def split_frontmatter(text: str) -> tuple[str | None, str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.lstrip("\ufeff \t\n\r")
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

    if "status" in outcome and outcome["status"] not in VALID_STATUSES:
        errors.append(
            f"{prefix}: invalid status {outcome['status']!r}, "
            "must be one of done, partial, blocked"
        )

    if "prs_merged" in outcome:
        prs_merged = outcome["prs_merged"]
        if type(prs_merged) is not int:
            errors.append(
                f"{prefix}: prs_merged must be int, got {type(prs_merged).__name__}"
            )

    mission = outcome.get("mission")
    if isinstance(mission, str) and mission and mission not in MISSION_METRICS:
        errors.append(f"{prefix}: unknown mission {mission!r}, not in MISSION_METRICS")

    if isinstance(mission, str) and mission in MISSION_METRICS:
        metrics = outcome.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{prefix}: mission '{mission}' requires metrics mapping")
        else:
            for mkey in MISSION_METRICS[mission]:
                if mkey not in metrics:
                    errors.append(f"{prefix}: metrics missing '{mkey}' for {mission}")
            for mkey, mval in metrics.items():
                if not isinstance(mval, (int, float, bool)):
                    errors.append(
                        f"{prefix}: metric '{mkey}' must be numeric or bool, "
                        f"got {type(mval).__name__}"
                    )

    deferred = outcome.get("deferred_missions")
    if deferred is not None and not isinstance(deferred, list):
        errors.append(f"{prefix}: deferred_missions must be a list")

    # Research discipline gate (optional, cross-cutting): every external fact the
    # build relied on must have a logged source. See engine.md RESEARCH DISCIPLINE.
    for rkey in ("unverified_assumptions", "sources_logged"):
        if rkey in outcome:
            rval = outcome[rkey]
            if type(rval) is not int or rval < 0:
                errors.append(
                    f"{prefix}: {rkey} must be a non-negative int, got {rval!r}"
                )

    # Cost routing telemetry (optional, cross-cutting): running spend estimate for
    # the run. May be fractional. See engine.md MODEL & COST ROUTING.
    if "cost_estimate" in outcome:
        cval = outcome["cost_estimate"]
        if isinstance(cval, bool) or not isinstance(cval, (int, float)) or cval < 0:
            errors.append(
                f"{prefix}: cost_estimate must be a non-negative number, got {cval!r}"
            )

    return errors


def _metric_value(outcome: dict[str, Any], name: str) -> Any:
    metrics = outcome.get("metrics") or {}
    if name in metrics:
        return metrics[name]
    if name in outcome:
        return outcome[name]
    return None


def _parse_right_operand(raw: str) -> Any:
    if raw in ("true", "false"):
        return raw == "true"
    stripped = raw.strip("\"'")
    if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
        return int(stripped)
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _coerce_for_ordering(left: Any, right: Any) -> tuple[float, float]:
    def to_float(value: Any) -> float:
        if isinstance(value, bool):
            return float(int(value))
        return float(value)

    return to_float(left), to_float(right)


def eval_edge(expr: str, outcome: dict[str, Any]) -> bool:
    expr = expr.strip()
    if expr == "always":
        return True

    m = re.match(r"deferred_missions\s+contains\s+(.+)$", expr)
    if m:
        target = m.group(1).strip()
        if len(target) >= 2 and target[0] == target[-1] and target[0] in ("'", '"'):
            target = target[1:-1]
        for item in outcome.get("deferred_missions") or []:
            if isinstance(item, dict) and item.get("id") == target:
                return True
            if isinstance(item, str) and item == target:
                return True
        return False

    m = re.match(r"([\w_]+)\s*(==|!=|>=|<=|>|<)\s*(.+)", expr)
    if m:
        key, op, raw = m.group(1), m.group(2), m.group(3).strip()
        left = _metric_value(outcome, key)
        if left is None:
            raise ValueError(
                f"metric {key!r} not found in outcome for edge {expr!r}"
            )
        right = _parse_right_operand(raw)
        if op in (">", "<", ">=", "<="):
            try:
                left_num, right_num = _coerce_for_ordering(left, right)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"cannot compare metric values numerically in edge {expr!r}: "
                    f"{left!r} {op} {right!r}"
                ) from exc
            ordering_ops = {
                ">": lambda a, b: a > b,
                "<": lambda a, b: a < b,
                ">=": lambda a, b: a >= b,
                "<=": lambda a, b: a <= b,
            }
            return bool(ordering_ops[op](left_num, right_num))
        equality_ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        return bool(equality_ops[op](left, right))

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