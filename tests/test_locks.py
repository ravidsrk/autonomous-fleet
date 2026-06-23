"""Tests for scripts/lib/locks.py — write-lock discipline.

Covers:
- FileLock acquire/release/timeout/context-manager
- Owner-mismatch on release
- ConstructionLock + RequestLock subclasses
- steal() rejects when holder is alive
- steal() succeeds when holder pid is dead
- steal() age-based fallback for stale locks
- Corrupted lock files (unparseable JSON) on release + steal

Pattern mirrors tests/test_verify_blind_fix.py: 100% coverage, in-process
exercises, minimal subprocess use.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.locks import (  # noqa: E402
    ConstructionLock,
    FileLock,
    LockOwnershipError,
    LockStealError,
    LockTimeoutError,
    RequestLock,
    _pid_alive,
)


# --- Acquire / release ---------------------------------------------------


def test_acquire_release_happy(tmp_path: Path) -> None:
    lock = FileLock(tmp_path, "task-1", timeout_s=1.0, owner="owner-A")
    lock.acquire()
    assert lock.lock_path.is_file()
    payload = json.loads(lock.lock_path.read_text())
    assert payload["owner"] == "owner-A"
    assert payload["pid"] == os.getpid()
    lock.release()
    assert not lock.lock_path.exists()


def test_release_without_acquire_is_noop(tmp_path: Path) -> None:
    lock = FileLock(tmp_path, "task-noop")
    # Never acquired — release should be a quiet no-op.
    lock.release()


def test_release_owner_mismatch_raises(tmp_path: Path) -> None:
    a = FileLock(tmp_path, "task-2", owner="A")
    a.acquire()
    # Manually rewrite the lock to a different owner (simulates the file
    # being stolen out from under us by another worker).
    a.lock_path.write_text(json.dumps({"owner": "B", "acquired_at": "now", "pid": 9999}))
    with pytest.raises(LockOwnershipError) as excinfo:
        a.release()
    assert "expected 'A'" in str(excinfo.value)


def test_release_after_lockfile_deleted_raises(tmp_path: Path) -> None:
    lock = FileLock(tmp_path, "task-x", owner="A")
    lock.acquire()
    lock.lock_path.unlink()  # Simulate disappearance.
    with pytest.raises(LockOwnershipError) as excinfo:
        lock.release()
    assert "cannot read lock file" in str(excinfo.value)


def test_release_unparseable_lockfile_raises(tmp_path: Path) -> None:
    lock = FileLock(tmp_path, "task-y", owner="A")
    lock.acquire()
    lock.lock_path.write_text("{ not valid json")
    with pytest.raises(LockOwnershipError) as excinfo:
        lock.release()
    assert "unparseable" in str(excinfo.value)


# --- Timeout & concurrency ------------------------------------------------


def test_second_acquire_times_out(tmp_path: Path) -> None:
    a = FileLock(tmp_path, "shared", owner="A").acquire()
    b = FileLock(
        tmp_path,
        "shared",
        owner="B",
        timeout_s=0.2,
        poll_interval_s=0.01,
        max_poll_interval_s=0.05,
    )
    with pytest.raises(LockTimeoutError):
        b.acquire()
    a.release()


def test_concurrent_acquire_after_release(tmp_path: Path) -> None:
    a = FileLock(tmp_path, "handoff", owner="A").acquire()

    acquired = threading.Event()
    result: dict[str, object] = {}

    def waiter() -> None:
        b = FileLock(
            tmp_path,
            "handoff",
            owner="B",
            timeout_s=2.0,
            poll_interval_s=0.01,
            max_poll_interval_s=0.05,
        )
        try:
            b.acquire()
            acquired.set()
            result["payload"] = json.loads(b.lock_path.read_text())
            b.release()
        except Exception as exc:  # pragma: no cover
            result["err"] = repr(exc)

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.1)  # Let waiter spin on the lock for a beat.
    a.release()
    t.join(timeout=3.0)
    assert acquired.is_set()
    assert result["payload"]["owner"] == "B"


# --- Context manager ------------------------------------------------------


def test_context_manager_releases_on_exit(tmp_path: Path) -> None:
    lock = FileLock(tmp_path, "ctx", owner="A")
    with lock as held:
        assert held.lock_path.is_file()
    assert not lock.lock_path.exists()


def test_context_manager_swallows_ownership_change(tmp_path: Path) -> None:
    """If the lock is stolen mid-block, __exit__ must not raise."""
    lock = FileLock(tmp_path, "ctx-steal", owner="A")
    with lock:
        # Simulate steal: rewrite owner.
        lock.lock_path.write_text(
            json.dumps({"owner": "stealer", "acquired_at": "now", "pid": 9999})
        )
    # Should not raise; lock file may or may not exist after, but we're not held.
    assert lock._held is False


# --- Subclasses -----------------------------------------------------------


def test_construction_lock_path(tmp_path: Path) -> None:
    lock = ConstructionLock(tmp_path, "task-99")
    assert lock.lock_path.name == "construction-task-99.lock"
    assert lock.task_id == "task-99"


def test_request_lock_path_and_default_timeout(tmp_path: Path) -> None:
    lock = RequestLock(tmp_path, "req-42")
    assert lock.lock_path.name == "request-req-42.lock"
    assert lock.request_id == "req-42"
    # Default timeout overridden by RequestLock.
    assert lock.timeout_s == RequestLock.DEFAULT_TIMEOUT_S


def test_request_lock_explicit_timeout_preserved(tmp_path: Path) -> None:
    lock = RequestLock(tmp_path, "req-43", timeout_s=10.0)
    assert lock.timeout_s == 10.0


# --- _pid_alive helper ----------------------------------------------------


def test_pid_alive_current_pid_is_alive() -> None:
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_zero_pid_is_not_alive() -> None:
    assert _pid_alive(0) is False
    assert _pid_alive(-1) is False


def test_pid_alive_dead_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_kill(pid: int, sig: int) -> None:
        raise ProcessLookupError(f"no process {pid}")

    monkeypatch.setattr(os, "kill", fake_kill)
    assert _pid_alive(99999) is False


def test_pid_alive_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_kill(pid: int, sig: int) -> None:
        raise PermissionError("operation not permitted")

    monkeypatch.setattr(os, "kill", fake_kill)
    # Permission error means process exists but we can't signal it.
    assert _pid_alive(1) is True


# --- Steal ---------------------------------------------------------------


def test_steal_rejected_when_no_lock(tmp_path: Path) -> None:
    with pytest.raises(LockStealError) as excinfo:
        FileLock.steal(tmp_path, "missing")
    assert "no lock to steal" in str(excinfo.value)


def test_steal_rejected_when_holder_alive(tmp_path: Path) -> None:
    """Holder's pid is the current test pid — definitely alive."""
    held = FileLock(tmp_path, "alive", owner="alive-owner").acquire()
    try:
        with pytest.raises(LockStealError) as excinfo:
            FileLock.steal(tmp_path, "alive", new_owner="thief", max_stale_s=86400)
        assert "still alive" in str(excinfo.value)
    finally:
        held.release()


