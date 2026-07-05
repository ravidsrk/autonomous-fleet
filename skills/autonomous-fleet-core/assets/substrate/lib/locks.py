"""Write-lock discipline for fleet workers.

Implements the WRITE-LOCK DISCIPLINE doctrine from locks.md / engine core. Two lock
kinds with different lifetimes:

- ``ConstructionLock``: long-held. Acquired before a worker starts
  BUILDING artifacts in its task slot (worktree, branch, attestation
  file). Released only on COMMIT or ABORT.
- ``RequestLock``: short-held. Acquired before a worker calls an
  external write API (gh pr merge, terraform apply, fly deploy, git
  push). Released immediately after the call returns.

Lock files live under ``.fleet/runs/<run_id>/locks/`` with contents
``{"owner", "acquired_at", "pid"}`` for diagnostics.

A dead-holder's lock MAY be stolen via ``FileLock.steal()`` — but ONLY
after the SIGNAL RECONCILIATION § dead-worker detection discipline has
confirmed the holder is gone (this module exposes the mechanism;
callers enforce the discipline).

Lineage: borrowable-patterns audit #9 (construction-lock + request-lock).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LockError(Exception):
    """Base class for lock-related failures."""


class LockTimeoutError(LockError):
    """Acquire timed out without obtaining the lock."""


class LockOwnershipError(LockError):
    """Caller tried to release a lock it does not own."""


class LockStealError(LockError):
    """Steal attempt rejected (holder still alive or steal preconditions unmet)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pid_alive(pid: int) -> bool:
    """Return True if the given pid is still running.

    Uses signal 0 (no-op probe). On Linux/macOS this returns without
    sending a signal but raises ``ProcessLookupError`` for dead pids.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we can't signal it — still alive.
        return True
    return True


def _read_steal_payload(lock_path: Path) -> tuple[str, dict[str, Any]]:
    """Read a lock body for steal checks.

    Empty lock files are recoverable corruption: they can be replaced by
    a steal because they cannot identify a live local holder.
    """
    text = lock_path.read_text(encoding="utf-8")
    if not text.strip():
        return text, {}
    try:
        payload: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LockStealError(f"lock file unparseable: {lock_path} ({exc})") from exc
    return text, payload


class FileLock:
    """File-based exclusive lock under a run-archive's ``locks/`` dir.

    Acquire publishes a complete pre-written record with an atomic
    no-clobber link; release is owner-checked. Stealing is a separate,
    explicit primitive that callers MUST gate on a confirmed-dead signal.
    """

    LOCKS_SUBDIR = "locks"

    def __init__(
        self,
        run_dir: Path,
        name: str,
        *,
        timeout_s: float = 30.0,
        owner: str | None = None,
        poll_interval_s: float = 0.05,
        max_poll_interval_s: float = 1.0,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.name = name
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.max_poll_interval_s = max_poll_interval_s
        self.owner = owner or f"pid-{os.getpid()}"
        self._held = False

    @property
    def lock_path(self) -> Path:
        return self.run_dir / self.LOCKS_SUBDIR / f"{self.name}.lock"

    # --- Acquire / release ------------------------------------------------

    def acquire(self) -> "FileLock":
        """Acquire the lock or raise LockTimeoutError after ``timeout_s``.

        Exponential backoff capped at ``max_poll_interval_s`` to avoid
        burning CPU while another worker holds the lock.
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_s
        delay = self.poll_interval_s
        while True:
            payload = {
                "owner": self.owner,
                "acquired_at": _now_iso(),
                "pid": os.getpid(),
            }
            tmp = self.lock_path.with_name(
                f".{self.lock_path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp"
            )
            try:
                tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
                try:
                    os.link(tmp, self.lock_path)
                except FileExistsError:
                    if time.monotonic() >= deadline:
                        raise LockTimeoutError(
                            f"acquire timed out after {self.timeout_s}s: {self.lock_path}"
                        )
                    time.sleep(delay)
                    delay = min(delay * 2, self.max_poll_interval_s)
                    continue
                self._held = True
                return self
            finally:
                # Always clean the staging file: success (lock is a separate hardlink),
                # retry, timeout, or a mid-write ENOSPC all leave no tmp behind.
                tmp.unlink(missing_ok=True)

    def release(self) -> None:
        """Release the lock. Raises LockOwnershipError if not held by us."""
        if not self._held:
            return
        try:
            text = self.lock_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LockOwnershipError(
                f"cannot read lock file (gone?): {self.lock_path} ({exc})"
            ) from exc
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LockOwnershipError(
                f"lock file unparseable: {self.lock_path} ({exc})"
            ) from exc
        if payload.get("owner") != self.owner:
            raise LockOwnershipError(
                f"lock owner mismatch: expected {self.owner!r}, "
                f"got {payload.get('owner')!r} ({self.lock_path})"
            )
        self.lock_path.unlink()
        self._held = False

    # --- Steal ------------------------------------------------------------

    @classmethod
    def steal(
        cls,
        run_dir: Path,
        name: str,
        *,
        new_owner: str | None = None,
        max_stale_s: float = 300.0,
    ) -> "FileLock":
        """Steal a dead-holder's lock and acquire it for the new owner.

        Refuses to steal if the holder pid resolves to a live local
        process. ``max_stale_s`` is retained for API compatibility only:
        lock age never authorizes stealing a live local holder.
        """
        del max_stale_s
        lock = cls(run_dir, name, owner=new_owner or f"pid-{os.getpid()}-stolen")
        if not lock.lock_path.is_file():
            raise LockStealError(f"no lock to steal: {lock.lock_path}")

        text, payload = _read_steal_payload(lock.lock_path)

        holder_pid = payload.get("pid")
        if isinstance(holder_pid, int) and _pid_alive(holder_pid):
            raise LockStealError(
                f"holder pid {holder_pid} still alive: {lock.lock_path}"
            )

        # CAS-shaped steal (issue #96 closed the TOCTOU): we NEVER overwrite
        # lock_path in place. (1) atomically rename the stale lock to a unique
        # tombstone — exactly one stealer's rename succeeds; (2) verify the
        # tombstone is byte-identical to what we validated (a mismatch means
        # we displaced a rewritten lock: restore best-effort and abort);
        # (3) acquire FRESH through the same link()-based CAS every acquirer
        # uses — losing that race to a fresh acquirer is a clean failure, not
        # a clobber.
        tombstone = lock.lock_path.with_name(
            f".{lock.lock_path.name}.steal.{os.getpid()}.{time.monotonic_ns()}"
        )
        try:
            os.rename(lock.lock_path, tombstone)
        except FileNotFoundError as exc:
            raise LockStealError(
                f"lost steal race (lock vanished): {lock.lock_path}"
            ) from exc
        stolen_text = tombstone.read_text(encoding="utf-8")
        # Pid-reuse guard: re-probe liveness AFTER winning the tombstone — a
        # holder that came alive between validation and takeover gets its
        # lock restored (same guarantee the pre-#96 protocol re-checked).
        recheck_pid = payload.get("pid")
        if isinstance(recheck_pid, int) and _pid_alive(recheck_pid):
            try:
                os.link(tombstone, lock.lock_path)
            except OSError:
                pass
            tombstone.unlink(missing_ok=True)
            raise LockStealError(
                f"holder pid {recheck_pid} revived before steal: {lock.lock_path}"
            )
        if stolen_text != text:
            # We displaced a lock rewritten after validation. Restore it if
            # nobody re-acquired meanwhile; either way, abort the steal.
            try:
                os.link(tombstone, lock.lock_path)
            except OSError:
                pass
            tombstone.unlink(missing_ok=True)
            raise LockStealError(f"lock changed before steal: {lock.lock_path}")
        try:
            fresh = cls(run_dir, name, owner=lock.owner, timeout_s=0.0).acquire()
        except LockTimeoutError as exc:
            tombstone.unlink(missing_ok=True)
            raise LockStealError(
                f"lost steal race to a fresh acquirer: {lock.lock_path}"
            ) from exc
        tombstone.unlink(missing_ok=True)
        # We now HOLD the lock; annotating our own file is race-free.
        annotated = {
            "owner": fresh.owner,
            "acquired_at": _now_iso(),
            "pid": os.getpid(),
            "stolen_from": payload.get("owner"),
        }
        tmp = fresh.lock_path.with_name(
            f".{fresh.lock_path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp"
        )
        tmp.write_text(json.dumps(annotated, sort_keys=True), encoding="utf-8")
        os.replace(tmp, fresh.lock_path)
        return fresh

    # --- Context manager --------------------------------------------------

    def __enter__(self) -> "FileLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._held:
            try:
                self.release()
            except LockOwnershipError:
                # Suppressed: someone else now owns the lock.
                # Caller's circuit-breaker handles the implication.
                self._held = False


class ConstructionLock(FileLock):
    """Long-held lock around artifact-building work for a single task."""

    def __init__(self, run_dir: Path, task_id: str, **kwargs: Any) -> None:
        super().__init__(run_dir, f"construction-{task_id}", **kwargs)
        self.task_id = task_id


class RequestLock(FileLock):
    """Short-held lock around a single external write-API call."""

    DEFAULT_TIMEOUT_S = 5.0  # request locks should be uncontested most of the time.

    def __init__(self, run_dir: Path, request_id: str, **kwargs: Any) -> None:
        kwargs.setdefault("timeout_s", self.DEFAULT_TIMEOUT_S)
        super().__init__(run_dir, f"request-{request_id}", **kwargs)
        self.request_id = request_id
