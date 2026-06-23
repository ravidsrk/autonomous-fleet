"""Tests for the trace-emission contract (Commit E).

Covers:
- TraceEmitter happy emit (file is opened, line is JSONL, fields populated).
- TraceEmitter atomic append (every emit() flushes; partial line is never
  observable to a concurrent reader).
- TraceEmitter context-manager close + idempotent ``close()``.
- validate_event() happy + every failure mode (missing field, wrong type,
  bad enum, bad ts, bad run_id, additional properties, bad evidence_hash,
  negative cost_delta, bad parent_event uuid, non-dict details, bad
  schema_version, non-string mission, non-string task_id).
- iter_trace_file() tolerates malformed and non-object lines.
- CLI: validate + summary subcommands (happy and failure paths).
- Doctrine enforcement: trace event MUST be emitted before the ledger
  write commits. Simulated by mocking a "ledger write" callback and
  asserting the trace file already has the line at the time the ledger
  write would land.

Schema-drift guard: assert PRIMITIVES / ROLES / STATUSES / SCHEMA_VERSION
match the schema file under ``skills/autonomous-fleet-core/assets/``.

Coverage on the lib + CLI is gated at 100% by validate-all.sh.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import fleet_run  # noqa: E402
from lib.emit_trace import (  # noqa: E402
    PRIMITIVES,
    ROLES,
    SCHEMA_VERSION,
    STATUSES,
    TraceEmitter,
    _ALLOWED_FIELDS,
    _EVIDENCE_HASH_RE,
    _REQUIRED_FIELDS,
    _RUN_ID_RE,
    _TS_RE,
    _UUID_RE,
    iter_trace_file,
    validate_event,
)


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "emit_trace_cli",
        REPO_ROOT / "scripts" / "emit_trace.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*argv: str) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    sys.argv = ["emit_trace.py", *argv]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(list(argv))
    finally:
        sys.argv = old_argv
    return rc, out.getvalue(), err.getvalue()


RUN_ID = "20260101T000000Z-doc-sync-abc123"
MISSION = "doc-sync"


def _valid_event(**overrides: object) -> dict:
    event = {
        "schema_version": SCHEMA_VERSION,
        "ts": "2026-01-01T00:00:00Z",
        "run_id": RUN_ID,
        "mission": MISSION,
        "primitive": "DISPATCH",
        "role": "COORDINATOR",
        "status": "started",
    }
    event.update(overrides)
    return event


def _manifest_archive(tmp_path: Path) -> tuple[Path, fleet_run.FileEntry]:
    archive_root = tmp_path / "run"
    archive_root.mkdir()
    readiness = archive_root / "readiness.md"
    readiness.write_text("ready\n", encoding="utf-8")
    entry = fleet_run.file_entry_for(
        readiness,
        archive_root,
        kind="readiness",
        producer="integrator",
    )
    return archive_root, entry


# --- TraceEmitter -----------------------------------------------------------


def test_emit_creates_jsonl_and_returns_event(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    with TraceEmitter(run_dir, mission=MISSION, run_id=RUN_ID) as emitter:
        event = emitter.emit(
            "DISPATCH",
            "COORDINATOR",
            "started",
            task_id="T1",
            cost_delta=0.25,
            details={"note": "first dispatch"},
        )
    assert event["primitive"] == "DISPATCH"
    assert event["task_id"] == "T1"
    assert event["mission"] == MISSION
    assert event["run_id"] == RUN_ID
    assert event["schema_version"] == SCHEMA_VERSION
    assert event["details"] == {"note": "first dispatch"}

    path = run_dir / "trace.jsonl"
    assert path.is_file()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed == event
    assert validate_event(parsed) == []


def test_emit_accepts_evidence_hash_and_parent_event(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    with TraceEmitter(run_dir, mission=MISSION, run_id=RUN_ID) as emitter:
        event = emitter.emit(
            "COMMIT",
            "INTEGRATOR",
            "succeeded",
            evidence_hash="a" * 64,
            parent_event="12345678-1234-1234-1234-1234567890ab",
        )
    assert event["evidence_hash"] == "a" * 64
    assert event["parent_event"] == "12345678-1234-1234-1234-1234567890ab"
    assert validate_event(event) == []


def test_emit_appends_across_emits(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    with TraceEmitter(run_dir, mission=MISSION, run_id=RUN_ID) as emitter:
        emitter.emit("SPAWN_WORKER", "COORDINATOR", "started")
        emitter.emit("DISPATCH", "BUILDER", "succeeded")
        emitter.emit("MERGE", "INTEGRATOR", "succeeded")
    lines = (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    primitives = [json.loads(line)["primitive"] for line in lines]
    assert primitives == ["SPAWN_WORKER", "DISPATCH", "MERGE"]


def test_emit_atomic_flush_visible_immediately(tmp_path: Path) -> None:
    """Each emit() flushes; a concurrent reader sees the full line."""
    run_dir = tmp_path / "run"
    emitter = TraceEmitter(run_dir, mission=MISSION, run_id=RUN_ID)
    try:
        emitter.emit("WAIT", "COORDINATOR", "started")
        # Read with a fresh handle BEFORE close — must already see the line.
        content = (run_dir / "trace.jsonl").read_text(encoding="utf-8")
        assert content.endswith("\n")
        parsed = json.loads(content.strip())
        assert parsed["primitive"] == "WAIT"
    finally:
        emitter.close()


def test_emit_path_property(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    emitter = TraceEmitter(run_dir, mission=MISSION, run_id=RUN_ID)
    try:
        assert emitter.path == run_dir / "trace.jsonl"
    finally:
        emitter.close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    emitter = TraceEmitter(run_dir, mission=MISSION, run_id=RUN_ID)
    emitter.close()
    emitter.close()  # second close is a no-op, not an error


def test_doctrine_emit_before_ledger_write(tmp_path: Path) -> None:
    """Enforces engine.md § TRACE EMISSION: trace event MUST land before
    the ledger row commits. Simulated by a ledger-write callback that, at
    the moment it would commit, asserts the trace file already contains
    the matching line.
    """
    run_dir = tmp_path / "run"
    trace_path = run_dir / "trace.jsonl"

    def commit_ledger_row(event: dict) -> None:
        # The doctrine says trace MUST be on disk before this commits.
        assert trace_path.is_file(), "trace file missing at ledger-commit time"
        lines = trace_path.read_text(encoding="utf-8").splitlines()
        assert any(
            json.loads(line)["primitive"] == event["primitive"] for line in lines
        ), "trace event not flushed before ledger write"

    with TraceEmitter(run_dir, mission=MISSION, run_id=RUN_ID) as emitter:
        event = emitter.emit("DISPATCH", "COORDINATOR", "started")
        commit_ledger_row(event)


def test_write_manifest_with_emitter_emits_t_final(tmp_path: Path) -> None:
    archive_root, entry = _manifest_archive(tmp_path)
    trace_path = archive_root / "trace.jsonl"

    with TraceEmitter(archive_root, mission=MISSION, run_id=RUN_ID) as emitter:
        manifest_path = fleet_run.write_manifest(
            archive_root,
            run_id=RUN_ID,
            mission=MISSION,
            files=[entry],
            emitter=emitter,
        )

    assert manifest_path == archive_root / "manifest.json"
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert validate_event(event) == []
    assert event["primitive"] == "T-FINAL"
    assert event["role"] == "INTEGRATOR"
    assert event["status"] == "succeeded"
    assert event["run_id"] == RUN_ID
    assert event["details"] == {"manifest": "manifest.json", "files": 1}


def test_write_manifest_without_emitter_does_not_emit_trace(tmp_path: Path) -> None:
    archive_root, entry = _manifest_archive(tmp_path)

    manifest_path = fleet_run.write_manifest(
        archive_root,
        run_id=RUN_ID,
        mission=MISSION,
        files=[entry],
    )

    assert manifest_path.is_file()
    assert not (archive_root / "trace.jsonl").exists()


# --- validate_event ---------------------------------------------------------


def test_validate_happy() -> None:
    assert validate_event(_valid_event()) == []


def test_validate_non_object() -> None:
    errors = validate_event("nope")  # type: ignore[arg-type]
    assert errors == ["event must be an object, got str"]


def test_validate_missing_field() -> None:
    event = _valid_event()
    del event["mission"]
    errors = validate_event(event)
    assert "missing required field: mission" in errors


def test_validate_additional_property_rejected() -> None:
    event = _valid_event(extra="nope")
    errors = validate_event(event)
    assert "additionalProperties not allowed: extra" in errors


def test_validate_schema_version_mismatch() -> None:
    event = _valid_event(schema_version="2.0")
    errors = validate_event(event)
    assert any("schema_version must be" in e for e in errors)


def test_validate_bad_ts() -> None:
    errors = validate_event(_valid_event(ts="2026-01-01 00:00:00"))
    assert any("ts must be ISO 8601 UTC" in e for e in errors)


def test_validate_ts_wrong_type() -> None:
    errors = validate_event(_valid_event(ts=12345))
    assert any("ts must be ISO 8601 UTC" in e for e in errors)


def test_validate_bad_run_id() -> None:
    errors = validate_event(_valid_event(run_id="my-pet-name"))
    assert any("run_id does not match archive pattern" in e for e in errors)


def test_validate_run_id_wrong_type() -> None:
    errors = validate_event(_valid_event(run_id=123))
    assert any("run_id does not match archive pattern" in e for e in errors)


def test_validate_mission_empty() -> None:
    errors = validate_event(_valid_event(mission=""))
    assert "mission must be a non-empty string" in errors


def test_validate_mission_wrong_type() -> None:
    errors = validate_event(_valid_event(mission=42))
    assert "mission must be a non-empty string" in errors


def test_validate_bad_primitive() -> None:
    errors = validate_event(_valid_event(primitive="WHATEVER"))
    assert any("primitive must be one of" in e for e in errors)


def test_validate_bad_role() -> None:
    errors = validate_event(_valid_event(role="MANAGER"))
    assert any("role must be one of" in e for e in errors)


def test_validate_bad_status() -> None:
    errors = validate_event(_valid_event(status="completed"))
    assert any("status must be one of" in e for e in errors)


def test_validate_task_id_empty() -> None:
    errors = validate_event(_valid_event(task_id=""))
    assert "task_id must be a non-empty string when set" in errors


def test_validate_task_id_wrong_type() -> None:
    errors = validate_event(_valid_event(task_id=5))
    assert "task_id must be a non-empty string when set" in errors


def test_validate_bad_evidence_hash() -> None:
    errors = validate_event(_valid_event(evidence_hash="not-a-sha"))
    assert any("evidence_hash must be 64-char hex sha256" in e for e in errors)


def test_validate_evidence_hash_wrong_type() -> None:
    errors = validate_event(_valid_event(evidence_hash=12345))
    assert any("evidence_hash must be 64-char hex sha256" in e for e in errors)


def test_validate_cost_delta_negative() -> None:
    errors = validate_event(_valid_event(cost_delta=-1))
    assert any("cost_delta must be non-negative" in e for e in errors)


def test_validate_cost_delta_wrong_type() -> None:
    errors = validate_event(_valid_event(cost_delta="cheap"))
    assert any("cost_delta must be a non-negative number" in e for e in errors)


def test_validate_cost_delta_bool_rejected() -> None:
    # bool is a subclass of int in Python; explicit guard.
    errors = validate_event(_valid_event(cost_delta=True))
    assert any("cost_delta must be a non-negative number" in e for e in errors)


def test_validate_bad_parent_event() -> None:
    errors = validate_event(_valid_event(parent_event="nope"))
    assert any("parent_event must be UUID-shaped" in e for e in errors)


def test_validate_parent_event_wrong_type() -> None:
    errors = validate_event(_valid_event(parent_event=123))
    assert any("parent_event must be UUID-shaped" in e for e in errors)


def test_validate_details_wrong_type() -> None:
    errors = validate_event(_valid_event(details="not-an-object"))
    assert "details must be an object when set" in errors


# --- iter_trace_file --------------------------------------------------------


def test_iter_trace_yields_events_and_skips_malformed(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(_valid_event()),
                "{not json",
                "",
                json.dumps([1, 2, 3]),  # not an object
                json.dumps(_valid_event(primitive="MERGE")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    events = list(iter_trace_file(path))
    assert [e["primitive"] for e in events] == ["DISPATCH", "MERGE"]
    assert iter_trace_file.last_skipped == 2  # type: ignore[attr-defined]


# --- CLI --------------------------------------------------------------------


def test_cli_validate_happy(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(_valid_event()),
                "",  # empty line tolerated
                json.dumps(_valid_event(primitive="MERGE", role="INTEGRATOR")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rc, out, err = _run_cli("validate", str(path))
    assert rc == 0, err
    assert "validated 2 events" in out


def test_cli_validate_reports_invalid(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(_valid_event()),
                json.dumps(_valid_event(primitive="BOGUS")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rc, _out, err = _run_cli("validate", str(path))
    assert rc == 1
    assert "primitive must be one of" in err


def test_cli_validate_reports_unparseable(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("{not json\n", encoding="utf-8")
    rc, _out, err = _run_cli("validate", str(path))
    assert rc == 1
    assert "invalid JSON" in err


def test_cli_validate_missing_file(tmp_path: Path) -> None:
    rc, _out, err = _run_cli("validate", str(tmp_path / "missing.jsonl"))
    assert rc == 2
    assert "not a file" in err


def test_cli_validate_unreadable_file(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("", encoding="utf-8")
    real_open = Path.open

    def boom(self, *a, **kw):
        if self == path:
            raise OSError("permission denied")
        return real_open(self, *a, **kw)

    monkeypatch.setattr(Path, "open", boom)
    rc, _out, err = _run_cli("validate", str(path))
    assert rc == 2
    assert "cannot read" in err


def test_cli_summary_happy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    with TraceEmitter(run_dir, mission=MISSION, run_id=RUN_ID) as emitter:
        emitter.emit("SPAWN_WORKER", "COORDINATOR", "started")
        emitter.emit("DISPATCH", "BUILDER", "succeeded")
        emitter.emit("DISPATCH", "BUILDER", "succeeded")
    rc, out, err = _run_cli("summary", str(run_dir))
    assert rc == 0, err
    assert "3 events" in out
    assert "DISPATCH: 2" in out
    assert "BUILDER: 2" in out
    assert "started: 1" in out


def test_cli_summary_missing_dir(tmp_path: Path) -> None:
    rc, _out, err = _run_cli("summary", str(tmp_path / "missing"))
    assert rc == 2
    assert "not a directory" in err


def test_cli_summary_missing_trace(tmp_path: Path) -> None:
    rc, _out, err = _run_cli("summary", str(tmp_path))
    assert rc == 2
    assert "trace file not found" in err


def test_cli_requires_subcommand() -> None:
    cli = _load_cli()
    err = io.StringIO()
    with redirect_stderr(err):
        with pytest.raises(SystemExit):
            cli.main([])


# --- Schema-drift guard -----------------------------------------------------


def _lib_pattern(pattern: str) -> str:
    return pattern.replace(r"\d", "[0-9]")


def test_schema_drift_against_assets() -> None:
    schema_path = (
        REPO_ROOT
        / "skills"
        / "autonomous-fleet-core"
        / "assets"
        / "fleet-trace.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert tuple(schema["properties"]["primitive"]["enum"]) == PRIMITIVES
    assert tuple(schema["properties"]["role"]["enum"]) == ROLES
    assert tuple(schema["properties"]["status"]["enum"]) == STATUSES
    assert schema["required"] == list(_REQUIRED_FIELDS)
    assert schema["properties"]["ts"]["pattern"] == _lib_pattern(_TS_RE.pattern)
    assert schema["properties"]["run_id"]["pattern"] == _lib_pattern(
        _RUN_ID_RE.pattern
    )
    assert schema["properties"]["evidence_hash"]["pattern"] == _lib_pattern(
        _EVIDENCE_HASH_RE.pattern
    )
    assert schema["properties"]["parent_event"]["pattern"] == _lib_pattern(
        _UUID_RE.pattern
    )
    assert schema["properties"]["mission"]["minLength"] == 1
    assert schema["properties"]["cost_delta"]["minimum"] == 0
    assert schema["properties"]["task_id"]["minLength"] == 1
    assert set(schema["properties"].keys()) == set(_ALLOWED_FIELDS)
    assert schema["$id"].endswith("fleet-trace.schema.json")
    assert schema["additionalProperties"] is False


def test_example_trace_asset_validates_clean() -> None:
    example_path = (
        REPO_ROOT
        / "skills"
        / "autonomous-fleet-core"
        / "assets"
        / "fleet-trace.v1.example.jsonl"
    )
    lines = example_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 4
    for line_no, line in enumerate(lines, start=1):
        event = json.loads(line)
        assert validate_event(event) == [], f"line {line_no}: {event}"


def test_example_trace_covers_all_enums() -> None:
    """The shipped example must exercise every primitive/role/status enum value, so a future
    enum drop is caught here too (belt-and-suspenders with the schema-drift test)."""
    path = (
        REPO_ROOT / "skills" / "autonomous-fleet-core" / "assets" / "fleet-trace.v1.example.jsonl"
    )
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert {e["primitive"] for e in events} == set(PRIMITIVES)
    assert {e["role"] for e in events} == set(ROLES)
    assert {e["status"] for e in events} == set(STATUSES)


def test_run_id_pattern_matches_fleet_run():
    """emit_trace._RUN_ID_RE MUST stay identical to fleet_run.RUN_ID_PATTERN
    (kept as a literal to avoid a circular import; pinned here instead)."""
    assert _RUN_ID_RE.pattern == fleet_run.RUN_ID_PATTERN.pattern


@pytest.mark.parametrize(
    "secret",
    [
        "gho_" + "a" * 36,
        "xoxb-" + "1" * 20,
        "sk_live_" + "a" * 20,
        "AIza" + "b" * 35,
        "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12,
        "Bearer " + "x" * 24,
    ],
)
def test_scan_flags_broadened_secret_shapes(secret):
    from lib.emit_trace import _scan_details

    assert _scan_details({"k": secret})


@pytest.mark.parametrize("hostpath", ["/etc/passwd", "/var/log/app.log"])
def test_scan_flags_more_host_paths(hostpath):
    from lib.emit_trace import _scan_details

    assert _scan_details({"k": hostpath})
