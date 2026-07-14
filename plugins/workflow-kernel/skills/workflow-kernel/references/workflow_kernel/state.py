"""Run-scoped lease and atomically materialized state."""

from __future__ import annotations

import errno
import json
import os
import tempfile
from pathlib import Path

from ._files import open_verified_regular, verified_regular_exists
from .schema import CorruptStateError, KernelError, LeaseConflictError, RevisionConflictError, RunState

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


MAX_STATE_BYTES = 4_194_304


def encode_state(state: RunState) -> bytes:
    return (json.dumps(state.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class RunLease:
    """Exclusive filesystem lease for a single run-state path."""

    def __init__(self, state_path):
        path = Path(state_path)
        self.state_path = Path(os.path.abspath(str(path)))
        self.path = path.with_name(path.name + ".lease")
        self._descriptor = None
        self._owner_pid = None

    def acquire(self):
        if fcntl is None:
            raise LeaseConflictError("crash-safe run locking is unavailable", {
                "reason_code": "locking_unsupported",
            })
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = open_verified_regular(self.path, os.O_CREAT | os.O_RDWR)
        except OSError as exc:
            raise LeaseConflictError("run lease path is unsafe", {"path": str(self.path)}) from exc
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            os.close(descriptor)
            raise LeaseConflictError("run already has a live writer lease", {"path": str(self.path)}) from exc
        try:
            os.ftruncate(descriptor, 0)
            os.write(descriptor, (str(os.getpid()) + "\n").encode("ascii"))
            os.fsync(descriptor)
        except Exception:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
            raise
        self._descriptor = descriptor
        self._owner_pid = os.getpid()
        return self

    def release(self):
        if self._descriptor is None:
            return
        fcntl.flock(self._descriptor, fcntl.LOCK_UN)
        os.close(self._descriptor)
        self._descriptor = None
        self._owner_pid = None

    def authorizes(self, state_path) -> bool:
        """Return whether this live capability owns the target state path."""
        if self._descriptor is None or self._owner_pid != os.getpid():
            return False
        try:
            os.fstat(self._descriptor)
        except OSError:
            return False
        return self.state_path == Path(os.path.abspath(str(state_path)))

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, traceback):
        self.release()
        return False


class StateStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self) -> RunState:
        try:
            descriptor = open_verified_regular(self.path, os.O_RDONLY)
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise CorruptStateError("materialized state path is unsafe", {"path": str(self.path)}) from exc
        try:
            if os.fstat(descriptor).st_size > MAX_STATE_BYTES:
                raise CorruptStateError("materialized state exceeds size limit", {"limit_bytes": MAX_STATE_BYTES})
            chunks = []
            remaining = MAX_STATE_BYTES + 1
            while remaining:
                chunk = os.read(descriptor, min(65_536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw_bytes = b"".join(chunks)
            if len(raw_bytes) > MAX_STATE_BYTES:
                raise CorruptStateError("materialized state exceeds size limit", {"limit_bytes": MAX_STATE_BYTES})
            raw = raw_bytes.decode("utf-8")
            data = json.loads(raw)
            return RunState.from_dict(data)
        except CorruptStateError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, KernelError) as exc:
            raise CorruptStateError("materialized state is corrupt", {"path": str(self.path)}) from exc
        finally:
            os.close(descriptor)

    def write(self, state: RunState, expected_revision: int, *, lease: RunLease = None) -> dict:
        if lease is None or not isinstance(lease, RunLease) or not lease.authorizes(self.path):
            raise LeaseConflictError("state write requires its acquired run lease", {"path": str(self.path)})
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < -1:
            raise RevisionConflictError("invalid expected revision", {"expected_revision": expected_revision})
        try:
            exists = verified_regular_exists(self.path)
        except OSError as exc:
            raise CorruptStateError("materialized state path is unsafe", {"path": str(self.path)}) from exc
        if exists:
            actual = self.load().revision
            if actual != expected_revision:
                raise RevisionConflictError("state revision changed", {"expected_revision": expected_revision, "actual_revision": actual})
            if state.revision < actual:
                raise RevisionConflictError("state revision cannot move backward", {
                    "candidate_revision": state.revision, "actual_revision": actual,
                })
        elif expected_revision != -1:
            raise RevisionConflictError("state does not exist at expected revision", {"expected_revision": expected_revision})

        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encode_state(state))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory_fsync = self._fsync_directory()
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return {"state_path": str(self.path), "revision": state.revision, "directory_fsync": directory_fsync}

    def _fsync_directory(self) -> str:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = None
        try:
            descriptor = os.open(str(self.path.parent), flags)
            os.fsync(descriptor)
            return "completed"
        except OSError as exc:
            unsupported = {errno.EINVAL, errno.EBADF, errno.EPERM}
            if hasattr(errno, "ENOTSUP"):
                unsupported.add(errno.ENOTSUP)
            if hasattr(errno, "EOPNOTSUPP"):
                unsupported.add(errno.EOPNOTSUPP)
            if exc.errno in unsupported:
                return "unsupported"
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)
