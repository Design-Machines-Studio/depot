import tempfile
import unittest
import os
import traceback
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

from tests import detail_digest
from workflow_kernel.events import EventStore, encode_event
from workflow_kernel.schema import (
    CorruptEventError, KernelError, LeaseConflictError, SequenceConflictError,
    UnsafePayloadError, WorkflowEvent,
)
from workflow_kernel.state import RunLease

def event(sequence):
    return WorkflowEvent(1, sequence, "run-1", None, "evidence.recorded", "2026-07-14T00:00:00Z", {"evidence": [str(sequence)]})


def event_store(path):
    path = Path(path)
    root = path.parent if path.name == "events.jsonl" else path
    return EventStore(root)


def append_event(store, value, expected_sequence):
    with RunLease(store.state_path) as lease:
        store.append(value, expected_sequence, lease=lease)


class EventStoreTests(unittest.TestCase):
    def test_store_derives_event_and_state_paths_from_one_run_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EventStore(root)
            self.assertEqual(store.path, root / "events.jsonl")
            self.assertEqual(store.state_path, root / "run-state.json")
            self.assertFalse(hasattr(store, "__dict__"))
            for name, value in (("root", root / "other"),
                                ("path", root / "other-events.jsonl"),
                                ("state_path", root / "other-state.json"),
                                ("_root", root / "other"),
                                ("_path", root / "other-events.jsonl"),
                                ("_state_path", root / "other-state.json"),
                                ("_lock_path", root / "other-events.lock")):
                with self.subTest(name=name), self.assertRaises((AttributeError, TypeError)):
                    object.__setattr__(store, name, value)
                with self.subTest(delete=name), self.assertRaises((AttributeError, TypeError)):
                    object.__delattr__(store, name)
            with self.assertRaises(TypeError):
                class ForgedEventStore(EventStore):
                    pass
            with self.assertRaises(TypeError):
                EventStore.__init__(store, root / "other")
            with self.assertRaises(TypeError):
                EventStore(root / "events.jsonl", root / "other-state.json")

    def test_store_canonicalizes_ledger_and_lock_before_chdir(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            try:
                os.chdir(first)
                store = event_store("events.jsonl")
                canonical_first = Path(first).resolve()
                self.assertEqual(store.path, canonical_first / "events.jsonl")
                self.assertEqual(store._lock_path, canonical_first / "events.jsonl.lock")
                os.chdir(second)
                append_event(store, event(0), 0)
            finally:
                os.chdir(original)
            self.assertTrue((Path(first) / "events.jsonl").exists())
            self.assertFalse((Path(second) / "events.jsonl").exists())

    def test_append_replay_and_sequence_conflict_preserves_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = event_store(path)
            append_event(store, event(0), 0)
            before = path.read_bytes()
            with self.assertRaises(SequenceConflictError):
                append_event(store, event(2), 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(store.replay(), (event(0),))

    def test_append_rejects_mutated_scalar_subclasses_without_corrupting_replay(self):
        class NegativeInt(int):
            def __lt__(self, _other):
                return False

            def __ne__(self, _other):
                return False

        class FakeTimestamp(str):
            def replace(self, *_args, **_kwargs):
                return "2026-07-14T00:00:00+00:00"

        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            for field, invalid in (("sequence", NegativeInt(-1)),
                                   ("occurred_at", FakeTimestamp("not-a-timestamp"))):
                candidate = WorkflowEvent(
                    1, 0, "run-1", None, "run.initialized",
                    "2026-07-14T00:00:00Z", {},
                )
                object.__setattr__(candidate, field, invalid)
                with self.subTest(field=field), RunLease(store.state_path) as lease:
                    with self.assertRaises(KernelError):
                        store.append(candidate, 0, lease=lease)
                self.assertEqual(store.replay(), ())

    def test_append_uses_one_captured_event_for_validation_and_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            candidate = WorkflowEvent(
                1, 1, "run-1", None, "run.initialized",
                "2026-07-14T00:00:00Z", {},
            )

            class MutatingPayload(Mapping):
                def __iter__(self):
                    yield "note"

                def __len__(self):
                    return 1

                def __getitem__(self, _key):
                    object.__setattr__(candidate, "sequence", 0)
                    return "captured"

            object.__setattr__(candidate, "payload", MutatingPayload())
            with RunLease(store.state_path) as lease:
                with self.assertRaises(SequenceConflictError):
                    store.append(candidate, 0, lease=lease)
            self.assertEqual(store.replay(), ())

    def test_corrupt_earlier_record_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_bytes(b"{bad}\n{}\n")
            with self.assertRaises(CorruptEventError):
                event_store(path).replay()

    def test_recovery_reports_truncated_final_record_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = event_store(path)
            append_event(store, event(0), 0)
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
            append_event(event_store(path), event(0), 0)
            self.assertEqual(event_store(path).replay(), (event(0),))

    def test_live_event_writer_contention_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            store = event_store(Path(directory) / "events.jsonl")
            lock = store._acquire()
            try:
                with self.assertRaises(SequenceConflictError):
                    append_event(store, event(0), 0)
            finally:
                store._release(lock)

    def test_append_requires_the_live_lease_for_its_bound_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = event_store(root / "events.jsonl")
            with self.assertRaises(TypeError):
                store.append(event(0), 0)
            with RunLease(root / "other-state.json") as foreign:
                with self.assertRaises(LeaseConflictError):
                    store.append(event(0), 0, lease=foreign)
            released = RunLease(store.state_path).acquire()
            released.release()
            with self.assertRaises(LeaseConflictError):
                store.append(event(0), 0, lease=released)
            self.assertFalse(store.path.exists())

    def test_held_run_lease_cannot_be_bypassed_for_ledger_append(self):
        with tempfile.TemporaryDirectory() as directory:
            store = event_store(Path(directory) / "events.jsonl")
            with RunLease(store.state_path):
                with self.assertRaises(TypeError):
                    store.append(event(0), 0)
            self.assertFalse(store.path.exists())

    def test_unlinked_live_event_lock_cannot_mutate_alongside_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = event_store(path)
            first = store._acquire()
            store._lock_path.unlink()
            second = store._acquire()
            try:
                stale = first
                first = None
                with mock.patch.object(EventStore, "_acquire", return_value=stale):
                    with self.assertRaises(SequenceConflictError) as raised:
                        append_event(store, event(0), 0)
                self.assertEqual(raised.exception.details["reason_code"], detail_digest("lock_identity_changed"))
                self.assertFalse(path.exists())
                with self.assertRaises(SequenceConflictError):
                    append_event(store, event(0), 0)
            finally:
                if first is not None:
                    store._release(first)
                store._release(second)
            append_event(store, event(0), 0)

    def test_replaced_live_event_lock_cannot_mutate_alongside_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = event_store(path)
            first = store._acquire()
            replacement = store._lock_path.with_name("replacement.lock")
            replacement.write_text("replacement")
            os.replace(replacement, store._lock_path)
            second = store._acquire()
            try:
                stale = first
                first = None
                with mock.patch.object(EventStore, "_acquire", return_value=stale):
                    with self.assertRaises(SequenceConflictError) as raised:
                        append_event(store, event(0), 0)
                self.assertEqual(raised.exception.details["reason_code"], detail_digest("lock_identity_changed"))
                self.assertFalse(path.exists())
                with self.assertRaises(SequenceConflictError):
                    append_event(store, event(0), 0)
            finally:
                if first is not None:
                    store._release(first)
                store._release(second)
            append_event(store, event(0), 0)

    def test_oversize_record_and_ledger_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_bytes(b"x" * 65 + b"\n")
            with mock.patch("workflow_kernel.events.MAX_RECORD_BYTES", 64):
                with self.assertRaises(CorruptEventError):
                    event_store(path).replay()
            with mock.patch("workflow_kernel.events.MAX_LEDGER_BYTES", 32):
                with self.assertRaises(CorruptEventError):
                    event_store(path).replay()

    def test_append_rejects_oversize_record_without_changing_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = event_store(path)
            append_event(store, event(0), 0)
            before = path.read_bytes()
            candidate = WorkflowEvent(1, 1, "run-1", None, "evidence.recorded",
                                      "2026-07-14T00:00:00Z", {"note": "x" * 256})
            with mock.patch("workflow_kernel.events.MAX_RECORD_BYTES", len(encode_event(candidate)) - 1):
                with self.assertRaises(UnsafePayloadError):
                    append_event(store, candidate, 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(store.replay(), (event(0),))

    def test_append_rejects_projected_ledger_overflow_without_changing_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = event_store(path)
            append_event(store, event(0), 0)
            before = path.read_bytes()
            candidate = event(1)
            projected_limit = len(before) + len(encode_event(candidate)) - 1
            with mock.patch("workflow_kernel.events.MAX_LEDGER_BYTES", projected_limit):
                with self.assertRaises(UnsafePayloadError):
                    append_event(store, candidate, 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(store.replay(), (event(0),))

    def test_excessive_payload_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text('{"kind":"run.initialized","node_id":null,"occurred_at":"2026-07-14T00:00:00Z","payload":{"a":{"b":{"c":1}}},"run_id":"run-1","schema_version":1,"sequence":0}\n')
            with mock.patch("workflow_kernel.schema.MAX_PAYLOAD_DEPTH", 2):
                with self.assertRaises(CorruptEventError):
                    event_store(path).replay()

    def test_symlinked_ledger_is_rejected_without_mutating_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "other-run"
            target_root.mkdir()
            target = target_root / "events.jsonl"
            append_event(event_store(target_root), event(0), 0)
            before = target.read_bytes()
            alias = root / "events.jsonl"
            alias.symlink_to(target)
            with self.assertRaises(CorruptEventError):
                event_store(alias).validate()
            with self.assertRaises(CorruptEventError):
                append_event(event_store(alias), event(1), 1)
            self.assertEqual(target.read_bytes(), before)

    def test_symlinked_event_lock_is_rejected_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            victim = Path(directory) / "victim.txt"
            victim.write_text("do-not-touch")
            path.with_name(path.name + ".lock").symlink_to(victim)
            before = victim.read_bytes()
            with self.assertRaises(SequenceConflictError):
                append_event(event_store(path), event(0), 0)
            self.assertEqual(victim.read_bytes(), before)

    def test_event_path_rejections_do_not_retain_raw_traceback_causes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = "never-persist-event-path"
            store = EventStore(root / sentinel)
            store.path.parent.mkdir()
            store.path.symlink_to(root / "missing-ledger")
            store._lock_path.symlink_to(root / "missing-lock")
            for reject in (store.validate, lambda: append_event(store, event(0), 0)):
                with self.subTest(reject=reject), self.assertRaises((CorruptEventError, SequenceConflictError)) as raised:
                    reject()
                rendered = "".join(traceback.format_exception(
                    type(raised.exception), raised.exception, raised.exception.__traceback__,
                ))
                self.assertIsNone(raised.exception.__cause__)
                self.assertNotIn(sentinel, rendered)

    def test_event_parent_setup_errors_are_stable_and_secret_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            sentinel = "never-render-event-parent"
            with RunLease(store.state_path) as lease:
                with mock.patch("workflow_kernel.events.Path.mkdir",
                                side_effect=NotADirectoryError(sentinel)):
                    with self.assertRaises(SequenceConflictError) as raised:
                        store.append(event(0), 0, lease=lease)
            rendered = "".join(traceback.format_exception(
                type(raised.exception), raised.exception, raised.exception.__traceback__,
            ))
            self.assertEqual(raised.exception.code, "sequence_conflict")
            self.assertIsNone(raised.exception.__cause__)
            self.assertNotIn(sentinel, rendered)

    def test_event_writer_fails_closed_without_crash_safe_locking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = event_store(path)
            lease = RunLease(store.state_path).acquire()
            try:
                with mock.patch("workflow_kernel._files.fcntl", None, create=True):
                    with self.assertRaises(SequenceConflictError) as raised:
                        store.append(event(0), 0, lease=lease)
            finally:
                lease.release()
            self.assertEqual(raised.exception.details["reason_code"], detail_digest("locking_unsupported"))
            self.assertFalse(path.exists())
            self.assertFalse(path.with_name(path.name + ".lock").exists())

    def test_hard_linked_ledger_is_rejected_without_mutating_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "other-run"
            target_root.mkdir()
            target = target_root / "events.jsonl"
            append_event(event_store(target_root), event(0), 0)
            before = target.read_bytes()
            alias = root / "events.jsonl"
            os.link(target, alias)
            with self.assertRaises(CorruptEventError):
                event_store(alias).validate()
            with self.assertRaises(CorruptEventError):
                append_event(event_store(alias), event(1), 1)
            self.assertEqual(target.read_bytes(), before)
