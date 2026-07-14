"""Run-scoped lease and atomically materialized state."""

from __future__ import annotations

import errno
import json
import os
import tempfile
import weakref
from dataclasses import dataclass
from pathlib import Path

from ._files import (
    LockContentionError, LockHandle, LockIdentityError, LockingUnsupportedError,
    canonical_path, open_verified_regular, verified_regular_exists,
)
from .schema import (
    CorruptStateError, ErrorDetailKey, ErrorMessage, KernelError, LeaseConflictError,
    RevisionConflictError, RunState, UnsafePayloadError,
)


MAX_STATE_BYTES = 4_194_304


def encode_state(state: RunState) -> bytes:
    return (json.dumps(state.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


@dataclass(frozen=True, eq=False)
class PreparedState:
    """Immutable state bytes authenticated for publication by one StateStore."""

    state: RunState
    encoded: bytes


class RunLease:
    """Exclusive filesystem lease for a single run-state path."""

    def __init__(self, state_path):
        self.state_path = canonical_path(Path(state_path))
        self.path = self.state_path.with_name(self.state_path.name + ".lease")
        self._handle = None
        self._owner_pid = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = LockHandle.acquire(self.path)
        except LockingUnsupportedError as exc:
            raise LeaseConflictError(ErrorMessage.RUN_LOCKING_UNAVAILABLE, {
                ErrorDetailKey.REASON_CODE.value: "locking_unsupported",
            }) from exc
        except LockIdentityError as exc:
            raise LeaseConflictError(ErrorMessage.RUN_LEASE_IDENTITY_CHANGED, {
                ErrorDetailKey.PATH.value: str(self.path),
                ErrorDetailKey.REASON_CODE.value: "lease_identity_changed",
            }) from exc
        except LockContentionError as exc:
            raise LeaseConflictError(ErrorMessage.RUN_WRITER_LEASE_HELD, {
                ErrorDetailKey.PATH.value: str(self.path),
            }) from exc
        except OSError as exc:
            raise LeaseConflictError(ErrorMessage.RUN_LEASE_PATH_UNSAFE, {
                ErrorDetailKey.PATH.value: str(self.path),
            }) from exc
        try:
            os.ftruncate(handle.descriptor, 0)
            os.write(handle.descriptor, (str(os.getpid()) + "\n").encode("ascii"))
            os.fsync(handle.descriptor)
        except Exception:
            handle.release()
            raise
        self._handle = handle
        self._owner_pid = os.getpid()
        return self

    def release(self):
        if self._handle is None:
            return
        handle = self._handle
        self._handle = None
        handle.release()
        self._owner_pid = None

    def require_authorized(self, state_path) -> None:
        """Require this live capability to own the target state path."""
        if self._handle is None or self._owner_pid != os.getpid():
            raise LeaseConflictError(ErrorMessage.STATE_LEASE_REQUIRED, {
                ErrorDetailKey.PATH.value: str(state_path),
                ErrorDetailKey.REASON_CODE.value: "lease_not_owned",
            })
        if self.state_path != canonical_path(Path(state_path)):
            raise LeaseConflictError(ErrorMessage.STATE_LEASE_REQUIRED, {
                ErrorDetailKey.PATH.value: str(state_path),
                ErrorDetailKey.REASON_CODE.value: "lease_path_mismatch",
            })
        try:
            self._handle.revalidate()
        except OSError as exc:
            raise LeaseConflictError(ErrorMessage.RUN_LEASE_IDENTITY_CHANGED, {
                ErrorDetailKey.PATH.value: str(self.path),
                ErrorDetailKey.REASON_CODE.value: "lease_identity_changed",
            }) from exc

    def authorizes(self, state_path) -> bool:
        """Return whether this live capability owns the target state path."""
        try:
            self.require_authorized(state_path)
        except LeaseConflictError:
            return False
        return True

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, traceback):
        self.release()
        return False


class StateStore:
    def __init__(self, path):
        self.path = canonical_path(Path(path))
        self._prepared = weakref.WeakSet()

    def load(self) -> RunState:
        try:
            descriptor = open_verified_regular(self.path, os.O_RDONLY)
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                ErrorDetailKey.PATH.value: str(self.path),
            }) from exc
        try:
            if os.fstat(descriptor).st_size > MAX_STATE_BYTES:
                raise CorruptStateError(ErrorMessage.STATE_SIZE_LIMIT, {
                    ErrorDetailKey.LIMIT_BYTES.value: MAX_STATE_BYTES,
                })
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
                raise CorruptStateError(ErrorMessage.STATE_SIZE_LIMIT, {
                    ErrorDetailKey.LIMIT_BYTES.value: MAX_STATE_BYTES,
                })
            raw = raw_bytes.decode("utf-8")
            data = json.loads(raw)
            return RunState.from_dict(data)
        except CorruptStateError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, KernelError, RecursionError) as exc:
            raise CorruptStateError(ErrorMessage.STATE_CORRUPT, {
                ErrorDetailKey.PATH.value: str(self.path),
            }) from exc
        finally:
            os.close(descriptor)

    def write(self, state: RunState, expected_revision: int, *, lease: RunLease = None) -> dict:
        prepared = self.prepare(state)
        return self.publish(prepared, expected_revision, lease=lease)

    def publish(self, prepared: PreparedState, expected_revision: int,
                *, lease: RunLease = None) -> dict:
        if (not isinstance(prepared, PreparedState)
                or prepared not in self._prepared):
            raise UnsafePayloadError(ErrorMessage.PREPARED_STATE_WRONG_STORE, {
                ErrorDetailKey.REASON_CODE.value: "prepared_state_owner_mismatch",
            })
        state = prepared.state
        if lease is None or not isinstance(lease, RunLease):
            raise LeaseConflictError(ErrorMessage.STATE_LEASE_REQUIRED, {
                ErrorDetailKey.PATH.value: str(self.path),
            })
        lease.require_authorized(self.path)
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < -1:
            raise RevisionConflictError(ErrorMessage.INVALID_EXPECTED_REVISION, {
                ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
            })
        try:
            exists = verified_regular_exists(self.path)
        except OSError as exc:
            raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                ErrorDetailKey.PATH.value: str(self.path),
            }) from exc
        if exists:
            actual = self.load().revision
            if actual != expected_revision:
                raise RevisionConflictError(ErrorMessage.STATE_REVISION_CHANGED, {
                    ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                    ErrorDetailKey.ACTUAL_REVISION.value: actual,
                })
            if state.revision < actual:
                raise RevisionConflictError(ErrorMessage.STATE_REVISION_BACKWARD, {
                    ErrorDetailKey.CANDIDATE_REVISION.value: state.revision,
                    ErrorDetailKey.ACTUAL_REVISION.value: actual,
                })
        elif expected_revision != -1:
            raise RevisionConflictError(ErrorMessage.STATE_MISSING_AT_REVISION, {
                ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
            })

        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(prepared.encoded)
                handle.flush()
                os.fsync(handle.fileno())
            lease.require_authorized(self.path)
            os.replace(temporary, self.path)
            directory_fsync = self._fsync_directory()
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return {"state_path": str(self.path), "revision": state.revision, "directory_fsync": directory_fsync}

    def prepare(self, state: RunState) -> PreparedState:
        """Return immutable state bytes authenticated for this store."""
        if not isinstance(state, RunState):
            raise UnsafePayloadError(ErrorMessage.PREPARED_STATE_RUN_STATE_REQUIRED)
        encoded = encode_state(state)
        if len(encoded) > MAX_STATE_BYTES:
            raise UnsafePayloadError(ErrorMessage.STATE_SIZE_LIMIT, {
                ErrorDetailKey.LIMIT_BYTES.value: MAX_STATE_BYTES,
            })
        prepared = PreparedState(state, encoded)
        self._prepared.add(prepared)
        return prepared

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
