import tempfile
import unittest
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
