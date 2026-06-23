"""Seat-analysis library — analyze.js-style "earns its seat" lens.

Reads a run-archive (``.fleet/runs/<run_id>/``) and computes per-run
contribution metrics. Aggregates across runs to surface roles or models
whose findings don't survive blind-fix at a meaningful rate.

Lineage: borrowable-patterns audit #7 (analyze.js "earns its seat" lens).
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Tiny epsilon to keep value-per-dollar finite when cost_estimate is 0.
COST_EPSILON = 0.01


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_yaml_outcome(path: Path) -> dict[str, Any] | None:
    """Read fleet-outcome.yaml.

    We avoid yaml imports here to keep the lib runtime-dep-free. The
    fleet-outcome shape only needs a few scalar fields (``run_id``,
    ``archive_enabled``, ``cost_estimate``), all line-grep-friendly.
    """
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    out: dict[str, Any] = {}
    for line in text.splitlines():
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.+?)\s*$", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2)
        # Strip inline comments and quotes.
        raw = re.sub(r"\s+#.*$", "", raw).strip().strip("'\"")
        if raw in ("true", "True"):
            out[key] = True
        elif raw in ("false", "False"):
            out[key] = False
        else:
            try:
                out[key] = float(raw) if "." in raw else int(raw)
            except ValueError:
                out[key] = raw
    return out


def _iter_trace_events(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None


def _decision_count(decisions_log: Path, decision: str) -> int:
    if not decisions_log.is_file():
        return 0
    try:
        text = decisions_log.read_text(encoding="utf-8")
    except OSError:
        return 0
    count = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("decision") == decision:
            count += 1
    return count


def analyze_run(run_dir: Path) -> dict[str, Any]:
    """Compute per-run contribution metrics for a single archive.

    Returns a dict with keys:
      run_dir, findings_emitted, findings_verified, findings_closed,
      findings_withdrawn_post_blind_fix, cost_estimate, value_per_dollar,
      wall_clock_to_freeze_s, wall_clock_to_all_closed_s,
      stop_verify_activations, parsable (bool: false if archive is too
      broken to score).
    """
    run_dir = Path(run_dir)
    findings_doc = _read_json(run_dir / "p0-review-findings.json")
    outcome = _read_yaml_outcome(run_dir / "fleet-outcome.yaml")

    findings_emitted = 0
    findings_verified = 0
    findings_closed = 0
    findings_withdrawn = 0

    if isinstance(findings_doc, dict):
        findings_list = findings_doc.get("findings") or []
        for f in findings_list:
            if not isinstance(f, dict):
                continue
            findings_emitted += 1
            if f.get("verified") is True:
                findings_verified += 1
                # Closed = verified AND a per-finding fix attestation exists.
                fid = f.get("id")
                if fid:
                    attestation = run_dir / f"p1-fix-attestation-{fid}.json"
                    legacy = run_dir / "p1-fix-attestation.json"
                    if attestation.is_file() or legacy.is_file():
                        findings_closed += 1
                # Withdrawn-post-blind-fix: blind_fix_chain.fixer_draft_sha
                # exists AND differs semantically from reviewer-quote. For
                # this scaffolding pass, we count any chain that DECLARES a
                # disagreement marker (presence of fixer_draft_sha differs
                # from integration_sha).
                chain = f.get("blind_fix_chain")
                if isinstance(chain, dict):
                    draft = chain.get("fixer_draft_sha")
                    integration = chain.get("integration_sha")
                    if draft and integration and draft != integration:
                        findings_withdrawn += 1

    cost_estimate = 0.0
    if isinstance(outcome, dict):
        raw_cost = outcome.get("cost_estimate", 0)
        try:
            cost_estimate = float(raw_cost)
        except (TypeError, ValueError):
            cost_estimate = 0.0

    value_per_dollar = findings_closed / max(cost_estimate, COST_EPSILON)

    # Trace-derived wall-clock metrics.
    events = list(_iter_trace_events(run_dir / "trace.jsonl"))
    first_ts: datetime | None = None
    freeze_ts: datetime | None = None
    last_commit_ts: datetime | None = None
    for event in events:
        ts = _parse_iso(event.get("ts"))
        if ts is None:
            continue
        if first_ts is None or ts < first_ts:
            first_ts = ts
        primitive = event.get("primitive")
        if primitive == "FREEZE" and (freeze_ts is None or ts < freeze_ts):
            freeze_ts = ts
        if primitive == "COMMIT" and (last_commit_ts is None or ts > last_commit_ts):
            last_commit_ts = ts

    wall_clock_to_freeze_s: float | None = None
    if first_ts is not None and freeze_ts is not None:
        wall_clock_to_freeze_s = (freeze_ts - first_ts).total_seconds()
    wall_clock_to_all_closed_s: float | None = None
    if first_ts is not None and last_commit_ts is not None:
        wall_clock_to_all_closed_s = (last_commit_ts - first_ts).total_seconds()

    stop_verify_activations = _decision_count(
        run_dir / "stop-verify-decisions.log", "block"
    )

    parsable = bool(findings_doc) or bool(outcome) or bool(events)

    return {
        "run_dir": str(run_dir),
        "findings_emitted": findings_emitted,
        "findings_verified": findings_verified,
        "findings_closed": findings_closed,
        "findings_withdrawn_post_blind_fix": findings_withdrawn,
        "cost_estimate": cost_estimate,
        "value_per_dollar": value_per_dollar,
        "wall_clock_to_freeze_s": wall_clock_to_freeze_s,
        "wall_clock_to_all_closed_s": wall_clock_to_all_closed_s,
        "stop_verify_activations": stop_verify_activations,
        "parsable": parsable,
    }


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-run results across many archives."""
    if not runs:
        return {
            "runs": 0,
            "findings_emitted_total": 0,
            "findings_verified_total": 0,
            "findings_closed_total": 0,
            "findings_withdrawn_total": 0,
            "cost_estimate_total": 0.0,
            "value_per_dollar_avg": 0.0,
            "stop_verify_activations_total": 0,
            "wall_clock_to_freeze_avg_s": None,
            "wall_clock_to_all_closed_avg_s": None,
        }

    findings_emitted = sum(r.get("findings_emitted", 0) for r in runs)
    findings_verified = sum(r.get("findings_verified", 0) for r in runs)
    findings_closed = sum(r.get("findings_closed", 0) for r in runs)
    findings_withdrawn = sum(
        r.get("findings_withdrawn_post_blind_fix", 0) for r in runs
    )
    cost_total = sum(r.get("cost_estimate", 0.0) for r in runs)
    vpd_values = [r.get("value_per_dollar", 0.0) for r in runs if r.get("parsable")]
    vpd_avg = sum(vpd_values) / len(vpd_values) if vpd_values else 0.0
    stop_verify_total = sum(r.get("stop_verify_activations", 0) for r in runs)

    def _avg(key: str) -> float | None:
        values = [r.get(key) for r in runs if r.get(key) is not None]
        if not values:
            return None
        return sum(values) / len(values)

    return {
        "runs": len(runs),
        "findings_emitted_total": findings_emitted,
        "findings_verified_total": findings_verified,
        "findings_closed_total": findings_closed,
        "findings_withdrawn_total": findings_withdrawn,
        "cost_estimate_total": cost_total,
        "value_per_dollar_avg": vpd_avg,
        "stop_verify_activations_total": stop_verify_total,
        "wall_clock_to_freeze_avg_s": _avg("wall_clock_to_freeze_s"),
        "wall_clock_to_all_closed_avg_s": _avg("wall_clock_to_all_closed_s"),
    }


def discover_runs(runs_root: Path) -> list[Path]:
    """Return all archive-shaped subdirectories under runs_root."""
    runs_root = Path(runs_root)
    if not runs_root.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir():
            continue
        # Heuristic: an archive has a manifest.json.
        if (child / "manifest.json").is_file():
            out.append(child)
    return out
