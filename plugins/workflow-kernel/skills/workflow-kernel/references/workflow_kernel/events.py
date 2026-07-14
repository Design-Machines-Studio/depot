"""Crash-conscious JSONL event ledger."""

from __future__ import annotations

import json
import os
import weakref
from pathlib import Path
from typing import List, Tuple

from ._files import (
    LockContentionError, LockHandle, LockIdentityError, LockingUnsupportedError,
    canonical_path, open_verified_regular,
)
from .redaction import redact
from .schema import (
    CorruptEventError, ErrorDetailKey, ErrorMessage, KernelError, SequenceConflictError,
    UnsafePayloadError, WorkflowEvent, _snapshot_workflow_event,
)
from .state import RunLease, _require_run_lease

MAX_RECORD_BYTES = 1_048_576
MAX_LEDGER_BYTES = 16_777_216


def _snapshot_and_encode_event(event: WorkflowEvent):
    try:
        snapshot = _snapshot_workflow_event(event)
        safe = redact(WorkflowEvent.to_dict(snapshot))
    except (KernelError, TypeError, ValueError):
        raise UnsafePayloadError(ErrorMessage.EVENT_UNSAFE_DURABLE_DATA) from None
    encoded = (json.dumps(safe, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    return snapshot, encoded


def encode_event(event: WorkflowEvent) -> bytes:
    _, encoded = _snapshot_and_encode_event(event)
    return encoded


def _event_store_type():
    records = weakref.WeakKeyDictionary()

    class EventStore:
        __slots__ = ("__weakref__",)

        def __init__(self, run_root):
            if self in records:
                raise TypeError("EventStore is already initialized")
            root = canonical_path(Path(run_root))
            path = root / "events.jsonl"
            records[self] = {
                "root": root,
                "path": path,
                "state_path": root / "run-state.json",
                "lock_path": path.with_name(path.name + ".lock"),
            }

        def __init_subclass__(cls, **_kwargs):
            raise TypeError("EventStore is final")

        @property
        def root(self):
            return records[self]["root"]

        @property
        def path(self):
            return records[self]["path"]

        @property
        def state_path(self):
            return records[self]["state_path"]

        @property
        def _lock_path(self):
            return records[self]["lock_path"]

        def _acquire(self) -> LockHandle:
            record = records[self]
            try:
                record["path"].parent.mkdir(parents=True, exist_ok=True)
                return LockHandle.acquire(record["lock_path"])
            except LockingUnsupportedError:
                raise SequenceConflictError(ErrorMessage.EVENT_LOCKING_UNAVAILABLE, {
                    ErrorDetailKey.REASON_CODE.value: "locking_unsupported",
                }) from None
            except LockIdentityError:
                raise SequenceConflictError(ErrorMessage.EVENT_LOCK_IDENTITY_CHANGED, {
                    ErrorDetailKey.PATH.value: str(record["lock_path"]),
                    ErrorDetailKey.REASON_CODE.value: "lock_identity_changed",
                }) from None
            except LockContentionError:
                raise SequenceConflictError(ErrorMessage.LEDGER_ANOTHER_WRITER, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                }) from None
            except OSError:
                raise SequenceConflictError(ErrorMessage.EVENT_LOCK_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(record["path"]),
                }) from None

        def _release(self, handle: LockHandle) -> None:
            handle.release()

        def _require_current_lock(self, handle: LockHandle) -> None:
            record = records[self]
            try:
                handle.revalidate()
            except OSError:
                raise SequenceConflictError(ErrorMessage.EVENT_LOCK_IDENTITY_CHANGED, {
                    ErrorDetailKey.PATH.value: str(record["lock_path"]),
                    ErrorDetailKey.REASON_CODE.value: "lock_identity_changed",
                }) from None

        def append(self, event: WorkflowEvent, expected_sequence: int, *, lease: RunLease) -> None:
            record = records[self]
            _require_run_lease(lease, record["state_path"])
            if type(expected_sequence) is not int or expected_sequence < 0:
                raise SequenceConflictError(ErrorMessage.INVALID_EXPECTED_SEQUENCE, {
                    ErrorDetailKey.EXPECTED_SEQUENCE.value: expected_sequence,
                })
            event_snapshot, data = _snapshot_and_encode_event(event)
            if len(data) > MAX_RECORD_BYTES:
                raise UnsafePayloadError(ErrorMessage.EVENT_RECORD_SIZE_LIMIT, {
                    ErrorDetailKey.LIMIT_BYTES.value: MAX_RECORD_BYTES,
                })
            lock = self._acquire()
            try:
                self._require_current_lock(lock)
                try:
                    descriptor = open_verified_regular(
                        record["path"], os.O_CREAT | os.O_APPEND | os.O_RDWR,
                    )
                except OSError:
                    raise CorruptEventError(ErrorMessage.LEDGER_PATH_UNSAFE, {
                        ErrorDetailKey.PATH.value: str(record["path"]),
                    }) from None
                try:
                    with os.fdopen(os.dup(descriptor), "rb") as handle:
                        events, _ = self._validate_handle(handle, recovery=False)
                    actual = len(events)
                    if expected_sequence != actual or event_snapshot.sequence != actual:
                        raise SequenceConflictError(ErrorMessage.EVENT_SEQUENCE_LEDGER_MISMATCH, {
                            ErrorDetailKey.EXPECTED_SEQUENCE.value: expected_sequence,
                            ErrorDetailKey.EVENT_SEQUENCE.value: event_snapshot.sequence,
                            ErrorDetailKey.ACTUAL_SEQUENCE.value: actual,
                        })
                    if events and event_snapshot.run_id != events[0].run_id:
                        raise CorruptEventError(ErrorMessage.EVENT_RUN_ID_CONFLICT, {
                            ErrorDetailKey.SEQUENCE.value: event_snapshot.sequence,
                        })
                    if os.fstat(descriptor).st_size + len(data) > MAX_LEDGER_BYTES:
                        raise UnsafePayloadError(ErrorMessage.LEDGER_PROJECTED_SIZE_LIMIT, {
                            ErrorDetailKey.LIMIT_BYTES.value: MAX_LEDGER_BYTES,
                        })
                    self._require_current_lock(lock)
                    _require_run_lease(lease, record["state_path"])
                    written = 0
                    while written < len(data):
                        written += os.write(descriptor, data[written:])
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            finally:
                self._release(lock)

        def replay(self) -> Tuple[WorkflowEvent, ...]:
            events, _ = self.validate(recovery=False)
            return events

        def validate(self, recovery: bool = False):
            path = records[self]["path"]
            try:
                descriptor = open_verified_regular(path, os.O_RDONLY)
            except FileNotFoundError:
                return (), ()
            except OSError:
                raise CorruptEventError(ErrorMessage.LEDGER_PATH_UNSAFE, {
                    ErrorDetailKey.PATH.value: str(path),
                }) from None
            with os.fdopen(descriptor, "rb") as handle:
                return self._validate_handle(handle, recovery)

        def _validate_handle(self, handle, recovery: bool):
            size = os.fstat(handle.fileno()).st_size
            if size > MAX_LEDGER_BYTES:
                raise CorruptEventError(ErrorMessage.LEDGER_SIZE_LIMIT, {
                    ErrorDetailKey.LIMIT_BYTES.value: MAX_LEDGER_BYTES,
                })
            if size == 0:
                return (), ()
            events: List[WorkflowEvent] = []
            notes = []
            offset = 0
            total = 0
            run_id = None
            line = handle.readline(MAX_RECORD_BYTES + 2)
            index = 0
            while line:
                next_line = handle.readline(MAX_RECORD_BYTES + 2)
                final = not next_line
                total += len(line)
                if total > MAX_LEDGER_BYTES:
                    raise CorruptEventError(ErrorMessage.LEDGER_SIZE_LIMIT, {
                        ErrorDetailKey.LIMIT_BYTES.value: MAX_LEDGER_BYTES,
                    })
                if len(line) > MAX_RECORD_BYTES:
                    raise CorruptEventError(ErrorMessage.EVENT_RECORD_SIZE_LIMIT, {
                        ErrorDetailKey.BYTE_OFFSET.value: offset,
                        ErrorDetailKey.LIMIT_BYTES.value: MAX_RECORD_BYTES,
                    })
                terminated = line.endswith(b"\n")
                try:
                    if final and not terminated:
                        raise ValueError("final record has no newline")
                    decoded = json.loads(line.decode("utf-8"))
                    current = WorkflowEvent.from_dict(decoded)
                except (UnicodeDecodeError, json.JSONDecodeError, KernelError, ValueError, RecursionError):
                    if final and not terminated and recovery:
                        notes.append({"code": "truncated_final_record", "byte_offset": offset})
                        break
                    raise CorruptEventError(ErrorMessage.INVALID_EVENT_RECORD, {
                        ErrorDetailKey.BYTE_OFFSET.value: offset,
                        ErrorDetailKey.RECORD.value: index + 1,
                    }) from None
                if current.sequence != len(events):
                    raise SequenceConflictError(ErrorMessage.LEDGER_SEQUENCE_NONCONTIGUOUS, {
                        ErrorDetailKey.BYTE_OFFSET.value: offset,
                        ErrorDetailKey.EXPECTED_SEQUENCE.value: len(events),
                        ErrorDetailKey.ACTUAL_SEQUENCE.value: current.sequence,
                    })
                if run_id is None:
                    run_id = current.run_id
                elif current.run_id != run_id:
                    raise CorruptEventError(ErrorMessage.LEDGER_CONFLICTING_RUN_IDS, {
                        ErrorDetailKey.BYTE_OFFSET.value: offset,
                    })
                events.append(current)
                offset += len(line)
                index += 1
                line = next_line
            return tuple(events), tuple(notes)

    return EventStore


EventStore = _event_store_type()
del _event_store_type
