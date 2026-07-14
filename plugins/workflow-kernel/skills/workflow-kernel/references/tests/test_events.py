import tempfile
import unittest
from pathlib import Path

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
