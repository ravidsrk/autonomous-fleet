"""Run-archive primitives for the autonomous fleet.

Every run that emits first-class artifacts (findings JSONs, verifier summaries,
blind-fix files, prompts, responses, diffs, readiness docs) lives under a single
directory: `.fleet/runs/<run_id>/`, with a `manifest.json` listing every file
the run produced. See engine.md ARCHIVE_ENABLED for the doctrine; this module
is the enforcement surface.

Three responsibilities:

1. `allocate_run_id(mission)` — produce a deterministic, sortable, greppable,
   per-run unique run_id. Format: `YYYYMMDDTHHMMSSZ-<mission>-<6-hex>`. The
   6-hex hash is derived from (timestamp + mission + pid) so concurrent runs
   on the same coordinator don't collide.

2. `write_manifest(archive_dir, ...)` — given an archive directory full of
   accreted artifacts and metadata about who produced what, walk the directory,
   compute sha256 + size + mtime per file, and emit a manifest.json conforming
   to fleet-run-manifest.schema.json.

3. `validate_manifest(archive_dir)` — the inverse: load manifest.json, verify
   the schema, verify every file exists and its checksum + size match, and
   verify the cross-cutting mtime-ordering invariants from engine.md
   ARCHIVE_ENABLED HARD RULE on mtime ordering:
       - blind_fix mtime < findings mtime (per producer)
       - verify_summary mtime > findings mtime
       - readiness mtime = max(mtime for all files)

The validator is the discipline. A manifest that passes the schema but
violates the ordering invariants FAILS validation — the engine's doctrine
is not "files exist", it's "files exist in the order the discipline demands".

Lib stays jsonschema-free (matches verify_findings.py convention). Schema
agreement is asserted by a test that compares lib constants to schema enum
values; drift is caught at test time, not runtime.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:  # pragma: no cover
    from .emit_trace import TraceEmitter

# ───────────────────────────────────────────────────────────────────────
# Pinned constants. The schema is authoritative; these mirror its enums
# and patterns. test_run_archive.py asserts agreement.
# ───────────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0"

VALID_KINDS = frozenset(
    {
        "findings",
        "verify_summary",
        "blind_fix",
        "prompt",
        "response",
        "diff",
        "readiness",
        "progress",
        "other",
    }
)

# Run-id regex. Mirrored from the schema. The mission-slug portion is
# constrained the same way (lowercase, hyphen-separated, ends alphanumerically)
# because mission slugs are also used as filename fragments downstream.
RUN_ID_PATTERN = re.compile(
    r"^[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*[a-z0-9]-[0-9a-f]{6}$"
)

# UTC ISO 8601 with optional fractional seconds, always Z-terminated.
UTC_ISO_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$"
)

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# Mission slug regex (used by run-id allocator). Must match the same shape
# as fleet_outcome.MISSION_METRICS keys. We don't import that here to keep
# this module standalone, but the test cross-checks.
MISSION_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")


# ───────────────────────────────────────────────────────────────────────
# Shapes
# ───────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FileEntry:
    """One file in the manifest. Mirrors $defs.file_entry in the schema."""

    path: str
    kind: str
    sha256: str
    mtime_utc: str
    producer: str
    bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "sha256": self.sha256,
            "mtime_utc": self.mtime_utc,
            "producer": self.producer,
            "bytes": self.bytes,
        }


# ───────────────────────────────────────────────────────────────────────
# Run-id allocation
# ───────────────────────────────────────────────────────────────────────


def _utc_now() -> datetime:
    """Indirected so tests can monkeypatch it. Always tz-aware UTC."""
    return datetime.now(timezone.utc)


def _timestamp_part(now: datetime) -> str:
    """YYYYMMDDTHHMMSSZ — sortable, filesystem-safe."""
    return now.strftime("%Y%m%dT%H%M%SZ")


def allocate_run_id(mission: str, *, now: datetime | None = None) -> str:
    """Allocate a deterministic-format run_id for the given mission.

    The 6-hex suffix uses os.urandom (via secrets) rather than a hash of
    pid+timestamp because: (a) two runs on the same coordinator-pid within
    the same second would collide on a hash, (b) urandom is the standard
    UUID-substitute primitive across the stdlib. Sort order is preserved
    by the timestamp prefix; the suffix is purely for collision avoidance.
    """
    if not isinstance(mission, str) or not MISSION_SLUG_PATTERN.match(mission):
        raise ValueError(
            f"mission slug must be lowercase kebab-case, got {mission!r}"
        )
    now = now if now is not None else _utc_now()
    ts = _timestamp_part(now)
    suffix = secrets.token_hex(3)  # 3 bytes = 6 hex chars
    run_id = f"{ts}-{mission}-{suffix}"
    # Self-consistency check: if this ever fails, the regex and the format
    # string have drifted. Cheap to verify and prevents shipping bad ids.
    # Defensive; should be unreachable unless someone edits the regex or the
    # format string without updating the other. # pragma: no cover
    if not RUN_ID_PATTERN.match(run_id):  # pragma: no cover
        raise RuntimeError(f"allocated run_id failed self-check: {run_id!r}")
    return run_id


def parse_run_id(run_id: str) -> tuple[datetime, str, str]:
    """Reverse of allocate_run_id. Returns (timestamp, mission, suffix).

    Used by INFLATION POST-MORTEM and the validator to sort runs by time
    and group by mission without re-reading every manifest.
    """
    m = RUN_ID_PATTERN.match(run_id)
    if not m:
        raise ValueError(f"not a valid run_id: {run_id!r}")
    ts_str, _, rest = run_id.partition("-")
    # rest is "<mission>-<6-hex>"; mission may itself contain hyphens.
    suffix = rest[-6:]
    mission = rest[: -len(suffix) - 1]  # strip "-<suffix>"
    ts = datetime.strptime(ts_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return ts, mission, suffix


# ───────────────────────────────────────────────────────────────────────
# Archive directory helpers
# ───────────────────────────────────────────────────────────────────────


def archive_dir(repo_root: Path, run_id: str, runs_root: str = ".fleet/runs") -> Path:
    """Canonical archive directory for `run_id` under `repo_root`.

    Does NOT create the directory; callers do that explicitly so the lib
    has no filesystem side-effects on import.
    """
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError(f"refusing to compute archive_dir for invalid run_id: {run_id!r}")
    return (repo_root / runs_root / run_id).resolve()


def ensure_archive_dir(
    repo_root: Path, run_id: str, runs_root: str = ".fleet/runs"
) -> Path:
    """Create the archive dir if it doesn't exist; return its absolute path.

    Idempotent. Used by workers/reviewers at the start of a run.
    """
    d = archive_dir(repo_root, run_id, runs_root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def emit_worker_commit_lifeline(
    emitter: "TraceEmitter",
    *,
    task_id: str,
    worker_role: str,
) -> tuple[str, str]:
    """Emit the reference worker causal edge: SPAWN_WORKER -> COMMIT."""
    spawn_event_id = emitter.emit(
        "SPAWN_WORKER",
        "COORDINATOR",
        "started",
        task_id=task_id,
    )
    commit_event_id = emitter.emit(
        "COMMIT",
        worker_role,
        "succeeded",
        task_id=task_id,
        parent_event=spawn_event_id,
    )
    return spawn_event_id, commit_event_id


def progress_excerpt_for_mission(source_root: Path, mission: str) -> str:
    """Return a verbatim slice from docs/<mission>-progress.md when present."""
    text = progress_text_for_mission(source_root, mission)
    return text[:2500] if len(text) > 2500 else text


def progress_text_for_mission(source_root: Path, mission: str) -> str:
    """Return full progress doc text (or synthetic fallback) for trace planning."""
    from .mission_registry import progress_path

    path = source_root / progress_path(mission)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return (
        f"# headless dry-run\n"
        f"MISSION: {mission}\n"
        f"PHASE: mechanical validation (no progress doc on disk)\n"
    )


@dataclass(frozen=True)
class ProgressTracePlan:
    """Trace transition hints parsed from a verbatim mission progress excerpt."""

    task_id: str
    runtime: str
    inspect_status: str
    merge_status: str
    goal_blocked_status: str
    note: str


def plan_dryrun_trace_from_progress(
    progress: str,
    *,
    mission: str,
    runtime: str,
) -> ProgressTracePlan:
    """Derive per-primitive statuses from progress-doc signals (TASK, PHASE, ledger flags)."""
    task_m = re.search(r"(?:^|\n)TASK\s+([^\s|]+)", progress)
    task_id = task_m.group(1) if task_m else f"headless-{mission}-1"

    phase_matches = re.findall(r"PHASE:\s*(\S+)", progress, re.I)
    phase = phase_matches[-1].upper() if phase_matches else ""
    goal_blocked_status = "skipped" if phase == "DONE" else "started"

    reviewed_m = re.search(r"REVIEWED=(t|f)", progress, re.I)
    inspect_status = (
        "succeeded"
        if reviewed_m and reviewed_m.group(1).lower() == "t"
        else "started"
    )

    merged_m = re.search(r"MERGED=(t|f)", progress, re.I)
    merge_status = (
        "succeeded"
        if merged_m and merged_m.group(1).lower() == "t"
        else "started"
    )

    mission_m = re.search(r"MISSION:\s*(\S+)", progress)
    mission_slug = mission_m.group(1) if mission_m else mission
    note = (
        f"progress excerpt MISSION:{mission_slug} "
        f"PHASE:{phase or 'unknown'} via {runtime}"
    )

    return ProgressTracePlan(
        task_id=task_id,
        runtime=runtime,
        inspect_status=inspect_status,
        merge_status=merge_status,
        goal_blocked_status=goal_blocked_status,
        note=note,
    )


def emit_dryrun_lifecycle_trace(
    emitter: "TraceEmitter",
    *,
    mission: str = "doc-sync",
    task_id: str | None = None,
    runtime: str = "grok",
    progress_excerpt: str | None = None,
    include_t_final: bool = False,
    manifest_name: str = "manifest.json",
    file_count: int = 2,
    goal_blocked_status: str = "skipped",
    abort_status: str = "skipped",
) -> dict[str, str]:
    """Orchestrate all 11 engine trace transitions for one headless dry-run unit.

    When ``progress_excerpt`` is set, task_id and per-primitive statuses are
    derived from ledger signals in the excerpt (TASK / PHASE / REVIEWED / MERGED).
    Otherwise the caller-supplied synthetic defaults apply.

    T-FINAL is omitted when write_manifest will emit it (trace-before-ledger).
    """
    if progress_excerpt:
        plan = plan_dryrun_trace_from_progress(
            progress_excerpt, mission=mission, runtime=runtime
        )
        task_id = plan.task_id
        goal_blocked_status = plan.goal_blocked_status
        inspect_status = plan.inspect_status
        merge_status = plan.merge_status
        note = plan.note
    else:
        task_id = task_id or f"headless-{mission}-1"
        note = f"headless dry-run via {runtime}"
        inspect_status = "succeeded"
        merge_status = "succeeded"

    ids: dict[str, str] = {}
    ids["dispatch"] = emitter.emit("DISPATCH", "COORDINATOR", "started", task_id=task_id)
    ids["spawn"] = emitter.emit(
        "SPAWN_WORKER",
        "COORDINATOR",
        "started",
        task_id=task_id,
        parent_event=ids["dispatch"],
    )
    ids["wait"] = emitter.emit("WAIT", "COORDINATOR", "started", task_id=task_id)
    ids["goal_blocked"] = emitter.emit(
        "GOAL_BLOCKED",
        "COORDINATOR",
        goal_blocked_status,
        task_id=task_id,
        details={"reason": note},
    )
    ids["inspect"] = emitter.emit(
        "INSPECT",
        "REVIEWER",
        inspect_status,
        task_id=task_id,
        parent_event=ids["spawn"],
    )
    ids["sync"] = emitter.emit("SYNC", "COORDINATOR", "succeeded", task_id=task_id)
    ids["merge"] = emitter.emit("MERGE", "INTEGRATOR", merge_status, task_id=task_id)
    ids["freeze"] = emitter.emit("FREEZE", "COORDINATOR", "succeeded")
    ids["commit"] = emitter.emit(
        "COMMIT",
        "FIXER",
        "succeeded",
        task_id=task_id,
        parent_event=ids["spawn"],
    )
    ids["abort"] = emitter.emit(
        "ABORT",
        "COORDINATOR",
        abort_status,
        task_id=task_id,
        details={"reason": f"compensation path not taken ({note})"},
    )
    if include_t_final:
        ids["t_final"] = emitter.emit(
            "T-FINAL",
            "INTEGRATOR",
            "succeeded",
            details={"manifest": manifest_name, "files": file_count},
        )
    return ids


def write_headless_dryrun_archive(
    repo_root: Path,
    *,
    mission: str,
    runtime: str = "grok",
    progress_source_root: Path | None = None,
) -> tuple[Path, str, list[str]]:
    """Emit archive under repo_root/.fleet/runs/<run_id>/ with full lifecycle trace.

    progress_source_root defaults to repo_root; pass fleet_root when --repo
    targets an external checkout but progress excerpts live in this clone.
    Archives are always written to disk; shell entry points remove ephemeral
    copies only on --dry-run (see run-mission-headless.sh).
    Returns (archive_dir, run_id, sorted primitive names).
    """
    from .emit_trace import TraceEmitter, iter_trace_file

    source = progress_source_root if progress_source_root is not None else repo_root
    run_id = allocate_run_id(mission)
    arch = ensure_archive_dir(repo_root, run_id)

    progress_archive = progress_excerpt_for_mission(source, mission)
    progress_parse = progress_text_for_mission(source, mission)
    progress_path = arch / "headless-dryrun-progress.md"
    progress_path.write_text(progress_archive, encoding="utf-8")

    with TraceEmitter(arch, mission=mission, run_id=run_id) as emitter:
        emit_dryrun_lifecycle_trace(
            emitter,
            mission=mission,
            progress_excerpt=progress_parse,
            runtime=runtime,
            include_t_final=False,
        )
        trace_path = arch / "trace.jsonl"
        entries = [
            file_entry_for(
                progress_path,
                arch,
                kind="progress",
                producer=f"headless-dryrun-{runtime}",
            ),
            file_entry_for(
                trace_path,
                arch,
                kind="other",
                producer="coordinator",
            ),
        ]
        write_manifest(
            arch,
            run_id=run_id,
            mission=mission,
            files=entries,
            coordinator=f"headless-dryrun-{runtime}",
            base_branch="main",
            notes=(
                "Mechanical headless dry-run archive "
                "(progress excerpt + fleet_run lifecycle trace)."
            ),
            emitter=emitter,
        )

    primitives = sorted({e["primitive"] for e in iter_trace_file(trace_path)})
    return arch, run_id, primitives


def record_headless_run(
    repo_root: Path,
    *,
    mission: str,
    runtime: str = "grok",
    progress_source_root: Path | None = None,
) -> tuple[Path, str, list[str]]:
    """Persist a headless run archive (alias for write_headless_dryrun_archive)."""
    return write_headless_dryrun_archive(
        repo_root,
        mission=mission,
        runtime=runtime,
        progress_source_root=progress_source_root,
    )


# ───────────────────────────────────────────────────────────────────────
# Manifest writing
# ───────────────────────────────────────────────────────────────────────


def _sha256_file(path: Path) -> str:
    """Stream-hash a file. Avoids loading large prompts/responses into RAM."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc_from_mtime(mtime: float) -> str:
    """Round to second resolution (matches manifest schema pattern; sub-second
    drift is irrelevant for our ordering invariants which are minutes apart)."""
    return (
        datetime.fromtimestamp(mtime, tz=timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def file_entry_for(
    file_path: Path, archive_root: Path, *, kind: str, producer: str
) -> FileEntry:
    """Build a FileEntry for `file_path` inside `archive_root`.

    Raises ValueError if `kind` is invalid OR if `file_path` is not a child
    of `archive_root` (the manifest indexes a directory, not the wider
    filesystem; path-escape attempts are rejected at construction time).
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(VALID_KINDS)}, got {kind!r}")
    if not isinstance(producer, str) or not producer.strip():
        raise ValueError("producer must be a non-empty string")
    archive_root = archive_root.resolve()
    abs_file = file_path.resolve()
    try:
        rel = abs_file.relative_to(archive_root)
    except ValueError as exc:
        raise ValueError(
            f"file {abs_file} is not inside archive root {archive_root}"
        ) from exc
    stat = abs_file.stat()
    return FileEntry(
        path=str(rel).replace(os.sep, "/"),
        kind=kind,
        sha256=_sha256_file(abs_file),
        mtime_utc=_utc_from_mtime(stat.st_mtime),
        producer=producer.strip(),
        bytes=stat.st_size,
    )


def write_manifest(
    archive_root: Path,
    *,
    run_id: str,
    mission: str,
    files: Iterable[FileEntry],
    coordinator: str | None = None,
    base_branch: str | None = None,
    notes: str | None = None,
    created_utc: datetime | None = None,
    emitter: TraceEmitter | None = None,
) -> Path:
    """Emit `archive_root/manifest.json` from the given file entries.

    Cross-checks: run_id matches the regex; mission matches the run_id slug;
    files is non-empty; manifest's `created_utc` is no later than any file's
    mtime (the manifest is created at the START of the run; if it's somehow
    newer than a listed file we caught a clock-skew bug).
    """
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError(f"invalid run_id for manifest: {run_id!r}")
    _, parsed_mission, _ = parse_run_id(run_id)
    if mission != parsed_mission:
        raise ValueError(
            f"mission {mission!r} does not match run_id slug {parsed_mission!r}"
        )

    file_list = list(files)
    if not file_list:
        raise ValueError("manifest requires at least one file entry")

    created = (created_utc or _utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    created_str = created.strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest_path = archive_root / "manifest.json"
    # Doctrine (engine.md TRACE EMISSION): trace first, ledger second — never the reverse,
    # or a crash leaves the manifest on disk with no externally-visible cause. Emit BEFORE write.
    if emitter is not None:
        emitter.emit(
            "T-FINAL",
            "INTEGRATOR",
            "succeeded",
            details={"manifest": manifest_path.name, "files": len(file_list)},
        )
        # T-FINAL appends to trace.jsonl after callers built file entries — refresh checksum.
        refreshed: list[FileEntry] = []
        for fe in file_list:
            if fe.path == "trace.jsonl":
                refreshed.append(
                    file_entry_for(
                        archive_root / "trace.jsonl",
                        archive_root,
                        kind=fe.kind,
                        producer=fe.producer,
                    )
                )
            else:
                refreshed.append(fe)
        file_list = refreshed

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mission": mission,
        "created_utc": created_str,
        "files": [fe.to_dict() for fe in file_list],
    }
    if coordinator is not None:
        payload["coordinator"] = coordinator
    if base_branch is not None:
        payload["base_branch"] = base_branch
    if notes is not None:
        payload["notes"] = notes

    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


# ───────────────────────────────────────────────────────────────────────
# Manifest validation — schema-shape + mtime ordering invariants
# ───────────────────────────────────────────────────────────────────────


def _validate_shape(manifest: dict[str, Any], where: str) -> list[str]:
    """Re-implement the JSON Schema constraints in Python (matches the
    verify_findings.py pattern — keeps the lib runtime-dep-free)."""
    errors: list[str] = []

    if not isinstance(manifest, dict):
        return [f"{where}: manifest must be an object"]

    required = ["schema_version", "run_id", "mission", "created_utc", "files"]
    for key in required:
        if key not in manifest:
            errors.append(f"{where}: missing required field {key!r}")

    sv = manifest.get("schema_version")
    if sv is not None and sv != SCHEMA_VERSION:
        errors.append(
            f"{where}: schema_version must be {SCHEMA_VERSION!r}, got {sv!r}"
        )

    run_id = manifest.get("run_id")
    if isinstance(run_id, str) and not RUN_ID_PATTERN.match(run_id):
        errors.append(f"{where}: run_id {run_id!r} does not match required format")

    mission = manifest.get("mission")
    if isinstance(mission, str) and isinstance(run_id, str) and RUN_ID_PATTERN.match(run_id):
        _, parsed_mission, _ = parse_run_id(run_id)
        if mission != parsed_mission:
            errors.append(
                f"{where}: mission {mission!r} does not match run_id slug "
                f"{parsed_mission!r}"
            )

    created = manifest.get("created_utc")
    if isinstance(created, str) and not UTC_ISO_PATTERN.match(created):
        errors.append(f"{where}: created_utc {created!r} not a valid UTC ISO 8601")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        errors.append(f"{where}: files must be a non-empty list")
        return errors

    for idx, entry in enumerate(files):
        ewhere = f"{where}.files[{idx}]"
        if not isinstance(entry, dict):
            errors.append(f"{ewhere}: must be an object")
            continue
        for field in ("path", "kind", "sha256", "mtime_utc", "producer", "bytes"):
            if field not in entry:
                errors.append(f"{ewhere}: missing field {field!r}")

        path = entry.get("path")
        if isinstance(path, str):
            if path.startswith("/") or ".." in Path(path).parts:
                errors.append(f"{ewhere}: path {path!r} escapes archive directory")

        kind = entry.get("kind")
        if isinstance(kind, str) and kind not in VALID_KINDS:
            errors.append(
                f"{ewhere}: kind {kind!r} not in {sorted(VALID_KINDS)}"
            )

        sha = entry.get("sha256")
        if isinstance(sha, str) and not SHA256_PATTERN.match(sha):
            errors.append(f"{ewhere}: sha256 must be 64 hex chars")

        mtime = entry.get("mtime_utc")
        if isinstance(mtime, str) and not UTC_ISO_PATTERN.match(mtime):
            errors.append(f"{ewhere}: mtime_utc not a valid UTC ISO 8601")

        producer = entry.get("producer")
        if not (isinstance(producer, str) and producer.strip()):
            errors.append(f"{ewhere}: producer must be a non-empty string")

        bytes_ = entry.get("bytes")
        if not (isinstance(bytes_, int) and not isinstance(bytes_, bool) and bytes_ >= 0):
            errors.append(f"{ewhere}: bytes must be a non-negative int")

    return errors


def _validate_ordering(files: list[dict[str, Any]], where: str) -> list[str]:
    """Enforce the cross-cutting mtime-ordering invariants from engine.md
    ARCHIVE_ENABLED HARD RULE on mtime ordering. These ARE the Commits 1-3
    disciplines made auditable; a schema-clean manifest that violates them
    is still doctrine-broken."""
    errors: list[str] = []

    # Parse mtimes once. Skip entries that didn't validate at the shape level
    # (their mtime might be missing/malformed; shape errors will already be
    # reported and we don't double-report). Also skip non-dict entries — the
    # shape check has already reported them, and treating them as ordering
    # input would raise AttributeError on `.get`.
    by_kind: dict[str, list[tuple[str, str, datetime]]] = {}
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path", "")
        producer = entry.get("producer", "")
        kind = entry.get("kind", "")
        mtime_str = entry.get("mtime_utc", "")
        if (
            not isinstance(kind, str)
            or kind not in VALID_KINDS
            or not isinstance(mtime_str, str)
            or not UTC_ISO_PATTERN.match(mtime_str)
        ):
            continue
        # strptime can't parse the trailing 'Z' without %z handling; use fromisoformat.
        iso = mtime_str.replace("Z", "+00:00")
        try:
            mt = datetime.fromisoformat(iso)
        except ValueError:
            continue
        by_kind.setdefault(kind, []).append((path, str(producer), mt))

    # Invariant 1: blind_fix before findings, per producer.
    findings_by_producer: dict[str, list[tuple[str, datetime]]] = {}
    for path, producer, mt in by_kind.get("findings", []):
        findings_by_producer.setdefault(producer, []).append((path, mt))
    for path, producer, blind_mt in by_kind.get("blind_fix", []):
        for findings_path, findings_mt in findings_by_producer.get(producer, []):
            if blind_mt >= findings_mt:
                errors.append(
                    f"{where}: ANTI-ANCHORING violation: blind_fix "
                    f"{path!r} (producer={producer!r}) mtime "
                    f"{blind_mt.isoformat()} is not strictly before findings "
                    f"{findings_path!r} mtime {findings_mt.isoformat()}"
                )

    # Invariant 2: verify_summary AFTER its corresponding findings file.
    # We can't know which summary corresponds to which findings without
    # cross-referencing producers (verifier inherits the producer slug of
    # the reviewer it audits). Same producer-pairing as Invariant 1.
    for path, producer, summary_mt in by_kind.get("verify_summary", []):
        for findings_path, findings_mt in findings_by_producer.get(producer, []):
            if summary_mt <= findings_mt:
                errors.append(
                    f"{where}: stale-audit violation: verify_summary "
                    f"{path!r} (producer={producer!r}) mtime "
                    f"{summary_mt.isoformat()} is not strictly after findings "
                    f"{findings_path!r} mtime {findings_mt.isoformat()}"
                )

    # Invariant 3: readiness is the LATEST mtime in the archive.
    readiness_entries = by_kind.get("readiness", [])
    if readiness_entries:
        readiness_max = max(mt for _, _, mt in readiness_entries)
        for kind, entries in by_kind.items():
            if kind == "readiness":
                continue
            for path, _producer, mt in entries:
                if mt > readiness_max:
                    errors.append(
                        f"{where}: readiness-not-latest violation: "
                        f"{kind} file {path!r} mtime {mt.isoformat()} is "
                        f"after the latest readiness mtime "
                        f"{readiness_max.isoformat()}"
                    )

    return errors


MAX_ARCHIVE_BYTES = 5 * 1024 * 1024  # 5 MB cap; see references/run-archive.md


def _lfs_patterns(ga_text: str) -> list[str]:
    """Path globs tracked by git-lfs, parsed from a .gitattributes body."""
    patterns: list[str] = []
    for line in ga_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "filter=lfs" not in stripped:
            continue
        patterns.append(stripped.split()[0])
    return patterns


def _matches_lfs(path: str, patterns: list[str]) -> bool:
    base = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(base, p) for p in patterns)


def _validate_size_cap(
    files: list[dict[str, Any]], archive_root: Path | None, where: str
) -> list[str]:
    """Enforce the 5 MB run-archive cap (references/run-archive.md). Over-cap is
    allowed only when the bytes NOT tracked by git-lfs stay under the cap — an
    LFS rule that doesn't match the oversized files does NOT exempt the archive."""
    sized = [e for e in files if isinstance(e, dict)]
    total = sum(
        e["bytes"]
        for e in sized
        if isinstance(e.get("bytes"), int) and not isinstance(e["bytes"], bool)
    )
    if total <= MAX_ARCHIVE_BYTES:
        return []
    if archive_root is not None:
        try:
            ga_text = (archive_root / ".gitattributes").read_text(encoding="utf-8")
        except OSError:
            ga_text = ""
        patterns = _lfs_patterns(ga_text)
        if patterns:
            non_lfs = sum(
                e["bytes"]
                for e in sized
                if isinstance(e.get("bytes"), int)
                and not isinstance(e["bytes"], bool)
                and not _matches_lfs(str(e.get("path", "")), patterns)
            )
            if non_lfs <= MAX_ARCHIVE_BYTES:
                return []
    return [
        f"{where}: non-LFS archive bytes exceed the {MAX_ARCHIVE_BYTES}-byte cap; "
        f"track the large artifacts with git lfs (see references/run-archive.md)"
    ]


def _validate_files_on_disk(
    archive_root: Path, files: list[dict[str, Any]], where: str
) -> list[str]:
    """Verify every listed file exists, matches the recorded size, and
    matches the recorded sha256. Size check runs first (cheap fail-fast)."""
    errors: list[str] = []
    archive_root = archive_root.resolve()

    for idx, entry in enumerate(files):
        ewhere = f"{where}.files[{idx}]"
        if not isinstance(entry, dict):
            # Shape check already reported the non-dict; on-disk check has
            # nothing to verify against. Skip silently to avoid AttributeError.
            continue
        rel = entry.get("path")
        if not isinstance(rel, str) or not rel:
            continue
        abs_path = (archive_root / rel).resolve()
        # Path-escape guard at validation time too. Belt + braces with the
        # shape check; a malicious manifest that smuggled "../foo" via path
        # normalisation tricks would be caught here.
        try:
            abs_path.relative_to(archive_root)
        except ValueError:
            errors.append(f"{ewhere}: resolved path {abs_path} escapes archive root")
            continue
        if not abs_path.is_file():
            errors.append(f"{ewhere}: file not found at {abs_path}")
            continue

        expected_size = entry.get("bytes")
        actual_size = abs_path.stat().st_size
        if (
            isinstance(expected_size, int)
            and not isinstance(expected_size, bool)
            and actual_size != expected_size
        ):
            errors.append(
                f"{ewhere}: size mismatch — manifest says {expected_size}, "
                f"disk says {actual_size}"
            )
            continue  # don't bother hashing a wrong-sized file

        expected_sha = entry.get("sha256")
        if isinstance(expected_sha, str) and SHA256_PATTERN.match(expected_sha):
            actual_sha = _sha256_file(abs_path)
            if actual_sha != expected_sha:
                errors.append(
                    f"{ewhere}: sha256 mismatch — manifest says "
                    f"{expected_sha}, disk says {actual_sha}"
                )

    return errors


def validate_manifest_payload(
    manifest: dict[str, Any],
    *,
    archive_root: Path | None = None,
    check_files_on_disk: bool = True,
    label: str = "manifest",
) -> list[str]:
    """Validate a manifest dict. When archive_root is provided AND
    check_files_on_disk=True, also verifies each listed file exists with
    matching size + sha256. Returns a flat list of error strings (empty list
    = valid). Matches verify_findings.validate_findings_doc shape."""
    errors = _validate_shape(manifest, label)
    # _validate_shape already returns early for non-dict manifests; mirror
    # that here so we don't AttributeError when the caller hands us a list
    # or other non-dict shape.
    if not isinstance(manifest, dict):
        return errors
    files = manifest.get("files")
    if isinstance(files, list) and files:
        errors.extend(_validate_ordering(files, label))
        errors.extend(_validate_size_cap(files, archive_root, label))
        if check_files_on_disk and archive_root is not None:
            errors.extend(_validate_files_on_disk(archive_root, files, label))
    return errors


def load_and_validate_manifest(archive_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load `archive_root/manifest.json` and validate. Returns (payload, errors).

    A missing manifest is itself an error (the archive_enabled discipline
    requires the manifest to exist). A malformed-JSON manifest returns
    (None, [parse_error])."""
    archive_root = archive_root.resolve()
    label = f"{archive_root}/manifest.json"
    manifest_path = archive_root / "manifest.json"
    if not manifest_path.is_file():
        return None, [f"{label}: manifest.json not found (ARCHIVE_ENABLED violation)"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{label}: invalid JSON — {exc}"]
    errs = validate_manifest_payload(
        payload, archive_root=archive_root, check_files_on_disk=True, label=label
    )
    return payload, errs
