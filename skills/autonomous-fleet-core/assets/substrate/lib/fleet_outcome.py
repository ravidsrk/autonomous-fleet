"""Parse and validate fleet-outcome YAML frontmatter from readiness docs."""

from __future__ import annotations

import math
import re
import warnings
from pathlib import Path
from typing import Any

import yaml

from .fleet_registry import MISSIONS

REQUIRED_TOP = frozenset({"mission", "status", "repo", "base_branch", "prs_merged"})
VALID_STATUSES = frozenset({"done", "partial", "blocked"})
VALID_REVIEWER_MODES = frozenset(
    {
        "cross-vendor-structural",
        "same-vendor-instructed",
        "single-process-instructed",
    }
)
VALID_REVIEWER_MODES_TEXT = ", ".join(sorted(VALID_REVIEWER_MODES))
REVIEWER_MODE_MISSING_WARNING = (
    "reviewer_mode missing — recording the review topology is required for new runs"
)

MISSION_METRICS: dict[str, frozenset[str]] = {
    mission_id: frozenset(str(metric) for metric in row["metrics"])
    for mission_id, row in MISSIONS.items()
}
E2E_VERIFIED_MISSIONS = frozenset(
    {"take-product-to-completion", "legacy-rebuild"}
)
DONE_METRIC_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "doc-sync": {"drift_open": 0},
    "test-coverage": {"gaps_open": 0, "coverage_regressed": False},
    "dependency-update": {"advisories_open": 0},
    "cleanup": {"cleanup_items_open": 0},
    "bug-batch": {"bugs_open": 0},
    "adversarial-review-and-fix": {"p0_open": 0, "findings_open": 0},
    "targeted-migration": {"migration_items_open": 0, "old_axis_removed": True},
    "design-integration": {"parity_items_open": 0, "regressions": 0},
    "landing-page-convergence": {"divergences_open": 0},
    "legacy-rebuild": {"units_open": 0, "floor_preserved": True, "e2e_verified": True},
    "take-product-to-completion": {
        "in_items_open": 0,
        "stubs_remaining": 0,
        "e2e_verified": True,
    },
    "inference-cost": {
        "cost_regressed": False,
        "quality_regressed": False,
        "levers_open": 0,
    },
}
DONE_OPTIONAL_METRIC_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "adversarial-review-and-fix": {"unverified_findings": 0},
}


def _validate_task_row_invariants(
    task: dict[str, Any], prefix: str, index: int
) -> list[str]:
    errors: list[str] = []
    task_id = task.get("id", f"#{index}")
    label = f"{prefix}: task {task_id}"

    if task.get("merged") is True and task.get("built") is not True:
        errors.append(f"{label}: merged a task that never built")
    if task.get("merged") is True and task.get("wt_clean") is not True:
        errors.append(f"{label}: merged but worktree not clean")
    if task.get("reviewed") is True and task.get("pr_open") is not True:
        errors.append(f"{label}: reviewed before PR opened")

    return errors


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


