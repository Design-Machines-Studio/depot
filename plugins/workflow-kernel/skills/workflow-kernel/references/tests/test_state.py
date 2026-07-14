import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workflow_kernel.schema import LeaseConflictError, RevisionConflictError, RunState
from workflow_kernel.state import RunLease, StateStore


class StateStoreTests(unittest.TestCase):
    def test_revision_guard_preserves_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            original = RunState.new("run-1", "2026-07-14T00:00:00Z")
            with RunLease(path):
                store.write(original, expected_revision=-1)
            before = path.read_bytes()
            with RunLease(path):
                with self.assertRaises(RevisionConflictError):
                    store.write(original, expected_revision=99)
            self.assertEqual(path.read_bytes(), before)

    def test_second_live_lease_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            with RunLease(path):
                with self.assertRaises(LeaseConflictError):
                    with RunLease(path):
                        pass

    def test_write_returns_durability_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            with RunLease(path):
                evidence = StateStore(path).write(state, -1)
            self.assertEqual(StateStore(path).load(), state)
            self.assertIn(evidence["directory_fsync"], ("completed", "unsupported"))
            self.assertEqual(list(Path(directory).glob(".run-state.json.*.tmp")), [])

    def test_failure_before_replace_preserves_prior_valid_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            original = RunState.new("run-1", "2026-07-14T00:00:00Z")
            with RunLease(path):
                store.write(original, -1)
            before = path.read_bytes()
            with RunLease(path), mock.patch("workflow_kernel.state.os.replace", side_effect=OSError("injected")):
                with self.assertRaises(OSError):
                    store.write(original, original.revision)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).glob(".run-state.json.*.tmp")), [])
