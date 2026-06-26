"""Thin entry-point wrapper; orchestration lives in fleet_run.write_headless_dryrun_archive."""
from __future__ import annotations

from pathlib import Path

from . import fleet_run


def progress_excerpt_for_mission(repo_root: Path, mission: str) -> str:
    """Re-export fleet_run.progress_excerpt_for_mission."""
    return fleet_run.progress_excerpt_for_mission(repo_root, mission)


def emit_headless_dryrun_archive(
    repo_root: Path,
    *,
    mission: str,
    runtime: str = "grok",
    fleet_root: Path | None = None,
    runtime_response_path: Path | None = None,
) -> tuple[Path, str, list[str]]:
    """Emit archive under repo_root/.fleet/runs/<run_id>/ (see fleet_run)."""
    return fleet_run.write_headless_dryrun_archive(
        repo_root,
        mission=mission,
        runtime=runtime,
        progress_source_root=fleet_root,
        runtime_response_path=runtime_response_path,
    )


def record_headless_run(
    repo_root: Path,
    *,
    mission: str,
    runtime: str = "grok",
    fleet_root: Path | None = None,
    runtime_response_path: Path | None = None,
) -> tuple[Path, str, list[str]]:
    """Persist headless archive; callers control ephemeral cleanup (shell dry-run only)."""
    return fleet_run.record_headless_run(
        repo_root,
        mission=mission,
        runtime=runtime,
        progress_source_root=fleet_root,
        runtime_response_path=runtime_response_path,
    )