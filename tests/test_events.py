import tempfile
import unittest
import os
import traceback
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

from tests import detail_digest, swap_parent_after_relative_stat
from workflow_kernel.events import EventStore, encode_event
from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
from workflow_kernel.dm_review_adapter import translate_review_receipts
from workflow_kernel.schema import (
    CorruptEventError, InvalidSchemaError, KernelError, LeaseConflictError,
    SequenceConflictError, UnsafePayloadError, WorkflowEvent,
)
from workflow_kernel.state import RunLease
from workflow_kernel._files import LockHandle, PinnedDirectory

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
    def test_telemetry_payload_is_redacted_bounded_immutable_and_replay_safe(self):
        raw = {
            "stage": "attempt_usage", "usage_scope": "attempt", "attempt": 1,
            "input_usage_count": 10, "cost_usd": 0.01,
            "measurement_source": "https://telemetry.example/receipt",
            "usage_estimated": False, "missing_case_ids": ["case-a"],
            "api_token": "never-persist-this-secret",
            "evidence": ["receipts/attempt.json"],
        }
        candidate = WorkflowEvent(
            1, 0, "run-telemetry", "chunk-a", "evidence.recorded",
            "2026-07-14T00:00:00Z", raw,
        )
        raw["input_usage_count"] = 999
        raw["missing_case_ids"].append("case-b")
        self.assertEqual(candidate.payload["input_usage_count"], 10)
        self.assertEqual(candidate.payload["missing_case_ids"], ("case-a",))
        with self.assertRaises(TypeError):
            candidate.payload["attempt"] = 2
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            append_event(store, candidate, 0)
            durable = store.path.read_text()
            self.assertNotIn("never-persist-this-secret", durable)
            self.assertNotIn("telemetry.example", durable)
            replayed = store.replay()
            self.assertEqual(replayed[0].payload["input_usage_count"], 10)
            self.assertEqual(store.validate()[0], replayed)

    def test_translated_telemetry_enforces_string_case_and_document_boundaries(self):
        usage = {
            "run_id": "run-telemetry", "sequence": 0, "stage": "attempt_usage",
            "status": "observed", "node_id": "chunk-a", "chunk_id": "chunk-a",
            "attempt": 1, "requested_provider": "openrouter",
            "attempted_provider": "openai", "implemented_by": "codex",
            "provider": "openai", "model": "gpt-5.6-sol", "host": "codex",
            "duration_seconds": 1.0, "usage_scope": "attempt", "usage_count": 10,
            "measurement_source": "m" * 4096, "usage_estimated": False,
            "occurred_at": "2026-07-14T00:00:00Z",
            "authoritative_receipt": "receipts/telemetry.json",
        }
        translated = translate_pipeline_receipts([usage])[0]
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            append_event(store, translated, 0)
            self.assertEqual(store.replay()[0].payload["usage_count"], 10)
        overlong = dict(usage)
        sentinel = "never-render-overlong-telemetry"
        overlong["measurement_source"] = sentinel + "x" * 4097
        with self.assertRaises(ValueError) as raised:
            translate_pipeline_receipts([overlong])
        self.assertNotIn(sentinel, str(raised.exception))

        def case_id(index):
            prefix = f"case-{index:03d}-"
            return prefix + "x" * (256 - len(prefix))

        browser = {
            "run_id": "run-browser", "sequence": 0, "stage": "browser_recovery",
            "status": "blocked", "reason_code": "human_help_required",
            "node_id": "review-browser",
            "human_intervention_id": "human-browser-boundary",
            "human_intervention_reason": "browser_evidence_unavailable",
            "missing_case_ids": [case_id(index) for index in range(64)],
            "occurred_at": "2026-07-14T00:00:00Z",
            "authoritative_receipt": "receipts/browser-boundary.json",
        }
        event = translate_review_receipts([browser])[0]
        self.assertEqual(len(event.payload["missing_case_ids"]), 64)
        over_document = dict(browser)
        over_document["missing_case_ids"] = [case_id(index) for index in range(65)]
        with self.assertRaises(ValueError):
            translate_review_receipts([over_document])
        over_count = dict(browser)
        over_count["missing_case_ids"] = [f"case-{index}" for index in range(257)]
        with self.assertRaises(ValueError):
            translate_review_receipts([over_count])

    def test_require_absent_accepts_missing_and_classifies_existing_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            EventStore(directory).require_absent()

        for entry_type, error_type in (
                ("empty", InvalidSchemaError),
                ("dangling", CorruptEventError),
                ("hardlink", CorruptEventError),
                ("directory", CorruptEventError)):
            with self.subTest(entry_type=entry_type), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "events.jsonl"
                if entry_type == "empty":
                    path.touch()
                elif entry_type == "dangling":
                    path.symlink_to("missing-ledger")
                elif entry_type == "hardlink":
                    target = root / "target"
                    target.touch()
                    os.link(target, path)
                else:
                    path.mkdir()
                with self.assertRaises(error_type):
                    EventStore(root).require_absent()

    def test_require_absent_revalidates_parent_on_present_and_missing_branches(self):
        for present in (True, False):
            with self.subTest(present=present), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory) / "run"
                parent.mkdir()
                if present:
                    (parent / "events.jsonl").touch()
                store = EventStore(parent)
                with mock.patch(
                        "workflow_kernel._files.os.stat",
                        side_effect=swap_parent_after_relative_stat(parent, "events.jsonl")), \
                        self.assertRaises(CorruptEventError):
                    store.require_absent()


    def test_empty_ledger_revalidates_file_identity_before_returning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "events.jsonl"
            path.write_bytes(b"")
            replacement = root / "replacement.jsonl"
            replacement.write_bytes(b"replacement\n")
            store = EventStore(root)
            original_fstat = os.fstat
            calls = 0

            def replace_during_empty_validation(descriptor):
                nonlocal calls
                calls += 1
                result = original_fstat(descriptor)
                if calls == 3:
                    os.replace(replacement, path)
                return result

            with mock.patch("workflow_kernel.events.os.fstat",
                            side_effect=replace_during_empty_validation), \
                    self.assertRaises(CorruptEventError):
                store.validate()
            self.assertEqual(path.read_bytes(), b"replacement\n")

    def test_empty_ledger_revalidates_parent_identity_before_returning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "run"
            parent.mkdir()
            (parent / "events.jsonl").write_bytes(b"")
            moved = root / "moved"
            store = EventStore(parent)
            original_fstat = os.fstat
            calls = 0

            def replace_parent_during_empty_validation(descriptor):
                nonlocal calls
                calls += 1
                result = original_fstat(descriptor)
                if calls == 3:
                    parent.rename(moved)
                    parent.mkdir()
                    (parent / "events.jsonl").write_bytes(b"")
                return result

            with mock.patch("workflow_kernel.events.os.fstat",
                            side_effect=replace_parent_during_empty_validation), \
                    self.assertRaises(CorruptEventError):
                store.validate()

    def test_missing_ledger_close_failure_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
                PinnedDirectory, "close", side_effect=OSError("cleanup-sentinel")):
            try:
                EventStore(directory).validate()
            except Exception as raised:
                self.assertIsInstance(raised, CorruptEventError)
                self.assertNotIn("cleanup-sentinel", str(raised))
            else:
                self.fail("close failure was not reported")

    def test_missing_file_in_live_bound_parent_is_an_empty_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(event_store(Path(directory) / "events.jsonl").validate(), ((), ()))

    def test_missing_ledger_revalidates_parent_before_returning_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "run"
            parent.mkdir()
            moved = root / "moved"
            store = EventStore(parent)

            def swap_parent_then_report_missing(*_args, **_kwargs):
                parent.rename(moved)
                parent.mkdir()
                raise FileNotFoundError("missing-ledger-sentinel")

            with mock.patch.object(PinnedDirectory, "open_regular",
                                   side_effect=swap_parent_then_report_missing), \
                    self.assertRaises(CorruptEventError) as raised:
                store.validate()
            self.assertIsNone(raised.exception.__cause__)

    def test_append_parent_swap_cannot_redirect_ledger_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "run"
            parent.mkdir()
            moved = root / "moved"
            store = event_store(parent / "events.jsonl")
            original_write = os.write
            injected = False

            def swap_parent_before_write(descriptor, data):
                nonlocal injected
                if not injected:
                    injected = True
                    parent.rename(moved)
                    parent.mkdir()
                    (parent / "events.jsonl").write_text("replacement-parent-sentinel")
                return original_write(descriptor, data)

            with RunLease(store.state_path) as lease, mock.patch(
                    "workflow_kernel.events.os.write", side_effect=swap_parent_before_write), \
                    self.assertRaises(CorruptEventError):
                store.append(event(0), 0, lease=lease)
            self.assertEqual(
                (parent / "events.jsonl").read_text(), "replacement-parent-sentinel",
            )

    def test_missing_bound_parent_is_normalized_as_corrupt_event(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "run"
            parent.mkdir()
            store = event_store(parent / "events.jsonl")
            parent.rmdir()
            with self.assertRaises(CorruptEventError) as raised:
                store.validate()
            self.assertIsNone(raised.exception.__cause__)

    def assert_stable_event_error(self, operation, error_type=CorruptEventError):
        sentinel = "never-render-descriptor-event-error"
        with self.assertRaises(error_type) as raised:
            operation(sentinel)
        rendered = "".join(traceback.format_exception(
            type(raised.exception), raised.exception, raised.exception.__traceback__,
        ))
        self.assertIsNone(raised.exception.__cause__)
        self.assertNotIn(sentinel, rendered)

    def test_store_derives_event_and_state_paths_from_one_run_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EventStore(root)
            self.assertEqual(store.path, root.resolve() / "events.jsonl")
            self.assertEqual(store.state_path, root.resolve() / "run-state.json")
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

    def test_event_store_binding_errors_are_normalized(self):
        sentinel = "never-render-event-binding"
        with mock.patch("workflow_kernel.events.bind_durable_path", side_effect=OSError(sentinel)), \
                self.assertRaises(CorruptEventError) as raised:
            EventStore("unused")
        self.assertIsNone(raised.exception.__cause__)
        self.assertNotIn(sentinel, "".join(traceback.format_exception(
            type(raised.exception), raised.exception, raised.exception.__traceback__,
        )))

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

    def test_validate_rejects_ledger_replaced_during_read(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            append_event(store, event(0), 0)
            replacement = Path(directory) / "replacement.jsonl"
            replacement.write_bytes(encode_event(event(0)))
            original = WorkflowEvent.from_dict

            def replace_then_parse(value):
                os.replace(replacement, store.path)
                return original(value)

            with mock.patch.object(WorkflowEvent, "from_dict", side_effect=replace_then_parse), \
                    self.assertRaises(CorruptEventError):
                store.validate()

    def test_append_rejects_ledger_replaced_during_write(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            replacement = Path(directory) / "replacement.jsonl"
            replacement.write_bytes(b"replacement\n")
            original_write = os.write
            replaced = False

            def replace_then_write(descriptor, data):
                nonlocal replaced
                if not replaced and descriptor not in ():
                    replaced = True
                    os.replace(replacement, store.path)
                return original_write(descriptor, data)

            lease = RunLease(store.state_path).acquire()
            try:
                with mock.patch("workflow_kernel.events.os.write", side_effect=replace_then_write), \
                        self.assertRaises(CorruptEventError):
                    store.append(event(0), 0, lease=lease)
            finally:
                lease.release()
            self.assertEqual(store.path.read_bytes(), b"replacement\n")

    def test_descriptor_read_stat_and_write_errors_are_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            append_event(store, event(0), 0)

            real_fstat = os.fstat

            def fail_validation_stat(sentinel):
                calls = 0

                def delayed(descriptor):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        raise OSError(sentinel)
                    return real_fstat(descriptor)

                with mock.patch("workflow_kernel.events.os.fstat", side_effect=delayed):
                    store.validate()

            self.assert_stable_event_error(fail_validation_stat)

            sentinel = "never-render-descriptor-event-error"
            lease = RunLease(store.state_path).acquire()
            try:
                with mock.patch("workflow_kernel.events.os.write", side_effect=OSError(sentinel)), \
                        self.assertRaises(CorruptEventError) as raised:
                    store.append(event(1), 1, lease=lease)
            finally:
                lease.release()
            self.assertIsNone(raised.exception.__cause__)
            self.assertNotIn(sentinel, "".join(traceback.format_exception(
                type(raised.exception), raised.exception, raised.exception.__traceback__,
            )))

    def test_descriptor_dup_readline_fsync_close_and_release_errors_are_normalized(self):
        sentinel = "never-render-event-descriptor-matrix"

        class FailingFile:
            def __init__(self, handle, operation):
                self.handle = handle
                self.operation = operation

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

            def close(self):
                self.handle.close()
                if self.operation == "close":
                    raise OSError(sentinel)

            def fileno(self):
                return self.handle.fileno()

            def readline(self, size=-1):
                if self.operation == "readline":
                    raise OSError(sentinel)
                return self.handle.readline(size)

        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            append_event(store, event(0), 0)
            real_fdopen = os.fdopen
            for operation in ("readline", "close"):
                def failing_fdopen(descriptor, mode, operation=operation):
                    return FailingFile(real_fdopen(descriptor, mode), operation)

                with self.subTest(operation=operation), mock.patch(
                    "workflow_kernel.events.os.fdopen", side_effect=failing_fdopen,
                ), self.assertRaises(CorruptEventError) as raised:
                    store.validate()
                self.assertNotIn(sentinel, "".join(traceback.format_exception(
                    type(raised.exception), raised.exception, raised.exception.__traceback__,
                )))

            for operation, patch_target in (("dup", "os.dup"), ("fsync", "os.fsync")):
                lease = RunLease(store.state_path).acquire()
                try:
                    with self.subTest(operation=operation), mock.patch(
                        "workflow_kernel.events." + patch_target,
                        side_effect=OSError(sentinel),
                    ), self.assertRaises(CorruptEventError) as raised:
                        store.append(event(1), 1, lease=lease)
                finally:
                    lease.release()
                self.assertNotIn(sentinel, "".join(traceback.format_exception(
                    type(raised.exception), raised.exception, raised.exception.__traceback__,
                )))

            lease = RunLease(store.state_path).acquire()
            try:
                actual = len(store.replay())
                with mock.patch.object(LockHandle, "release", side_effect=OSError(sentinel)), \
                        self.assertRaises(SequenceConflictError) as raised:
                    store.append(event(actual), actual, lease=lease)
            finally:
                lease.release()
            self.assertNotIn(sentinel, "".join(traceback.format_exception(
                type(raised.exception), raised.exception, raised.exception.__traceback__,
            )))

    def test_primary_event_error_survives_lock_release_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            lease = RunLease(store.state_path).acquire()
            try:
                with mock.patch.object(LockHandle, "release", side_effect=OSError("cleanup")), \
                        self.assertRaises(SequenceConflictError) as raised:
                    store.append(event(2), 0, lease=lease)
            finally:
                lease.release()
            self.assertEqual(raised.exception.message, "event sequence does not match ledger")

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
                lock.release()

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
                    first.release()
                second.release()
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
                    first.release()
                second.release()
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
