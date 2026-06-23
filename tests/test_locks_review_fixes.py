"""Regression tests for review-found lock concurrency defects."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import locks as locks_module  # noqa: E402
from lib.locks import FileLock, LockStealError  # noqa: E402


def _lock_path(run_dir: Path, name: str) -> Path:
    path = run_dir / "locks" / f"{name}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_lock(run_dir: Path, name: str, *, owner: str, pid: object) -> Path:
    path = _lock_path(run_dir, name)
    path.write_text(
        json.dumps(
            {"owner": owner, "acquired_at": "1970-01-01T00:00:00Z", "pid": pid},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _unused_pid() -> int:
    candidate = max(os.getpid() + 1_000_000, 999_999)
    for _ in range(1000):
        try:
            os.kill(candidate, 0)
        except ProcessLookupError:
            return candidate
        except PermissionError:
            candidate += 1
            continue
        candidate += 1
    raise AssertionError("could not find an unused pid")


def test_live_holder_is_not_stealable_regardless_of_age(tmp_path: Path) -> None:
    lock_path = _write_lock(tmp_path, "live-review", owner="live", pid=os.getpid())

    with pytest.raises(LockStealError) as excinfo:
        FileLock.steal(tmp_path, "live-review", new_owner="thief", max_stale_s=0.0)

    assert "still alive" in str(excinfo.value)
    assert json.loads(lock_path.read_text(encoding="utf-8"))["owner"] == "live"


def test_dead_holder_unused_pid_is_stealable(tmp_path: Path) -> None:
    dead_pid = _unused_pid()
    _write_lock(tmp_path, "dead-review", owner="dead", pid=dead_pid)

    stolen = FileLock.steal(tmp_path, "dead-review", new_owner="reaper")
    try:
        payload = json.loads(stolen.lock_path.read_text(encoding="utf-8"))
        assert payload["owner"] == "reaper"
        assert payload["stolen_from"] == "dead"
    finally:
        stolen.release()


def test_zero_byte_lock_file_is_stealable_corruption(tmp_path: Path) -> None:
    lock_path = _lock_path(tmp_path, "empty-review")
    lock_path.touch()

    stolen = FileLock.steal(tmp_path, "empty-review", new_owner="recovery")
    try:
        payload = json.loads(stolen.lock_path.read_text(encoding="utf-8"))
        assert payload["owner"] == "recovery"
        assert payload["stolen_from"] is None
    finally:
        stolen.release()


def test_acquire_publishes_complete_record_without_final_os_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_write = locks_module.os.write

    def fail_old_final_write(fd: int, data: bytes) -> int:
        if b"atomic-owner" in data:
            raise AssertionError("old acquire wrote into the final lock file")
        return real_write(fd, data)

    monkeypatch.setattr(locks_module.os, "write", fail_old_final_write)
    lock = FileLock(tmp_path, "atomic-review", owner="atomic-owner").acquire()
    try:
        assert lock.lock_path.stat().st_size > 0
        payload = json.loads(lock.lock_path.read_text(encoding="utf-8"))
        assert payload["owner"] == "atomic-owner"
        assert payload["pid"] == os.getpid()
        assert isinstance(payload["acquired_at"], str)
    finally:
        lock.release()


def test_steal_aborts_if_holder_changes_before_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock_path = _write_lock(tmp_path, "race-review", owner="dead", pid=_unused_pid())
    changed_text = json.dumps(
        {"owner": "other", "acquired_at": "1970-01-01T00:00:00Z", "pid": _unused_pid()},
        sort_keys=True,
    )
    original_read_text = Path.read_text
    read_count = 0

    def changing_read_text(self: Path, *args: object, **kwargs: object) -> str:
        nonlocal read_count
        if self == lock_path:
            read_count += 1
            if read_count == 2:
                return changed_text
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", changing_read_text)
    with pytest.raises(LockStealError) as excinfo:
        FileLock.steal(tmp_path, "race-review", new_owner="thief")

    assert "changed before steal" in str(excinfo.value)
    assert not list(lock_path.parent.glob("*.tmp"))


def test_steal_rechecks_liveness_before_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    holder_pid = _unused_pid()
    _write_lock(tmp_path, "revived-review", owner="dead-then-live", pid=holder_pid)
    probes = 0

    def first_dead_then_alive(pid: int, sig: int) -> None:
        nonlocal probes
        probes += 1
        if probes == 1:
            raise ProcessLookupError("dead on first probe")

    monkeypatch.setattr(os, "kill", first_dead_then_alive)
    with pytest.raises(LockStealError) as excinfo:
        FileLock.steal(tmp_path, "revived-review", new_owner="thief")

    assert "revived before steal" in str(excinfo.value)
