"""Run-scoped lease and atomically materialized state."""

from __future__ import annotations

import errno
import json
import os
import tempfile
from pathlib import Path

from .schema import CorruptEventError, InvalidSchemaError, LeaseConflictError, RevisionConflictError, RunState

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


def encode_state(state: RunState) -> bytes:
    return (json.dumps(state.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class RunLease:
    """Exclusive filesystem lease for a single run-state path."""

    def __init__(self, state_path):
        path = Path(state_path)
        self.state_path = Path(os.path.abspath(str(path)))
        self.path = path.with_name(path.name + ".lease")
        self._descriptor = None
        self._exclusive_file = False
        self._owner_pid = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if fcntl is not None:
            descriptor = os.open(str(self.path), os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError) as exc:
                os.close(descriptor)
                raise LeaseConflictError("run already has a live writer lease", {"path": str(self.path)}) from exc
            os.ftruncate(descriptor, 0)
        else:
            try:
                descriptor = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                self._exclusive_file = True
            except FileExistsError as exc:
                raise LeaseConflictError("run already has a live writer lease", {"path": str(self.path)}) from exc
        try:
            os.write(descriptor, (str(os.getpid()) + "\n").encode("ascii"))
            os.fsync(descriptor)
        except Exception:
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
            if self._exclusive_file:
                self.path.unlink(missing_ok=True)
                self._exclusive_file = False
            raise
        self._descriptor = descriptor
        self._owner_pid = os.getpid()
        return self

    def release(self):
        if self._descriptor is None:
            return
        if fcntl is not None:
            fcntl.flock(self._descriptor, fcntl.LOCK_UN)
        os.close(self._descriptor)
        self._descriptor = None
        self._owner_pid = None
        if self._exclusive_file:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self._exclusive_file = False

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
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return RunState.from_dict(data)
        except FileNotFoundError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, InvalidSchemaError) as exc:
            raise CorruptEventError("materialized state is corrupt", {"path": str(self.path)}) from exc

    def write(self, state: RunState, expected_revision: int, *, lease: RunLease = None) -> dict:
        if lease is None or not isinstance(lease, RunLease) or not lease.authorizes(self.path):
            raise LeaseConflictError("state write requires its acquired run lease", {"path": str(self.path)})
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < -1:
            raise RevisionConflictError("invalid expected revision", {"expected_revision": expected_revision})
        if self.path.exists():
            actual = self.load().revision
            if actual != expected_revision:
                raise RevisionConflictError("state revision changed", {"expected_revision": expected_revision, "actual_revision": actual})
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