VALID_DEGRADED_MODES = {"no_scm_auth"}


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

    degraded = outcome.get("degraded_mode")
    if degraded is not None and not isinstance(degraded, str):
        errors.append(f"{prefix}: degraded_mode must be a string when present")
    elif isinstance(degraded, str) and degraded not in VALID_DEGRADED_MODES:
        # Closed enum: a typo'd mode must not slip past the done-gate below.
        errors.append(
            f"{prefix}: unknown degraded_mode {degraded!r}; "
            f"valid: {sorted(VALID_DEGRADED_MODES)}"
        )
    if degraded == "no_scm_auth" and outcome.get("status") == "done":
        # engine-autonomy.md PRECONDITIONS (issue #97): an unauthenticated-gh run
        # detours to local merges — no PRs, no reviewer pass, no SHA-pin.
        # That run must not report an undifferentiated done.
        errors.append(
            f"{prefix}: cannot be done under degraded_mode 'no_scm_auth' — "
            "the PR/review pipeline never ran; report status 'partial'"
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
            if (
                mission in E2E_VERIFIED_MISSIONS
                and outcome.get("status") == "done"
                and metrics.get("e2e_verified") is not True
            ):
                errors.append(
                    f"{prefix}: cannot be done without end-to-end verification: "
                    "a green test suite is not proof a product works; "
                    "e2e_verified must be true (verify the real end-to-end "
                    "result state, not exit codes)"
                )
            if outcome.get("status") == "done":
                for mkey, expected in DONE_METRIC_REQUIREMENTS.get(mission, {}).items():
                    if metrics.get(mkey) != expected:
                        errors.append(
                            f"{prefix}: cannot be done while metric '{mkey}' is "
                            f"{metrics.get(mkey)!r}; expected {expected!r}"
                        )
                for mkey, expected in DONE_OPTIONAL_METRIC_REQUIREMENTS.get(
                    mission, {}
                ).items():
                    if mkey in metrics and metrics[mkey] != expected:
                        errors.append(
                            f"{prefix}: cannot be done while metric '{mkey}' is "
                            f"{metrics[mkey]!r}; expected {expected!r}"
                        )
            for mkey, mval in metrics.items():
                if isinstance(mval, bool):
                    continue
                if not isinstance(mval, (int, float)):
                    errors.append(
                        f"{prefix}: metric '{mkey}' must be numeric or bool, "
                        f"got {type(mval).__name__}"
                    )
                elif isinstance(mval, float) and not math.isfinite(mval):
                    errors.append(
                        f"{prefix}: metric '{mkey}' must be finite, got {mval!r}"
                    )

    deferred = outcome.get("deferred_missions")
    if deferred is not None and not isinstance(deferred, list):
        errors.append(f"{prefix}: deferred_missions must be a list")

    # Research discipline gate (optional, cross-cutting): every external fact the
    # build relied on must have a logged source. See engine-workers.md RESEARCH DISCIPLINE.
    for rkey in ("unverified_assumptions", "sources_logged"):
        if rkey in outcome:
            rval = outcome[rkey]
            if type(rval) is not int or rval < 0:
                errors.append(
                    f"{prefix}: {rkey} must be a non-negative int, got {rval!r}"
                )

    # Run-archive discipline telemetry (optional, cross-cutting): when a mission
    # has emitted ANY first-class artifact under .fleet/runs/<run_id>/, T-FINAL
    # records archive_enabled at the outcome level. true = manifest.json exists
    # and validate_run_archive.py passes (Commit 4 ARCHIVE_ENABLED HARD RULE).
    # Missions that emit no first-class artifacts (pure doc updates with no
    # findings/blind-fix/verifier outputs) OMIT the field. Lives at the top
    # level (not in metrics) because it's a discipline assertion, not a count
    # — mirrors the shape of `root_cause_audited`.
    if "archive_enabled" in outcome:
        ae = outcome["archive_enabled"]
        if not isinstance(ae, bool):
            errors.append(
                f"{prefix}: archive_enabled must be bool, "
                f"got {type(ae).__name__}"
            )
        # Hard precondition for status=done: a mission can't ship done with
        # archive_enabled=false — the audit trail is the discipline. This is
        # the only cross-cutting field that gates status=done from the
        # validator (root_cause_audited explicitly DOES NOT, by design — that
        # one lives in the SKILL prose because its semantics depend on whether
        # any RCD findings were filed). archive_enabled is unambiguous: if you
        # asserted it false, you're not done.
        elif ae is False and outcome.get("status") == "done":
            errors.append(
                f"{prefix}: cannot be done with archive_enabled=false: the "
                "run-archive manifest is the audit trail (engine-recovery.md "
                "ARCHIVE_ENABLED); a status=done without a passing archive "
                "is not auditable. Set status=partial instead, or fix the "
                "manifest so archive_enabled=true."
            )

    # Run-archive run_id reference (optional, cross-cutting). When the mission
    # produced a run-archive, T-FINAL records its run_id so post-hoc tools
    # (INFLATION POST-MORTEM, dashboards) can jump straight to the archive.
    # Validated via the same regex as fleet_run.RUN_ID_PATTERN; we don't import
    # that lib here to keep fleet_outcome standalone, so the regex is inlined.
    if "run_id" in outcome:
        rid = outcome["run_id"]
        if not isinstance(rid, str) or not re.match(
            r"^[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*[a-z0-9]-[0-9a-f]{6}$", rid
        ):
            errors.append(
                f"{prefix}: run_id must match "
                "YYYYMMDDTHHMMSSZ-<mission>-<6-hex>, got {rid!r}".format(rid=rid)
            )

    # Root-cause-depth audit telemetry (optional, cross-cutting): when a review
    # mission has reckoned with the ROOT_CAUSE_DEPTH discipline (review-findings.md), it
    # records the result at the outcome level. true = every root_cause_depth
    # finding had its cascade_impact paths re-EVIDed; false = at least one cascade
    # path was deferred. Optional so non-review missions don't need to assert it.
    # Lives at the top level (not in metrics) because it's a discipline assertion,
    # not a count — mirrors the shape of `sources_logged`.
    if "root_cause_audited" in outcome:
        rca = outcome["root_cause_audited"]
        if not isinstance(rca, bool):
            errors.append(
                f"{prefix}: root_cause_audited must be bool, "
                f"got {type(rca).__name__}"
            )

    # Cost routing telemetry (optional, cross-cutting): running spend estimate for
    # the run. May be fractional. See cost-routing.md MODEL & COST ROUTING.
    if "cost_estimate" in outcome:
        cval = outcome["cost_estimate"]
        if (
            isinstance(cval, bool)
            or not isinstance(cval, (int, float))
            or (isinstance(cval, float) and not math.isfinite(cval))
            or cval < 0
        ):
            errors.append(
                f"{prefix}: cost_estimate must be a non-negative finite number, got {cval!r}"
            )

    # Reviewer-mode disclosure (required for new runs, warning-only for
    # historical archives): which review topology the run actually used.
    # cross-vendor-structural = builder/reviewer split across vendor/model
    # families and separate processes/terminals (mechanical context barrier);
    # same-vendor-instructed = same vendor in a fresh reviewer session handed
    # only the diff + acceptance criteria; single-process-instructed = headless
    # or collapsed single-process review where blindness is prompt discipline,
    # not a mechanical process barrier. Lives at the top level (not in metrics)
    # because it's a disclosure assertion, not a count.
    if "reviewer_mode" in outcome:
        rmode = outcome["reviewer_mode"]
        if rmode not in VALID_REVIEWER_MODES:
            errors.append(
                f"{prefix}: invalid reviewer_mode {rmode!r}, "
                f"must be one of {VALID_REVIEWER_MODES_TEXT}"
            )
    else:
        warnings.warn(
            f"{prefix}: {REVIEWER_MODE_MISSING_WARNING}",
            UserWarning,
            stacklevel=2,
        )

    # Optional flat-ledger row invariants. The markdown ledger remains the
    # source of narrative loop memory; this only rejects impossible booleans
    # when a machine-readable task snapshot is present.
    tasks = outcome.get("tasks")
    if isinstance(tasks, list):
        for index, task in enumerate(tasks):
            if isinstance(task, dict):
                errors.extend(_validate_task_row_invariants(task, prefix, index))

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
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"non-finite operand: {value!r}")
        return result

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

    # Right operand is a SINGLE token anchored to end-of-string. A trailing token (a campaign-author
    # typo like `status == blocked now`) must NOT match here — it falls through to the
    # "unsupported expression" raise below so the edge is logged + skipped (the documented
    # do-not-guess contract), instead of == silently comparing against a multi-word string.
    m = re.match(r"([\w_]+)\s*(==|!=|>=|<=|>|<)\s*(\S+)\s*$", expr)
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
        # An edge whose expression references a missing metric (or is malformed) must NOT crash the
        # whole pick and strand a valid `if: always` fallback edge after it. Per the documented
        # "unknown expression -> skip edge, do not guess" rule, treat a raising edge as not-taken.
        try:
            matched = eval_edge(str(expr), outcome)
        except ValueError:
            continue
        if matched:
            to = edge.get("to")
            # A matched edge with no usable destination is a misconfigured campaign, not a terminal
            # node: fail loudly rather than returning None (which reads as "no edge matched / DONE").
            if not isinstance(to, str) or not to:
                raise ValueError(
                    f"matched edge on node {current_node!r} has no valid 'to': {edge!r}"
                )
            return to
    return None
