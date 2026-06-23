"""Write-lock discipline for fleet workers.

Implements the WRITE-LOCK DISCIPLINE doctrine from engine.md. Two lock
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


class FileLock:
    """File-based exclusive lock under a run-archive's ``locks/`` dir.

    Acquire is exclusive-create (``O_CREAT|O_EXCL``); release is
    owner-checked. Stealing is a separate, explicit primitive that
    callers MUST gate on a confirmed-dead signal.
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
            try:
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(
                        f"acquire timed out after {self.timeout_s}s: {self.lock_path}"
                    )
                time.sleep(delay)
                delay = min(delay * 2, self.max_poll_interval_s)
                continue

            payload = {
                "owner": self.owner,
                "acquired_at": _now_iso(),
                "pid": os.getpid(),
            }
            try:
                os.write(fd, json.dumps(payload, sort_keys=True).encode("utf-8"))
            finally:
                os.close(fd)
            self._held = True
            return self

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

        Refuses to steal unless the holder pid is verifiably dead.
        Age-based fallback (``max_stale_s``) covers the case where the
        holder is on a different host and pid liveness can't be checked
        locally — but the caller's circuit-breaker discipline MUST have
        already declared the holder dead before invoking this.
        """
        lock = cls(run_dir, name, owner=new_owner or f"pid-{os.getpid()}-stolen")
        if not lock.lock_path.is_file():
            raise LockStealError(f"no lock to steal: {lock.lock_path}")

        text = lock.lock_path.read_text(encoding="utf-8")
        try:
            payload: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as exc:
            # Garbled lock file is a corruption signal, not stealable.
            raise LockStealError(
                f"lock file unparseable: {lock.lock_path} ({exc})"
            ) from exc

        holder_pid = payload.get("pid")
        if isinstance(holder_pid, int) and _pid_alive(holder_pid):
            # Age check as a tiebreaker for cross-host setups.
            acquired = payload.get("acquired_at")
            age_s = float("inf")
            if isinstance(acquired, str):
                try:
                    acquired_dt = datetime.strptime(acquired, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    )
                    age_s = (datetime.now(timezone.utc) - acquired_dt).total_seconds()
                except ValueError:
                    age_s = float("inf")
            if age_s < max_stale_s:
                raise LockStealError(
                    f"holder pid {holder_pid} still alive and lock age "
                    f"{age_s:.0f}s < max_stale_s={max_stale_s}: {lock.lock_path}"
                )

        # Holder gone (or stale beyond max_stale_s) — replace atomically.
        new_payload = {
            "owner": lock.owner,
            "acquired_at": _now_iso(),
            "pid": os.getpid(),
            "stolen_from": payload.get("owner"),
        }
        tmp = lock.lock_path.with_suffix(".lock.tmp")
        tmp.write_text(json.dumps(new_payload, sort_keys=True), encoding="utf-8")
        os.replace(tmp, lock.lock_path)
        lock._held = True
        return lock

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
