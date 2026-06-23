"""Tests for the post-merge deep-review fixes (PR #39 follow-up).

Covers: TRACE EMISSION ordering (emit before ledger write), details redaction enforcement,
and the steal() vanished-lock LockStealError wrap. Each asserts real behaviour and fails if the
fix is reverted.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import fleet_run as fr  # noqa: E402
from lib import locks as locks_mod  # noqa: E402
from lib.emit_trace import TraceEmitter, _scan_details, validate_event  # noqa: E402
from lib.locks import FileLock, LockStealError  # noqa: E402

RUN_ID = "20260623T000000Z-doc-sync-abc123"


def _valid_event(**over) -> dict:
    ev = {
        "schema_version": "1.0",
        "ts": "2026-06-23T00:00:00Z",
        "run_id": RUN_ID,
        "mission": "doc-sync",
        "primitive": "DISPATCH",
        "role": "COORDINATOR",
        "status": "started",
    }
    ev.update(over)
    return ev


# --- #1 TRACE EMISSION ordering: emit BEFORE the manifest (ledger) write ---

def test_write_manifest_emits_before_writing_manifest(tmp_path):
    rid = fr.allocate_run_id("doc-sync")
    arch = fr.ensure_archive_dir(tmp_path, rid)
    fd = arch / "f.json"
    fd.write_text("{}", encoding="utf-8")
    seen = {}

    class Spy:
        def emit(self, *a, **k):
            seen["manifest_existed_at_emit"] = (arch / "manifest.json").exists()

    fr.write_manifest(
        arch,
        run_id=rid,
        mission="doc-sync",
        files=[fr.file_entry_for(fd, arch, kind="findings", producer="r")],
        emitter=Spy(),
    )
    # Doctrine: trace first, ledger second. The manifest must NOT exist yet at emit time.
    assert seen["manifest_existed_at_emit"] is False
    assert (arch / "manifest.json").exists()


# --- #2 details redaction enforcement ---

def test_scan_details_flags_secret():
    assert _scan_details({"key": "sk-" + "a" * 24})
    assert _scan_details({"aws": "AKIA" + "B" * 16})
    assert _scan_details({"gh": "ghp_" + "c" * 36})


def test_scan_details_flags_host_path():
    assert _scan_details({"p": "/Users/ravindra/.ssh/id_rsa"})
    assert _scan_details({"p": "/home/ci/secret"})


def test_scan_details_walks_nested_dict_and_list():
    assert _scan_details({"a": {"b": "AKIA" + "D" * 16}})
    assert _scan_details({"a": ["ok", "ghp_" + "e" * 36]})
    assert _scan_details({"clean": "manifest.json", "n": 9}) == []


def test_validate_event_flags_secret_in_details():
    errs = validate_event(_valid_event(details={"token": "sk-" + "f" * 24}))
    assert any("secret" in e for e in errs)


def test_emit_rejects_secret_in_details(tmp_path):
    with TraceEmitter(tmp_path / "run", mission="doc-sync", run_id=RUN_ID) as em:
        with pytest.raises(ValueError, match="secret"):
            em.emit("DISPATCH", "COORDINATOR", "started", details={"k": "sk-" + "g" * 24})
        with pytest.raises(ValueError, match="host-absolute"):
            em.emit("DISPATCH", "COORDINATOR", "started", details={"p": "/Users/x/.aws/creds"})


# --- #7 steal() wraps a vanished-lock FileNotFoundError as LockStealError ---

def _unused_pid() -> int:
    cand = max(os.getpid() + 1_000_000, 999_999)
    while True:
        try:
            os.kill(cand, 0)
        except ProcessLookupError:
            return cand
        except PermissionError:
            return cand
        cand += 1


def test_steal_wraps_vanished_lock_as_lock_steal_error(tmp_path, monkeypatch):
    lock = FileLock(tmp_path, "vanish")
    lock.lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock.lock_path.write_text(
        json.dumps({"owner": "dead", "acquired_at": "1970-01-01T00:00:00Z", "pid": _unused_pid()}),
        encoding="utf-8",
    )
    real = locks_mod._read_steal_payload
    calls = {"n": 0}

    def flaky(path):
        calls["n"] += 1
        if calls["n"] >= 2:  # the re-validation read inside the try
            raise FileNotFoundError(str(path))
        return real(path)

    monkeypatch.setattr(locks_mod, "_read_steal_payload", flaky)
    with pytest.raises(LockStealError, match="vanished"):
        FileLock.steal(tmp_path, "vanish", new_owner="thief")
