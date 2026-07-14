"""Run-scoped lease and atomically materialized state."""

from __future__ import annotations

import errno
import json
import os
import tempfile
import weakref
from pathlib import Path

from ._files import (
    LockContentionError, LockHandle, LockIdentityError, LockingUnsupportedError,
    canonical_path, open_verified_regular, verified_regular_exists,
)
from .schema import (
    CorruptStateError, ErrorDetailKey, ErrorMessage, KernelError, LeaseConflictError,
    RevisionConflictError, RunState, UnsafePayloadError, _snapshot_run_state,
)


MAX_STATE_BYTES = 4_194_304


def _snapshot_and_encode_state(state: RunState):
    snapshot = _snapshot_run_state(state)
    encoded = (json.dumps(RunState.to_dict(snapshot), ensure_ascii=False,
                          sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return snapshot, encoded


def encode_state(state: RunState) -> bytes:
    _, encoded = _snapshot_and_encode_state(state)
    return encoded


def _capability_types():
    lease_records = weakref.WeakKeyDictionary()
    store_records = weakref.WeakKeyDictionary()

    def finalize_lease(record, handle) -> None:
        if record.get("handle") is handle:
            record["handle"] = None
            record["owner_pid"] = None
            record["finalizer"] = None
        handle.release()

    class PreparedState:
        """Opaque identity capability issued and owned by one StateStore."""

        __slots__ = ("__weakref__",)

        def __new__(cls, *_args, **_kwargs):
            raise TypeError("prepared states are store-issued")

        def __init_subclass__(cls, **_kwargs):
            raise TypeError("PreparedState is final")

    class RunLease:
        """Exclusive registry-backed filesystem lease for one run-state path."""

        __slots__ = ("__weakref__",)

        def __init__(self, state_path):
            if self in lease_records:
                raise TypeError("RunLease is already initialized")
            state_path = canonical_path(Path(state_path))
            lease_records[self] = {
                "state_path": state_path,
                "path": state_path.with_name(state_path.name + ".lease"),
                "handle": None,
                "owner_pid": None,
                "finalizer": None,
            }

        def __init_subclass__(cls, **_kwargs):
            raise TypeError("RunLease is final")

        @property
        def state_path(self):
            return lease_records[self]["state_path"]

        @property
        def path(self):
            return lease_records[self]["path"]

        def acquire(self):
            if type(self) is not RunLease:
                raise LeaseConflictError(ErrorMessage.STATE_LEASE_REQUIRED)
            record = lease_records[self]
            if record["handle"] is not None:
                raise LeaseConflictError(ErrorMessage.RUN_WRITER_LEASE_HELD, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                })
            try:
                record["path"].parent.mkdir(parents=True, exist_ok=True)
                handle = LockHandle.acquire(record["path"])
            except LockingUnsupportedError:
                raise LeaseConflictError(ErrorMessage.RUN_LOCKING_UNAVAILABLE, {
                    ErrorDetailKey.REASON_CODE.value: "locking_unsupported",
                }) from None
            except LockIdentityError:
                raise LeaseConflictError(ErrorMessage.RUN_LEASE_IDENTITY_CHANGED, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                    ErrorDetailKey.REASON_CODE.value: "lease_identity_changed",
                }) from None
            except LockContentionError:
                raise LeaseConflictError(ErrorMessage.RUN_WRITER_LEASE_HELD, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                }) from None
            except OSError:
                raise LeaseConflictError(ErrorMessage.RUN_LEASE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                }) from None
            try:
                os.ftruncate(handle.descriptor, 0)
                os.write(handle.descriptor, (str(os.getpid()) + "\n").encode("ascii"))
                os.fsync(handle.descriptor)
            except OSError:
                handle.release()
                raise LeaseConflictError(ErrorMessage.RUN_LEASE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                }) from None
            except Exception:
                handle.release()
                raise
            record["handle"] = handle
            record["owner_pid"] = os.getpid()
            record["finalizer"] = weakref.finalize(self, finalize_lease, record, handle)
            return self

        def release(self):
            record = lease_records.get(self)
            if record is None or record["handle"] is None:
                return
            handle = record["handle"]
            record["handle"] = None
            record["owner_pid"] = None
            finalizer = record["finalizer"]
            record["finalizer"] = None
            if finalizer is not None and finalizer.alive:
                finalizer()
            else:
                handle.release()

        def __enter__(self):
            return self.acquire()

        def __exit__(self, exc_type, exc, traceback):
            self.release()
            return False

    def require_run_lease(lease, state_path) -> None:
        """Non-dispatching authorization for one exact live lease capability."""
        canonical = canonical_path(Path(state_path))
        if type(lease) is not RunLease:
            raise LeaseConflictError(ErrorMessage.STATE_LEASE_REQUIRED, {
                ErrorDetailKey.PATH.value: str(canonical),
            })
        record = lease_records.get(lease)
        if (record is None or record["handle"] is None
                or record["owner_pid"] != os.getpid()):
            raise LeaseConflictError(ErrorMessage.STATE_LEASE_REQUIRED, {
                ErrorDetailKey.PATH.value: str(canonical),
                ErrorDetailKey.REASON_CODE.value: "lease_not_owned",
            })
        if record["state_path"] != canonical:
            raise LeaseConflictError(ErrorMessage.STATE_LEASE_REQUIRED, {
                ErrorDetailKey.PATH.value: str(canonical),
                ErrorDetailKey.REASON_CODE.value: "lease_path_mismatch",
            })
        try:
            record["handle"].revalidate()
        except OSError:
            raise LeaseConflictError(ErrorMessage.RUN_LEASE_IDENTITY_CHANGED, {
                ErrorDetailKey.PATH.value: str(record["path"]),
                ErrorDetailKey.REASON_CODE.value: "lease_identity_changed",
            }) from None

    class StateStore:
        __slots__ = ("__weakref__",)

        def __init__(self, path):
            if self in store_records:
                raise TypeError("StateStore is already initialized")
            store_records[self] = {
                "path": canonical_path(Path(path)),
                "prepared": weakref.WeakKeyDictionary(),
            }

        def __init_subclass__(cls, **_kwargs):
            raise TypeError("StateStore is final")

        @property
        def path(self):
            return store_records[self]["path"]

        def load(self) -> RunState:
            path = store_records[self]["path"]
            try:
                descriptor = open_verified_regular(path, os.O_RDONLY)
            except FileNotFoundError:
                raise
            except OSError:
                raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(path),
                }) from None
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
                data = json.loads(raw_bytes.decode("utf-8"))
                return RunState.from_dict(data)
            except CorruptStateError:
                raise
            except (UnicodeDecodeError, json.JSONDecodeError, KernelError, RecursionError):
                raise CorruptStateError(ErrorMessage.STATE_CORRUPT, {
                    ErrorDetailKey.PATH.value: str(path),
                }) from None
            finally:
                os.close(descriptor)

        def write(self, state: RunState, expected_revision: int, *, lease: RunLease = None) -> dict:
            prepared = self.prepare(state)
            return self.publish(prepared, expected_revision, lease=lease)

        def publish(self, prepared: PreparedState, expected_revision: int,
                    *, lease: RunLease = None) -> dict:
            record = store_records[self]
            if type(prepared) is not PreparedState:
                raise UnsafePayloadError(ErrorMessage.PREPARED_STATE_WRONG_STORE, {
                    ErrorDetailKey.REASON_CODE.value: "prepared_state_owner_mismatch",
                })
            try:
                revision, encoded = record["prepared"][prepared]
            except (KeyError, TypeError):
                raise UnsafePayloadError(ErrorMessage.PREPARED_STATE_WRONG_STORE, {
                    ErrorDetailKey.REASON_CODE.value: "prepared_state_owner_mismatch",
                }) from None
            require_run_lease(lease, record["path"])
            if type(expected_revision) is not int or expected_revision < -1:
                raise RevisionConflictError(ErrorMessage.INVALID_EXPECTED_REVISION, {
                    ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                })
            try:
                exists = verified_regular_exists(record["path"])
            except OSError:
                raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                }) from None
            if exists:
                actual = self.load().revision
                if actual != expected_revision:
                    raise RevisionConflictError(ErrorMessage.STATE_REVISION_CHANGED, {
                        ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                        ErrorDetailKey.ACTUAL_REVISION.value: actual,
                    })
                if revision < actual:
                    raise RevisionConflictError(ErrorMessage.STATE_REVISION_BACKWARD, {
                        ErrorDetailKey.CANDIDATE_REVISION.value: revision,
                        ErrorDetailKey.ACTUAL_REVISION.value: actual,
                    })
            elif expected_revision != -1:
                raise RevisionConflictError(ErrorMessage.STATE_MISSING_AT_REVISION, {
                    ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                })

            path = record["path"]
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(
                    prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
                )
            except OSError:
                raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(path),
                }) from None
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                require_run_lease(lease, path)
                os.replace(temporary, path)
                directory_fsync = self._fsync_directory()
            except OSError:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(path),
                }) from None
            except Exception:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
            return {"state_path": str(path), "revision": revision,
                    "directory_fsync": directory_fsync}

        def prepare(self, state: RunState) -> PreparedState:
            snapshot, encoded = _snapshot_and_encode_state(state)
            if len(encoded) > MAX_STATE_BYTES:
                raise UnsafePayloadError(ErrorMessage.STATE_SIZE_LIMIT, {
                    ErrorDetailKey.LIMIT_BYTES.value: MAX_STATE_BYTES,
                })
            prepared = object.__new__(PreparedState)
            store_records[self]["prepared"][prepared] = (snapshot.revision, encoded)
            return prepared

        def _fsync_directory(self) -> str:
            path = store_records[self]["path"]
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            descriptor = None
            try:
                descriptor = os.open(str(path.parent), flags)
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

    return PreparedState, RunLease, StateStore, require_run_lease


PreparedState, RunLease, StateStore, _require_run_lease = _capability_types()
del _capability_types
