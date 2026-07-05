"""Compose fleet run verification layers for one run archive directory."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .emit_trace import TraceScanStats, health_rollup, iter_trace_file, validate_event
from .fleet_outcome import parse_readiness, validate_outcome
from .fleet_run import load_and_validate_manifest, parse_run_id
from .verify_blind_fix import verify_blind_fix_doc
from .verify_findings import load_findings_doc, validate_findings_doc, verify_findings_doc

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

# Upper bound on trace events the verifier will load. A real run's trace is a
# few dozen events; in the CI-gate use case the run dir is attacker-controlled,
# so a hostile multi-million-event trace.jsonl must fail fast rather than
# exhaust memory. Module-level so tests can lower it.
MAX_TRACE_EVENTS = 100_000


@dataclass(frozen=True)
class LayerResult:
    name: str
    artifact: str
    status: str
    detail: str
    errors: tuple[str, ...] = ()
    data: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "name": self.name,
            "artifact": self.artifact,
            "status": self.status,
            "detail": self.detail,
            "errors": list(self.errors),
        }
        if self.data is not None:
            row["data"] = self.data
        return row


def _pass(name: str, artifact: str, detail: str, **data: Any) -> LayerResult:
    return LayerResult(name, artifact, PASS, detail, data=data or None)


def _fail(name: str, artifact: str, detail: str, errors: list[str]) -> LayerResult:
    return LayerResult(name, artifact, FAIL, detail, tuple(errors))


def _skip(name: str, artifact: str, detail: str) -> LayerResult:
    return LayerResult(name, artifact, SKIP, detail)


def _check_manifest(run_dir: Path) -> LayerResult:
    artifact = "manifest.json"
    if not (run_dir / artifact).exists():
        return _skip("run-archive", artifact, "artifact absent")
    try:
        payload, errors = load_and_validate_manifest(run_dir)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return _fail("run-archive", artifact, "manifest unreadable", [str(exc)])
    if errors:
        return _fail("run-archive", artifact, f"{len(errors)} manifest error(s)", errors)
    files = payload.get("files", []) if isinstance(payload, dict) else []
    declared_kinds = sorted(
        {
            entry["kind"]
            for entry in files
            if isinstance(entry, dict) and isinstance(entry.get("kind"), str)
        }
    )
    return _pass(
        "run-archive",
        artifact,
        f"{len(files)} files validated",
        files=len(files),
        declared_kinds=declared_kinds,
    )


def _check_findings(run_dir: Path, repo: Path) -> LayerResult:
    artifact = "p0-review-findings.json"
    path = run_dir / artifact
    if not path.exists():
        return _skip("findings", artifact, "artifact absent")
    try:
        doc = load_findings_doc(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return _fail("findings", artifact, "findings document unreadable", [str(exc)])
    errors = validate_findings_doc(doc, str(path))
    if errors:
        return _fail("findings", artifact, f"{len(errors)} schema error(s)", errors)
    summary = verify_findings_doc(doc, repo)
    total = summary.get("total_findings", 0)
    unverified = summary.get("unverified_findings", 0)
    if unverified:
        ids = ", ".join(summary.get("unverified_ids", []))
        return _fail(
            "findings",
            artifact,
            f"{unverified}/{total} finding(s) unverified",
            [f"unverified finding(s): {ids}"],
        )
    return _pass(
        "findings",
        artifact,
        f"{summary.get('verified_findings', 0)}/{total} findings verified",
        summary=summary,
    )


def _has_blind_fix_artifact(run_dir: Path, findings_doc: dict[str, Any]) -> bool:
    if any(run_dir.glob("reviewer-blind-fix-*.md")):
        return True
    if any(run_dir.glob("*/reviewer-blind-fix-*.md")):
        return True
    findings = findings_doc.get("findings") or []
    if not isinstance(findings, list):
        return False
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        chain = finding.get("blind_fix_chain")
        if isinstance(chain, dict) and str(chain.get("path") or "").strip():
            return True
    return False


def _check_blind_fix(run_dir: Path) -> LayerResult:
    artifact = "reviewer-blind-fix-*.md"
    findings_path = run_dir / "p0-review-findings.json"
    if not findings_path.exists():
        return _skip("blind-fix", artifact, "p0-review-findings.json absent")
    try:
        doc = load_findings_doc(findings_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return _fail("blind-fix", artifact, "findings prerequisite unreadable", [str(exc)])
    if not _has_blind_fix_artifact(run_dir, doc):
        return _skip("blind-fix", artifact, "artifact absent")
    summary = verify_blind_fix_doc(doc, run_dir=run_dir, findings_path=findings_path)
    total = summary.get("findings", 0)
    unverified = summary.get("unverified_blind_fix", 0)
    if unverified:
        errors = [
            f"{row['finding_id']}: {', '.join(row['reasons'])}"
            for row in summary.get("results", [])
            if not row.get("ok")
        ]
        return _fail("blind-fix", artifact, f"{unverified}/{total} blind-fix chain(s) invalid", errors)
    return _pass(
        "blind-fix",
        artifact,
        f"{summary.get('verified_blind_fix', 0)}/{total} blind-fix chains valid",
        summary=summary,
    )


def _check_outcome(run_dir: Path) -> LayerResult:
    artifact = "fleet-outcome.yaml"
    path = run_dir / artifact
    if not path.exists():
        return _skip("fleet-outcome", artifact, "artifact absent")
    try:
        outcome = parse_readiness(path)
        errors = validate_outcome(outcome, path)
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError) as exc:
        return _fail("fleet-outcome", artifact, "fleet-outcome unreadable", [str(exc)])
    if errors:
        return _fail("fleet-outcome", artifact, f"{len(errors)} outcome error(s)", errors)
    return _pass(
        "fleet-outcome",
        artifact,
        f"mission={outcome.get('mission')} status={outcome.get('status')}",
        mission=outcome.get("mission"),
        status=outcome.get("status"),
    )


def _check_trace(run_dir: Path) -> LayerResult:
    artifact = "trace.jsonl"
    path = run_dir / artifact
    if not path.exists():
        return _skip("trace", artifact, "artifact absent")
    stats = TraceScanStats()
    events: list[dict[str, Any]] = []
    try:
        for event in iter_trace_file(path, stats):
            events.append(event)
            if len(events) > MAX_TRACE_EVENTS:
                return _fail(
                    "trace",
                    artifact,
                    f"trace exceeds {MAX_TRACE_EVENTS} events (resource-exhaustion guard)",
                    [f"trace.jsonl exceeds the {MAX_TRACE_EVENTS}-event cap; refusing to load in full"],
                )
    except (OSError, UnicodeDecodeError) as exc:
        return _fail("trace", artifact, "trace unreadable", [str(exc)])
    errors: list[str] = []
    for index, event in enumerate(events, start=1):
        errors.extend(f"event {index}: {error}" for error in validate_event(event))
    if stats.skipped:
        errors.append(f"{stats.skipped} malformed JSON/non-object line(s)")
    if not events:
        errors.append("trace has no events")
    if errors:
        return _fail("trace", artifact, f"{len(errors)} trace error(s)", errors)
    rollup = health_rollup(events)
    return _pass(
        "trace",
        artifact,
        f"{rollup['total']} events valid; health {rollup['succeeded']} ok / {rollup['failed']} failed / {rollup['blocked']} blocked / {rollup['skipped']} skipped",
        health=rollup,
    )


def _check_identity(run_dir: Path) -> LayerResult:
    """Cross-bind run_id across artifacts to catch replayed/foreign evidence.

    Every run_id-bearing artifact (manifest, fleet-outcome, trace) must agree,
    and — when the directory name is itself a well-formed run_id — the dir must
    agree too. Fixture dirs (non-run_id names) bind by artifact agreement alone.
    """
    artifact = "run_id binding"
    sources: list[tuple[str, str]] = []
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            payload, errors = load_and_validate_manifest(run_dir)
        except (OSError, UnicodeDecodeError, ValueError):
            payload, errors = None, ["unreadable"]
        if not errors and isinstance(payload, dict) and isinstance(payload.get("run_id"), str):
            sources.append(("manifest", payload["run_id"]))
    outcome_path = run_dir / "fleet-outcome.yaml"
    if outcome_path.exists():
        try:
            outcome = parse_readiness(outcome_path)
            run_id = outcome.get("run_id") if isinstance(outcome, dict) else None
            if isinstance(run_id, str):
                sources.append(("fleet-outcome", run_id))
        except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError):
            pass
    trace_path = run_dir / "trace.jsonl"
    if trace_path.exists():
        try:
            seen: set[str] = set()
            for count, event in enumerate(iter_trace_file(trace_path), start=1):
                run_id = event.get("run_id")
                if isinstance(run_id, str):
                    seen.add(run_id)
                if len(seen) > 1 or count > MAX_TRACE_EVENTS:
                    break
            sources.extend(("trace", run_id) for run_id in sorted(seen))
        except (OSError, UnicodeDecodeError):
            pass
    try:
        parse_run_id(run_dir.name)
        sources.append(("dir-name", run_dir.name))
    except ValueError:
        pass
    if not sources:
        return _skip("identity", artifact, "no run_id-bearing artifacts")
    distinct = {run_id for _, run_id in sources}
    if len(distinct) > 1:
        return _fail(
            "identity",
            artifact,
            "run_id mismatch across artifacts (possible replayed evidence)",
            [f"{src}={run_id}" for src, run_id in sources],
        )
    return _pass(
        "identity",
        artifact,
        f"run_id consistent across {len(sources)} source(s)",
        run_id=next(iter(distinct)),
        sources=[src for src, _ in sources],
    )


def verify_layers(run_dir: Path, repo: Path) -> list[LayerResult]:
    manifest = _check_manifest(run_dir)
    findings = _check_findings(run_dir, repo)
    if (
        manifest.status == PASS
        and findings.status == SKIP
        and isinstance(manifest.data, dict)
        and "findings" in (manifest.data.get("declared_kinds") or ())
    ):
        findings = _fail(
            "findings",
            "p0-review-findings.json",
            "artifact absent but manifest declares findings artifact",
            [
                "manifest declares a kind='findings' artifact, but "
                "p0-review-findings.json is absent at the verifier path"
            ],
        )
    return [
        manifest,
        findings,
        _check_blind_fix(run_dir),
        _check_outcome(run_dir),
        _check_trace(run_dir),
        _check_identity(run_dir),
    ]


def _exit_code(layers: list[LayerResult]) -> int:
    ran = sum(layer.status != SKIP for layer in layers)
    if ran == 0:
        return 2 if ran == 0 else 0
    if layers and layers[0].name == "run-archive" and layers[0].status == SKIP:
        return 2
    if any(layer.status == FAIL for layer in layers):
        return 1
    return 0


def build_report(run_dir: Path, repo: Path, layers: list[LayerResult]) -> dict[str, Any]:
    counts = {status: sum(layer.status == status for layer in layers) for status in (PASS, FAIL, SKIP)}
    return {
        "run_dir": str(run_dir),
        "repo": str(repo),
        "exit_code": _exit_code(layers),
        "summary": counts,
        "layers": [layer.to_json() for layer in layers],
    }


def verify_run(run_dir: Path, repo: Path) -> dict[str, Any]:
    return build_report(run_dir, repo, verify_layers(run_dir, repo))


def format_table(layers: list[dict[str, Any]]) -> str:
    rows = [("Layer", "Artifact", "Status", "Detail")]
    rows.extend((row["name"], row["artifact"], row["status"], row["detail"]) for row in layers)
    widths = [max(len(str(row[index])) for row in rows) for index in range(4)]
    lines = ["  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row)).rstrip() for row in rows]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fleet-verify", description="Verify one autonomous-fleet run directory.")
    parser.add_argument("run_dir", type=Path, help="Path to .fleet/runs/<run_id>/")
    parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root for source verification")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a table")
    args = parser.parse_args(argv)

    if not args.run_dir.is_dir():
        print(f"fleet-verify: not a directory: {args.run_dir}", file=sys.stderr)
        return 2
    if not args.repo.is_dir():
        print(f"fleet-verify: --repo not a directory: {args.repo}", file=sys.stderr)
        return 2

    report = verify_run(args.run_dir, args.repo)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_table(report["layers"]), end="")
    return int(report["exit_code"])
