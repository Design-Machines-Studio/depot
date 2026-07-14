import tempfile
import unittest
import os
import subprocess
import sys
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
            with RunLease(path) as lease:
                store.write(original, expected_revision=-1, lease=lease)
            before = path.read_bytes()
            with RunLease(path) as lease:
                with self.assertRaises(RevisionConflictError):
                    store.write(original, expected_revision=99, lease=lease)
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
            with RunLease(path) as lease:
                evidence = StateStore(path).write(state, -1, lease=lease)
            self.assertEqual(StateStore(path).load(), state)
            self.assertIn(evidence["directory_fsync"], ("completed", "unsupported"))
            self.assertEqual(list(Path(directory).glob(".run-state.json.*.tmp")), [])

    def test_failure_before_replace_preserves_prior_valid_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            original = RunState.new("run-1", "2026-07-14T00:00:00Z")
            with RunLease(path) as lease:
                store.write(original, -1, lease=lease)
            before = path.read_bytes()
            with RunLease(path) as lease, mock.patch("workflow_kernel.state.os.replace", side_effect=OSError("injected")):
                with self.assertRaises(OSError):
                    store.write(original, original.revision, lease=lease)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).glob(".run-state.json.*.tmp")), [])

    def test_write_requires_owned_lease_bound_to_store(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            with self.assertRaises(LeaseConflictError):
                StateStore(first).write(state, -1)
            with RunLease(first) as lease:
                with self.assertRaises(LeaseConflictError):
                    StateStore(second).write(state, -1, lease=lease)

    def test_crashed_process_lock_residue_is_recoverable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            code = "import os,sys; from workflow_kernel.state import RunLease; RunLease(sys.argv[1]).acquire(); os._exit(0)"
            result = subprocess.run([sys.executable, "-c", code, str(path)], env=dict(os.environ), check=False)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(path.with_name(path.name + ".lease").exists())
            with RunLease(path):
                pass
