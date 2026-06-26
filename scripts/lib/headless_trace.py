"""Mechanical trace + archive emission for headless --dry-run entry points.

Invoked from run-mission-headless.sh and (via that script) run-campaign.sh
when --dry-run is set. Uses fleet_run.allocate_run_id, TraceEmitter, and
write_manifest on representative progress-doc inputs — no runtime CLI auth.
"""
from __future__ import annotations

from pathlib import Path

from .emit_trace import TraceEmitter, emit_full_primitive_trace, iter_trace_file
from . import fleet_run


def progress_excerpt_for_mission(repo_root: Path, mission: str) -> str:
    """Return a verbatim slice from docs/<mission>-progress.md when present."""
    path = repo_root / "docs" / f"{mission}-progress.md"
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        return text[:2500] if len(text) > 2500 else text
    return (
        f"# headless dry-run\n"
        f"MISSION: {mission}\n"
        f"PHASE: mechanical validation (no progress doc on disk)\n"
    )


def emit_headless_dryrun_archive(
    repo_root: Path,
    *,
    mission: str,
    runtime: str = "grok",
    fleet_root: Path | None = None,
) -> tuple[Path, str, list[str]]:
    """Emit a multi-primitive trace archive under repo_root/.fleet/runs/<run_id>/.

    Returns (archive_dir, run_id, sorted primitive names emitted).
    T-FINAL is emitted by write_manifest per engine doctrine (trace before ledger).
    """
    if fleet_root is None:
        fleet_root = repo_root

    run_id = fleet_run.allocate_run_id(mission)
    arch = fleet_run.ensure_archive_dir(fleet_root, run_id)

    excerpt = progress_excerpt_for_mission(fleet_root, mission)
    progress_name = "headless-dryrun-progress.md"
    progress_path = arch / progress_name
    progress_path.write_text(excerpt, encoding="utf-8")

    with TraceEmitter(arch, mission=mission, run_id=run_id) as emitter:
        emit_full_primitive_trace(
            emitter,
            task_id=f"headless-{mission}-1",
            include_t_final=False,
            goal_blocked_status="skipped",
            abort_status="skipped",
            details_note=f"headless dry-run via {runtime}",
        )
        trace_path = arch / "trace.jsonl"
        entries = [
            fleet_run.file_entry_for(
                progress_path,
                arch,
                kind="progress",
                producer=f"headless-dryrun-{runtime}",
            ),
            fleet_run.file_entry_for(
                trace_path,
                arch,
                kind="other",
                producer="coordinator",
            ),
        ]
        fleet_run.write_manifest(
            arch,
            run_id=run_id,
            mission=mission,
            files=entries,
            coordinator=f"headless-dryrun-{runtime}",
            base_branch="main",
            notes="Mechanical headless dry-run archive (representative progress excerpt + full primitive trace).",
            emitter=emitter,
        )

    primitives = sorted({e["primitive"] for e in iter_trace_file(trace_path)})
    return arch, run_id, primitives