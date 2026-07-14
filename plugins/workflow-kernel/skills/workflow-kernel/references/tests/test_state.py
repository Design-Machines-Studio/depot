import hashlib
import tempfile
import unittest
import json
import os
import subprocess
import sys
from pathlib import Path
from dataclasses import FrozenInstanceError, replace
from unittest import mock

from workflow_kernel import CorruptStateError
from workflow_kernel.events import EventStore
from workflow_kernel.schema import LeaseConflictError, RevisionConflictError, RunState, UnsafePayloadError, WorkflowEvent
from workflow_kernel.state import RunLease, StateStore, encode_state


def detail_digest(value):
    return "value-sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


class StateStoreTests(unittest.TestCase):
    def test_prepared_state_is_frozen_and_publishes_exact_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            self.assertTrue(hasattr(store, "prepare"))
            prepared = store.prepare(state)
            self.assertEqual(prepared.state, state)
            self.assertEqual(prepared.encoded, encode_state(state))
            with self.assertRaises(FrozenInstanceError):
                prepared.encoded = b"corrupt\n"
            with RunLease(path) as lease:
                for invalid in (b"corrupt\n", replace(prepared, encoded=b"corrupt\n")):
                    with self.subTest(invalid=type(invalid).__name__), self.assertRaises(UnsafePayloadError):
                        store.publish(invalid, -1, lease=lease)
                store.publish(prepared, -1, lease=lease)
            self.assertEqual(store.load(), state)
            self.assertFalse(hasattr(store, "_write_prepared"))

    def test_prepared_state_cannot_publish_through_another_store(self):
        with tempfile.TemporaryDirectory() as directory:
            first = StateStore(Path(directory) / "first.json")
            second = StateStore(Path(directory) / "second.json")
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            self.assertTrue(hasattr(first, "prepare"))
            prepared = first.prepare(state)
            with RunLease(second.path) as lease:
                with self.assertRaises(UnsafePayloadError) as raised:
                    second.publish(prepared, -1, lease=lease)
            self.assertEqual(raised.exception.details["reason_code"], detail_digest("prepared_state_owner_mismatch"))
            self.assertFalse(second.path.exists())

    def test_relative_stores_keep_all_artifacts_bound_across_chdir(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            try:
                os.chdir(first)
                events = EventStore("events.jsonl")
                states = StateStore("run-state.json")
                canonical_first = Path(first).resolve()
                self.assertEqual(events.path, canonical_first / "events.jsonl")
                self.assertEqual(states.path, canonical_first / "run-state.json")

                os.chdir(second)
                event = WorkflowEvent(
                    1, 0, "run-1", None, "run.initialized",
                    "2026-07-14T00:00:00Z", {"mode": "shadow"},
                )
                events.append(event, 0)
                state = RunState.new("run-1", "2026-07-14T00:00:00Z")
                with RunLease(states.path) as lease:
                    states.write(state, -1, lease=lease)
            finally:
                os.chdir(original)

            for name in ("events.jsonl", "events.jsonl.lock", "run-state.json", "run-state.json.lease"):
                self.assertTrue((Path(first) / name).exists(), name)
                self.assertFalse((Path(second) / name).exists(), name)

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
                self.assertEqual(raised.exception.details["reason_code"], detail_digest("lease_identity_changed"))
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
                self.assertEqual(raised.exception.details["reason_code"], detail_digest("lease_identity_changed"))
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

    def test_deeply_nested_state_is_normalized_to_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            path.write_text("[" * 1_200 + "0" + "]" * 1_200)
            with self.assertRaises(Exception) as raised:
                StateStore(path).load()
            self.assertIsInstance(raised.exception, CorruptStateError)
            self.assertEqual(raised.exception.code, "corrupt_state")

    def test_oversize_state_write_preserves_prior_materialization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            with RunLease(path) as lease:
                store.write(state, -1, lease=lease)
            before = path.read_bytes()
            candidate = replace(state, evidence=("x" * 256,))
            self.assertGreater(len(encode_state(candidate)), len(before) + 16)
            with mock.patch("workflow_kernel.state.MAX_STATE_BYTES", len(before) + 16):
                with RunLease(path) as lease, self.assertRaises(UnsafePayloadError):
                    store.write(candidate, state.revision, lease=lease)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).glob(".run-state.json.*.tmp")), [])

    def test_lease_fails_closed_without_crash_safe_locking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            with mock.patch("workflow_kernel._files.fcntl", None, create=True):
                with self.assertRaises(LeaseConflictError) as raised:
                    RunLease(path).acquire()
            self.assertEqual(raised.exception.details["reason_code"], detail_digest("locking_unsupported"))
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
