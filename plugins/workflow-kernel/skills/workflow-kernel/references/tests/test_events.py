import tempfile
import unittest
import os
from pathlib import Path
from unittest import mock

from workflow_kernel.events import EventStore
from workflow_kernel.schema import CorruptEventError, SequenceConflictError, WorkflowEvent


def event(sequence):
    return WorkflowEvent(1, sequence, "run-1", None, "evidence.recorded", "2026-07-14T00:00:00Z", {"evidence": [str(sequence)]})


class EventStoreTests(unittest.TestCase):
    def test_append_replay_and_sequence_conflict_preserves_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = EventStore(path)
            store.append(event(0), expected_sequence=0)
            before = path.read_bytes()
            with self.assertRaises(SequenceConflictError):
                store.append(event(2), expected_sequence=1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(store.replay(), (event(0),))

    def test_corrupt_earlier_record_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_bytes(b"{bad}\n{}\n")
            with self.assertRaises(CorruptEventError):
                EventStore(path).replay()

    def test_recovery_reports_truncated_final_record_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = EventStore(path)
            store.append(event(0), 0)
            offset = path.stat().st_size
            with path.open("ab") as handle:
                handle.write(b'{"schema_version":')
            with self.assertRaises(CorruptEventError):
                store.replay()
            recovered, notes = store.validate(recovery=True)
            self.assertEqual(recovered, (event(0),))
            self.assertEqual(notes[0]["byte_offset"], offset)

    def test_stale_lock_file_does_not_block_append(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.with_name(path.name + ".lock").write_text("crashed writer")
            EventStore(path).append(event(0), 0)
            self.assertEqual(EventStore(path).replay(), (event(0),))

    def test_live_event_writer_contention_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "events.jsonl")
            lock = store._acquire()
            try:
                with self.assertRaises(SequenceConflictError):
                    store.append(event(0), 0)
            finally:
                store._release(lock)

    def test_unlinked_live_event_lock_cannot_mutate_alongside_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = EventStore(path)
            first = store._acquire()
            store._lock_path.unlink()
            second = store._acquire()
            try:
                stale = first
                first = None
                with mock.patch.object(store, "_acquire", return_value=stale):
                    with self.assertRaises(SequenceConflictError) as raised:
                        store.append(event(0), 0)
                self.assertEqual(raised.exception.details["reason_code"], "lock_identity_changed")
                self.assertFalse(path.exists())
                with self.assertRaises(SequenceConflictError):
                    store.append(event(0), 0)
            finally:
                if first is not None:
                    store._release(first)
                store._release(second)
            store.append(event(0), 0)

    def test_replaced_live_event_lock_cannot_mutate_alongside_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = EventStore(path)
            first = store._acquire()
            replacement = store._lock_path.with_name("replacement.lock")
            replacement.write_text("replacement")
            os.replace(replacement, store._lock_path)
            second = store._acquire()
            try:
                stale = first
                first = None
                with mock.patch.object(store, "_acquire", return_value=stale):
                    with self.assertRaises(SequenceConflictError) as raised:
                        store.append(event(0), 0)
                self.assertEqual(raised.exception.details["reason_code"], "lock_identity_changed")
                self.assertFalse(path.exists())
                with self.assertRaises(SequenceConflictError):
                    store.append(event(0), 0)
            finally:
                if first is not None:
                    store._release(first)
                store._release(second)
            store.append(event(0), 0)

    def test_oversize_record_and_ledger_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_bytes(b"x" * 65 + b"\n")
            with mock.patch("workflow_kernel.events.MAX_RECORD_BYTES", 64):
                with self.assertRaises(CorruptEventError):
                    EventStore(path).replay()
            with mock.patch("workflow_kernel.events.MAX_LEDGER_BYTES", 32):
                with self.assertRaises(CorruptEventError):
                    EventStore(path).replay()

    def test_excessive_payload_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text('{"kind":"run.initialized","node_id":null,"occurred_at":"2026-07-14T00:00:00Z","payload":{"a":{"b":{"c":1}}},"run_id":"run-1","schema_version":1,"sequence":0}\n')
            with mock.patch("workflow_kernel.schema.MAX_PAYLOAD_DEPTH", 2):
                with self.assertRaises(CorruptEventError):
                    EventStore(path).replay()

    def test_symlinked_ledger_is_rejected_without_mutating_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "other-run.jsonl"
            EventStore(target).append(event(0), 0)
            before = target.read_bytes()
            alias = root / "events.jsonl"
            alias.symlink_to(target)
            with self.assertRaises(CorruptEventError):
                EventStore(alias).validate()
            with self.assertRaises(CorruptEventError):
                EventStore(alias).append(event(1), 1)
            self.assertEqual(target.read_bytes(), before)

    def test_symlinked_event_lock_is_rejected_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            victim = Path(directory) / "victim.txt"
            victim.write_text("do-not-touch")
            path.with_name(path.name + ".lock").symlink_to(victim)
            before = victim.read_bytes()
            with self.assertRaises(SequenceConflictError):
                EventStore(path).append(event(0), 0)
            self.assertEqual(victim.read_bytes(), before)

    def test_event_writer_fails_closed_without_crash_safe_locking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with mock.patch("workflow_kernel.events.fcntl", None):
                with self.assertRaises(SequenceConflictError) as raised:
                    EventStore(path).append(event(0), 0)
            self.assertEqual(raised.exception.details["reason_code"], "locking_unsupported")
            self.assertFalse(path.exists())
            self.assertFalse(path.with_name(path.name + ".lock").exists())

    def test_append_does_not_reopen_a_swapped_regular_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "events.jsonl"
            target = root / "other-run.jsonl"
            EventStore(path).append(event(0), 0)
            EventStore(target).append(event(0), 0)
            before = target.read_bytes()
            store = EventStore(path)

            def swap_after_replay():
                existing = EventStore(path).replay()
                path.unlink()
                os.link(target, path)
                return existing

            with mock.patch.object(store, "replay", side_effect=swap_after_replay):
                store.append(event(1), 1)
            self.assertEqual(target.read_bytes(), before)

    def test_hard_linked_ledger_is_rejected_without_mutating_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "other-run.jsonl"
            EventStore(target).append(event(0), 0)
            before = target.read_bytes()
            alias = root / "events.jsonl"
            os.link(target, alias)
            with self.assertRaises(CorruptEventError):
                EventStore(alias).validate()
            with self.assertRaises(CorruptEventError):
                EventStore(alias).append(event(1), 1)
            self.assertEqual(target.read_bytes(), before)
