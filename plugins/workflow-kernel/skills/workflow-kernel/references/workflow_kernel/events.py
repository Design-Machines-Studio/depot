"""Crash-conscious JSONL event ledger."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Tuple

from ._files import (
    LockContentionError, LockHandle, LockIdentityError, LockingUnsupportedError,
    canonical_path, open_verified_regular,
)
from .redaction import redact
from .schema import CorruptEventError, KernelError, SequenceConflictError, UnsafePayloadError, WorkflowEvent

MAX_RECORD_BYTES = 1_048_576
MAX_LEDGER_BYTES = 16_777_216


def encode_event(event: WorkflowEvent) -> bytes:
    try:
        safe = redact(event.to_dict())
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError("event contains unsafe durable data") from exc
    return (json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class EventStore:
    def __init__(self, path):
        self.path = canonical_path(Path(path))
        self._lock_path = self.path.with_name(self.path.name + ".lock")

    def _acquire(self) -> LockHandle:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return LockHandle.acquire(self._lock_path)
        except LockingUnsupportedError as exc:
            raise SequenceConflictError("crash-safe event locking is unavailable", {
                "reason_code": "locking_unsupported",
            }) from exc
        except LockIdentityError as exc:
            raise SequenceConflictError("event lock identity changed", {
                "path": str(self._lock_path), "reason_code": "lock_identity_changed",
            }) from exc
        except LockContentionError as exc:
            raise SequenceConflictError("event ledger has another writer", {"path": str(self.path)}) from exc
        except OSError as exc:
            raise SequenceConflictError("event lock path is unsafe", {"path": str(self.path)}) from exc

    def _release(self, handle: LockHandle) -> None:
        handle.release()

    def _require_current_lock(self, handle: LockHandle) -> None:
        try:
            handle.revalidate()
        except OSError as exc:
            raise SequenceConflictError("event lock identity changed", {
                "path": str(self._lock_path), "reason_code": "lock_identity_changed",
            }) from exc

    def append(self, event: WorkflowEvent, expected_sequence: int) -> None:
        if isinstance(expected_sequence, bool) or not isinstance(expected_sequence, int) or expected_sequence < 0:
            raise SequenceConflictError("invalid expected sequence", {"expected_sequence": expected_sequence})
        data = encode_event(event)
        if len(data) > MAX_RECORD_BYTES:
            raise UnsafePayloadError("event record exceeds size limit", {"limit_bytes": MAX_RECORD_BYTES})
        lock = self._acquire()
        try:
            self._require_current_lock(lock)
            try:
                descriptor = open_verified_regular(self.path, os.O_CREAT | os.O_APPEND | os.O_RDWR)
            except OSError as exc:
                raise CorruptEventError("event ledger path is unsafe", {"path": str(self.path)}) from exc
            try:
                with os.fdopen(os.dup(descriptor), "rb") as handle:
                    events, _ = self._validate_handle(handle, recovery=False)
                actual = len(events)
                if expected_sequence != actual or event.sequence != actual:
                    raise SequenceConflictError("event sequence does not match ledger", {
                        "expected_sequence": expected_sequence, "event_sequence": event.sequence,
                        "actual_sequence": actual,
                    })
                if events and event.run_id != events[0].run_id:
                    raise CorruptEventError("event run id conflicts with ledger", {"sequence": event.sequence})
                if os.fstat(descriptor).st_size + len(data) > MAX_LEDGER_BYTES:
                    raise UnsafePayloadError("event ledger would exceed size limit", {
                        "limit_bytes": MAX_LEDGER_BYTES,
                    })
                self._require_current_lock(lock)
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
        try:
            descriptor = open_verified_regular(self.path, os.O_RDONLY)
        except FileNotFoundError:
            return (), ()
        except OSError as exc:
            raise CorruptEventError("event ledger path is unsafe", {"path": str(self.path)}) from exc
        with os.fdopen(descriptor, "rb") as handle:
            return self._validate_handle(handle, recovery)

    def _validate_handle(self, handle, recovery: bool):
        size = os.fstat(handle.fileno()).st_size
        if size > MAX_LEDGER_BYTES:
            raise CorruptEventError("event ledger exceeds size limit", {"limit_bytes": MAX_LEDGER_BYTES})
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
                raise CorruptEventError("event ledger exceeds size limit", {"limit_bytes": MAX_LEDGER_BYTES})
            if len(line) > MAX_RECORD_BYTES:
                raise CorruptEventError("event record exceeds size limit", {"byte_offset": offset, "limit_bytes": MAX_RECORD_BYTES})
            terminated = line.endswith(b"\n")
            try:
                if final and not terminated:
                    raise ValueError("final record has no newline")
                decoded = json.loads(line.decode("utf-8"))
                current = WorkflowEvent.from_dict(decoded)
            except (UnicodeDecodeError, json.JSONDecodeError, KernelError, ValueError, RecursionError) as exc:
                if final and not terminated and recovery:
                    notes.append({"code": "truncated_final_record", "byte_offset": offset})
                    break
                raise CorruptEventError("invalid event record", {"byte_offset": offset, "record": index + 1}) from exc
            if current.sequence != len(events):
                raise SequenceConflictError("event ledger sequence is not contiguous", {
                    "byte_offset": offset, "expected_sequence": len(events), "actual_sequence": current.sequence,
                })
            if run_id is None:
                run_id = current.run_id
            elif current.run_id != run_id:
                raise CorruptEventError("event ledger contains conflicting run ids", {"byte_offset": offset})
            events.append(current)
            offset += len(line)
            index += 1
            line = next_line
        return tuple(events), tuple(notes)
