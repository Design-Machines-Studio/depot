import tempfile
import unittest
import json
import os
import subprocess
import sys
from pathlib import Path
from dataclasses import replace
from unittest import mock

from workflow_kernel import CorruptStateError
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

    def test_unlinked_live_lease_cannot_authorize_alongside_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            first = RunLease(path).acquire()
            first.path.unlink()
            second = RunLease(path).acquire()
            try:
                self.assertFalse(first.authorizes(path))
                with self.assertRaises(LeaseConflictError) as raised:
                    StateStore(path).write(state, -1, lease=first)
                self.assertEqual(raised.exception.details["reason_code"], "lease_identity_changed")
                self.assertFalse(path.exists())
                StateStore(path).write(state, -1, lease=second)
            finally:
                first.release()
                self.assertTrue(second.authorizes(path))
                second.release()

    def test_replaced_live_lease_cannot_authorize_alongside_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            first = RunLease(path).acquire()
            replacement = first.path.with_name("replacement.lease")
            replacement.write_text("replacement")
            os.replace(replacement, first.path)
            second = RunLease(path).acquire()
            try:
                self.assertFalse(first.authorizes(path))
                with self.assertRaises(LeaseConflictError) as raised:
                    StateStore(path).write(state, -1, lease=first)
                self.assertEqual(raised.exception.details["reason_code"], "lease_identity_changed")
                self.assertFalse(path.exists())
                StateStore(path).write(state, -1, lease=second)
            finally:
                first.release()
                self.assertTrue(second.authorizes(path))
                second.release()

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

    def test_symlinked_lease_and_state_are_rejected_without_touching_victims(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_victim = root / "state-victim.json"
            state_victim.write_text("victim-state")
            state_path = root / "run-state.json"
            state_path.symlink_to(state_victim)
            before_state = state_victim.read_bytes()
            with self.assertRaises(CorruptStateError):
                StateStore(state_path).load()
            self.assertEqual(state_victim.read_bytes(), before_state)

            lease_victim = root / "lease-victim.txt"
            lease_victim.write_text("victim-lease")
            lease_path = state_path.with_name(state_path.name + ".lease")
            lease_path.symlink_to(lease_victim)
            before_lease = lease_victim.read_bytes()
            with self.assertRaises(LeaseConflictError):
                RunLease(state_path).acquire()
            self.assertEqual(lease_victim.read_bytes(), before_lease)

    def test_oversize_state_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            path.write_bytes(b"x" * 65)
            with mock.patch("workflow_kernel.state.MAX_STATE_BYTES", 64):
                with self.assertRaises(CorruptStateError) as raised:
                    StateStore(path).load()
            self.assertEqual(raised.exception.code, "corrupt_state")

    def test_lease_fails_closed_without_crash_safe_locking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            with mock.patch("workflow_kernel.state.fcntl", None):
                with self.assertRaises(LeaseConflictError) as raised:
                    RunLease(path).acquire()
            self.assertEqual(raised.exception.details["reason_code"], "locking_unsupported")
            self.assertFalse(path.with_name(path.name + ".lease").exists())

    def test_candidate_revision_cannot_downgrade_materialized_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            base = RunState.new("run-1", "2026-07-14T00:00:00Z")
            current = replace(base, revision=2)
            candidate = replace(base, revision=1)
            with RunLease(path) as lease:
                store.write(current, -1, lease=lease)
            before = path.read_bytes()
            with RunLease(path) as lease:
                with self.assertRaises(RevisionConflictError):
                    store.write(candidate, 2, lease=lease)
            self.assertEqual(path.read_bytes(), before)

    def test_hard_linked_state_and_lease_are_rejected_without_touching_victims(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_victim = root / "state-victim.json"
            state_victim.write_text(json.dumps(RunState.new("run-1", "2026-07-14T00:00:00Z").to_dict()))
            state_path = root / "run-state.json"
            os.link(state_victim, state_path)
            before_state = state_victim.read_bytes()
            with self.assertRaises(CorruptStateError):
                StateStore(state_path).load()
            self.assertEqual(state_victim.read_bytes(), before_state)

            lease_victim = root / "lease-victim.txt"
            lease_victim.write_text("do-not-touch")
            os.link(lease_victim, state_path.with_name(state_path.name + ".lease"))
            before_lease = lease_victim.read_bytes()
            with self.assertRaises(LeaseConflictError):
                RunLease(state_path).acquire()
            self.assertEqual(lease_victim.read_bytes(), before_lease)

    def test_unsafe_reference_in_state_is_normalized_to_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            data = RunState.new("run-1", "2026-07-14T00:00:00Z").to_dict()
            data["evidence"] = ["https://user:credential@example.invalid/proof"]
            path.write_text(json.dumps(data))
            with self.assertRaises(CorruptStateError) as raised:
                StateStore(path).load()
            self.assertEqual(raised.exception.code, "corrupt_state")