def test_steal_succeeds_when_holder_dead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    held = FileLock(tmp_path, "dead", owner="dead-owner").acquire()

    def fake_kill(pid: int, sig: int) -> None:
        raise ProcessLookupError("dead")

    monkeypatch.setattr(os, "kill", fake_kill)
    new = FileLock.steal(tmp_path, "dead", new_owner="reaper")
    try:
        payload = json.loads(new.lock_path.read_text())
        assert payload["owner"] == "reaper"
        assert payload["stolen_from"] == "dead-owner"
    finally:
        new.release()


def test_steal_age_fallback_succeeds_on_stale_lock(tmp_path: Path) -> None:
    held = FileLock(tmp_path, "stale", owner="stale-owner").acquire()
    # Rewrite acquired_at to ancient history while the pid is still ours
    # (the test's own pid). max_stale_s=0 forces "stale".
    payload = json.loads(held.lock_path.read_text())
    payload["acquired_at"] = "1970-01-01T00:00:00Z"
    held.lock_path.write_text(json.dumps(payload))

    new = FileLock.steal(tmp_path, "stale", new_owner="grim", max_stale_s=0.5)
    try:
        payload2 = json.loads(new.lock_path.read_text())
        assert payload2["owner"] == "grim"
    finally:
        new.release()


def test_steal_age_unparseable_with_live_pid_falls_through(tmp_path: Path) -> None:
    """Unparseable acquired_at sets age=inf. If holder is alive, the
    'age < max_stale_s' check is False (inf is not < any finite max),
    so steal *succeeds* — the holder's liveness alone isn't sufficient
    to block when age is unbounded. This documents the actual behaviour."""
    held = FileLock(tmp_path, "bad-ts", owner="A").acquire()
    payload = json.loads(held.lock_path.read_text())
    payload["acquired_at"] = "not-an-iso-date"
    held.lock_path.write_text(json.dumps(payload))
    # Holder pid is alive (test's own pid); age is inf; max_stale_s is finite.
    # inf < finite is False → steal proceeds.
    new = FileLock.steal(tmp_path, "bad-ts", new_owner="thief", max_stale_s=10000)
    payload2 = json.loads(new.lock_path.read_text())
    assert payload2["owner"] == "thief"
    # NOTE: held.release() will fail with LockOwnershipError because thief
    # now owns it — that's the expected state, not a test failure. Don't
    # call held.release().
    new.release()


def test_steal_rejects_corrupted_lockfile(tmp_path: Path) -> None:
    FileLock(tmp_path, "corrupt", owner="A").acquire()
    lock_path = tmp_path / "locks" / "corrupt.lock"
    lock_path.write_text("{not json at all")
    with pytest.raises(LockStealError) as excinfo:
        FileLock.steal(tmp_path, "corrupt")
    assert "unparseable" in str(excinfo.value)


def test_steal_with_default_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Steal with no new_owner uses the auto pid-N-stolen owner string."""
    FileLock(tmp_path, "default-thief", owner="victim").acquire()
    monkeypatch.setattr(os, "kill", lambda *_: (_ for _ in ()).throw(ProcessLookupError()))
    new = FileLock.steal(tmp_path, "default-thief")
    try:
        assert new.owner.startswith("pid-") and new.owner.endswith("-stolen")
    finally:
        new.release()


def test_steal_with_non_int_pid(tmp_path: Path) -> None:
    """A lock with no pid field (or non-int) is treated as 'liveness unknown'.

    Falls through to age-check; if age is also unknown/zero, steal succeeds.
    """
    held = FileLock(tmp_path, "nopid", owner="A").acquire()
    payload = json.loads(held.lock_path.read_text())
    payload["pid"] = "not-an-int"
    payload["acquired_at"] = "1970-01-01T00:00:00Z"
    held.lock_path.write_text(json.dumps(payload))
    new = FileLock.steal(tmp_path, "nopid", new_owner="recovery", max_stale_s=0.1)
    try:
        assert json.loads(new.lock_path.read_text())["owner"] == "recovery"
    finally:
        new.release()
