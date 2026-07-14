"""Run-scoped lease and atomically materialized state."""

from __future__ import annotations

import json
import os
import weakref
from pathlib import Path

from ._files import (
    LockContentionError, LockHandle, LockIdentityError, LockingUnsupportedError,
    _OwnedResourceScope, bind_durable_path,
)
from .schema import (
    CorruptStateError, ErrorDetailKey, ErrorMessage, InvalidSchemaError, KernelError,
    LeaseConflictError, RevisionConflictError, RunState, UnsafePayloadError,
    _snapshot_run_state,
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


def _read_state_descriptor(descriptor: int, path: Path) -> RunState:
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
    try:
        return RunState.from_dict(json.loads(raw_bytes.decode("utf-8")))
    except CorruptStateError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, KernelError, RecursionError):
        raise CorruptStateError(ErrorMessage.STATE_CORRUPT, {
            ErrorDetailKey.PATH.value: str(path),
        }) from None


def _capability_types():
    lease_records = weakref.WeakKeyDictionary()
    store_records = weakref.WeakKeyDictionary()
    monotonic_issuance = object()
    ledger_reconciliation_issuance = object()

    def issue_prepared(record, state, issuance_mode, expected_revision=None):
        snapshot, encoded = _snapshot_and_encode_state(state)
        if len(encoded) > MAX_STATE_BYTES:
            raise UnsafePayloadError(ErrorMessage.STATE_SIZE_LIMIT, {
                ErrorDetailKey.LIMIT_BYTES.value: MAX_STATE_BYTES,
            })
        prepared = object.__new__(PreparedState)
        record["prepared"][prepared] = (
            snapshot.revision, encoded, issuance_mode, expected_revision,
        )
        return prepared

    def finalize_lease(record, handle, owner_pid) -> None:
        if record.get("handle") is handle:
            record["handle"] = None
            record["owner_pid"] = None
            record["finalizer"] = None
        try:
            if owner_pid == os.getpid():
                handle.release()
            else:
                handle.close_inherited()
        except OSError:
            pass

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
            requested = Path(state_path)
            try:
                binding = bind_durable_path(requested)
            except OSError:
                raise LeaseConflictError(ErrorMessage.RUN_LEASE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(requested),
                }) from None
            state_path = binding.path
            lease_records[self] = {
                "state_path": state_path,
                "path": state_path.with_name(state_path.name + ".lease"),
                "binding": binding,
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
                record["binding"].revalidate_parent()
                record["path"].parent.mkdir(parents=True, exist_ok=True)
                if record["binding"].parent_identity is None:
                    record["binding"] = bind_durable_path(record["state_path"])
                handle = LockHandle.acquire_bound(bind_durable_path(record["path"]))
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
                try:
                    handle.release()
                except BaseException:
                    pass
                raise LeaseConflictError(ErrorMessage.RUN_LEASE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                }) from None
            except Exception:
                try:
                    handle.release()
                except BaseException:
                    pass
                raise
            record["handle"] = handle
            record["owner_pid"] = os.getpid()
            record["finalizer"] = weakref.finalize(
                self, finalize_lease, record, handle, record["owner_pid"],
            )
            return self

        def release(self):
            record = lease_records.get(self)
            if record is None or record["handle"] is None:
                return
            handle = record["handle"]
            owner_pid = record["owner_pid"]
            record["handle"] = None
            record["owner_pid"] = None
            finalizer = record["finalizer"]
            record["finalizer"] = None
            if finalizer is not None and finalizer.alive:
                finalizer.detach()
            try:
                if owner_pid == os.getpid():
                    handle.release()
                else:
                    handle.close_inherited()
            except OSError:
                raise LeaseConflictError(ErrorMessage.RUN_LEASE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                }) from None

        def __enter__(self):
            return self.acquire()

        def __exit__(self, exc_type, exc, traceback):
            try:
                self.release()
            except BaseException:
                if exc_type is None:
                    raise
            return False

    def require_run_lease(lease, state_path) -> None:
        """Non-dispatching authorization for one exact live lease capability."""
        try:
            canonical = bind_durable_path(Path(state_path)).path
        except OSError:
            raise LeaseConflictError(ErrorMessage.RUN_LEASE_PATH_UNSAFE) from None
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
            requested = Path(path)
            try:
                binding = bind_durable_path(requested)
            except OSError:
                raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(requested),
                }) from None
            store_records[self] = {
                "path": binding.path,
                "binding": binding,
                "prepared": weakref.WeakKeyDictionary(),
            }

        def __init_subclass__(cls, **_kwargs):
            raise TypeError("StateStore is final")

        @property
        def path(self):
            return store_records[self]["path"]

        def require_absent(self) -> None:
            record = store_records[self]
            path = record["path"]
            try:
                with _OwnedResourceScope() as scope:
                    directory = scope.pin(record["binding"])
                    directory.require_absent(path.name)
            except FileExistsError:
                raise InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_INITIALIZED, {
                    ErrorDetailKey.DIRECTORY.value: str(path.parent),
                }) from None
            except OSError:
                raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(path),
                }) from None

        def load(self) -> RunState:
            record = store_records[self]
            path = record["path"]
            try:
                with _OwnedResourceScope() as scope:
                    try:
                        directory = scope.pin(record["binding"])
                    except FileNotFoundError:
                        raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                            ErrorDetailKey.PATH.value: str(path),
                        }) from None
                    try:
                        descriptor = scope.own(
                            directory.open_regular(path.name, os.O_RDONLY),
                        )
                    except FileNotFoundError:
                        directory.revalidate()
                        raise
                    result = _read_state_descriptor(descriptor, path)
                    directory.revalidate()
                    directory.require_identity(descriptor, path.name)
                    return result
            except FileNotFoundError:
                raise
            except CorruptStateError:
                raise
            except OSError:
                raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(path),
                }) from None

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
                revision, encoded, issuance_mode, issued_expected_revision = record["prepared"][prepared]
            except (KeyError, TypeError):
                raise UnsafePayloadError(ErrorMessage.PREPARED_STATE_WRONG_STORE, {
                    ErrorDetailKey.REASON_CODE.value: "prepared_state_owner_mismatch",
                }) from None
            require_run_lease(lease, record["path"])
            if type(expected_revision) is not int or expected_revision < -1:
                raise RevisionConflictError(ErrorMessage.INVALID_EXPECTED_REVISION, {
                    ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                })
            if (issuance_mode is ledger_reconciliation_issuance
                    and expected_revision != issued_expected_revision):
                raise RevisionConflictError(ErrorMessage.INVALID_EXPECTED_REVISION, {
                    ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                    ErrorDetailKey.REASON_CODE.value: "prepared_expected_revision_mismatch",
                })
            if issuance_mode is ledger_reconciliation_issuance:
                try:
                    record["prepared"].pop(prepared)
                except (KeyError, TypeError):
                    raise UnsafePayloadError(ErrorMessage.PREPARED_STATE_WRONG_STORE, {
                        ErrorDetailKey.REASON_CODE.value: "prepared_state_owner_mismatch",
                    }) from None
            path = record["path"]
            if record["binding"].parent_identity is None:
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    record["binding"] = bind_durable_path(path)
                except OSError:
                    raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                        ErrorDetailKey.PATH.value: str(path),
                    }) from None
            try:
                with _OwnedResourceScope() as scope:
                    directory = scope.pin(record["binding"])
                    try:
                        observed = scope.own(
                            directory.open_regular(path.name, os.O_RDONLY),
                        )
                    except FileNotFoundError:
                        observed = None
                    if observed is not None:
                        actual = _read_state_descriptor(observed, path).revision
                        directory.require_identity(observed, path.name)
                        if actual != expected_revision:
                            raise RevisionConflictError(ErrorMessage.STATE_REVISION_CHANGED, {
                                ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                                ErrorDetailKey.ACTUAL_REVISION.value: actual,
                            })
                        if (issuance_mode is not ledger_reconciliation_issuance
                                and revision < actual):
                            raise RevisionConflictError(ErrorMessage.STATE_REVISION_BACKWARD, {
                                ErrorDetailKey.CANDIDATE_REVISION.value: revision,
                                ErrorDetailKey.ACTUAL_REVISION.value: actual,
                            })
                    elif expected_revision != -1:
                        raise RevisionConflictError(ErrorMessage.STATE_MISSING_AT_REVISION, {
                            ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                        })
                    descriptor, temporary = directory.create_temporary(
                        prefix=f".{path.name}.", suffix=".tmp",
                    )
                    scope.own_temporary(descriptor, temporary)
                    with os.fdopen(descriptor, "wb", closefd=False) as handle:
                        handle.write(encoded)
                        handle.flush()
                        os.fsync(handle.fileno())
                    directory.require_identity(descriptor, temporary)
                    require_run_lease(lease, path)
                    directory.revalidate()
                    if observed is None:
                        if directory.regular_exists(path.name):
                            current = scope.own(
                                directory.open_regular(path.name, os.O_RDONLY),
                            )
                            actual = _read_state_descriptor(current, path).revision
                            raise RevisionConflictError(ErrorMessage.STATE_REVISION_CHANGED, {
                                ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                                ErrorDetailKey.ACTUAL_REVISION.value: actual,
                            })
                    else:
                        try:
                            directory.require_identity(observed, path.name)
                        except OSError:
                            current = scope.own(
                                directory.open_regular(path.name, os.O_RDONLY),
                            )
                            actual = _read_state_descriptor(current, path).revision
                            raise RevisionConflictError(ErrorMessage.STATE_REVISION_CHANGED, {
                                ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                                ErrorDetailKey.ACTUAL_REVISION.value: actual,
                            }) from None
                        os.lseek(observed, 0, os.SEEK_SET)
                        actual = _read_state_descriptor(observed, path).revision
                        if actual != expected_revision:
                            raise RevisionConflictError(ErrorMessage.STATE_REVISION_CHANGED, {
                                ErrorDetailKey.EXPECTED_REVISION.value: expected_revision,
                                ErrorDetailKey.ACTUAL_REVISION.value: actual,
                            })
                    directory.replace(temporary, path.name)
                    scope.disown_temporary()
                    directory_fsync = directory.fsync()
                    directory.revalidate()
                    directory.require_identity(descriptor, path.name)
            except OSError:
                raise CorruptStateError(ErrorMessage.STATE_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(path),
                }) from None
            return {"state_path": str(path), "revision": revision,
                    "directory_fsync": directory_fsync}

        def prepare(self, state: RunState) -> PreparedState:
            return issue_prepared(
                store_records[self], state, monotonic_issuance,
            )

    def prepare_replay_state(store, state, expected_revision) -> PreparedState:
        """Issue a private ledger-reconciliation capability for CLI replay."""
        if type(store) is not StateStore:
            raise UnsafePayloadError(ErrorMessage.PREPARED_STATE_WRONG_STORE, {
                ErrorDetailKey.REASON_CODE.value: "prepared_state_owner_mismatch",
            })
        return issue_prepared(
            store_records[store], state, ledger_reconciliation_issuance,
            expected_revision,
        )

    return PreparedState, RunLease, StateStore, require_run_lease, prepare_replay_state


PreparedState, RunLease, StateStore, _require_run_lease, _prepare_replay_state = _capability_types()
del _capability_types
