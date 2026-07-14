"""Crash-conscious JSONL event ledger."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Tuple

from .schema import CorruptEventError, KernelError, SequenceConflictError, WorkflowEvent


def encode_event(event: WorkflowEvent) -> bytes:
    return (json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class EventStore:
    def __init__(self, path):
        self.path = Path(path)
        self._lock_path = self.path.with_name(self.path.name + ".lock")

    def _acquire(self) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return os.open(str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise SequenceConflictError("event ledger has another writer", {"path": str(self.path)}) from exc

    def _release(self, descriptor: int) -> None:
        os.close(descriptor)
        try:
            self._lock_path.unlink()
        except FileNotFoundError:
            pass

    def append(self, event: WorkflowEvent, expected_sequence: int) -> None:
        if isinstance(expected_sequence, bool) or not isinstance(expected_sequence, int) or expected_sequence < 0:
            raise SequenceConflictError("invalid expected sequence", {"expected_sequence": expected_sequence})
        lock = self._acquire()
        try:
            events = self.replay()
            actual = len(events)
            if expected_sequence != actual or event.sequence != actual:
                raise SequenceConflictError("event sequence does not match ledger", {
                    "expected_sequence": expected_sequence, "event_sequence": event.sequence, "actual_sequence": actual,
                })
            if events and event.run_id != events[0].run_id:
                raise CorruptEventError("event run id conflicts with ledger", {"sequence": event.sequence})
            descriptor = os.open(str(self.path), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            try:
                data = encode_event(event)
                written = 0
                while written < len(data):
                    written += os.write(descriptor, data[written:])
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            self._release(lock)

    def replay(self) -> Tuple[WorkflowEvent, ...]:
        events, notes = self.validate(recovery=False)
        if notes:
            raise CorruptEventError("event ledger contains recovery notes", notes[0])
        return events

    def validate(self, recovery: bool = False):
        if not self.path.exists():
            return (), ()
        raw = self.path.read_bytes()
        if not raw:
            return (), ()
        lines = raw.splitlines(keepends=True)
        events: List[WorkflowEvent] = []
        notes = []
        offset = 0
        run_id = None
        for index, line in enumerate(lines):
            final = index == len(lines) - 1
            terminated = line.endswith(b"\n")
            try:
                if final and not terminated:
                    raise ValueError("final record has no newline")
                decoded = json.loads(line.decode("utf-8"))
                current = WorkflowEvent.from_dict(decoded)
            except (UnicodeDecodeError, json.JSONDecodeError, KernelError, ValueError) as exc:
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
        return tuple(events), tuple(notes)
