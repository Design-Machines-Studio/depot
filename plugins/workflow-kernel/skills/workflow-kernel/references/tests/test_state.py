import tempfile
import unittest
import json
import os
import gc
import subprocess
import sys
import traceback
import weakref
from pathlib import Path
from dataclasses import replace
from unittest import mock

from tests import detail_digest
from workflow_kernel import CorruptStateError
from workflow_kernel.events import EventStore
from workflow_kernel.schema import LeaseConflictError, RevisionConflictError, RunState, UnsafePayloadError, WorkflowEvent
from workflow_kernel.state import PreparedState, RunLease, StateStore, encode_state
from workflow_kernel._files import LockHandle, PinnedDirectory

class StateStoreTests(unittest.TestCase):
    def test_missing_file_in_live_bound_parent_remains_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                StateStore(Path(directory) / "run-state.json").load()

    def test_publish_parent_swap_cannot_redirect_atomic_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "run"
            parent.mkdir()
            path = parent / "run-state.json"
            moved = root / "moved"
            store = StateStore(path)
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            original_fsync = os.fsync
            injected = False

            def swap_parent_after_temp_write(descriptor):
                nonlocal injected
                result = original_fsync(descriptor)
                if not injected:
                    injected = True
                    parent.rename(moved)
                    parent.mkdir()
                    temporary = next(moved.glob(".run-state.json.*.tmp"))
                    (parent / temporary.name).write_text("replacement-parent-sentinel")
                return result

            with RunLease(path) as lease, mock.patch(
                    "workflow_kernel.state.os.fsync", side_effect=swap_parent_after_temp_write), \
                    self.assertRaises((CorruptStateError, LeaseConflictError)):
                store.write(state, -1, lease=lease)
            self.assertFalse(path.exists())
            self.assertEqual(
                next(parent.glob(".run-state.json.*.tmp")).read_text(),
                "replacement-parent-sentinel",
            )
            self.assertEqual(list(moved.glob(".run-state.json.*.tmp")), [])

    def test_missing_bound_parent_is_normalized_as_corrupt_state(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "run"
            parent.mkdir()
            store = StateStore(parent / "run-state.json")
            parent.rmdir()
            with self.assertRaises(CorruptStateError) as raised:
                store.load()
            self.assertIsNone(raised.exception.__cause__)

    def test_publish_preserves_revision_interloper_created_after_temp_fsync(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            base = RunState.new("run-1", "2026-07-14T00:00:00Z")
            with RunLease(path) as lease:
                store.write(base, -1, lease=lease)
            candidate = replace(base, revision=1)
            interloper = replace(base, revision=2)
            replacement = Path(directory) / "interloper.json"
            replacement.write_bytes(encode_state(interloper))
            original_fsync = os.fsync
            original_replace = os.replace
            injected = False

            def inject_after_temp_write(descriptor):
                nonlocal injected
                result = original_fsync(descriptor)
                if not injected:
                    injected = True
                    original_replace(replacement, path)
                return result

            with RunLease(path) as lease, mock.patch(
                    "workflow_kernel.state.os.fsync", side_effect=inject_after_temp_write), \
                    self.assertRaises(RevisionConflictError):
                store.write(candidate, 0, lease=lease)
            self.assertEqual(store.load().revision, 2)

    @unittest.skipUnless(hasattr(os, "fork"), "requires POSIX fork")
    def test_fork_child_explicit_release_only_closes_inherited_lease_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            lease = RunLease(path).acquire()
            pid = os.fork()
            if pid == 0:
                try:
                    lease.release()
                finally:
                    os._exit(0)
            os.waitpid(pid, 0)
            try:
                with self.assertRaises(LeaseConflictError):
                    RunLease(path).acquire()
            finally:
                lease.release()

    @unittest.skipUnless(hasattr(os, "fork"), "requires POSIX fork")
    def test_fork_child_gc_only_closes_inherited_lease_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            lease = RunLease(path).acquire()
            pid = os.fork()
            if pid == 0:
                try:
                    del lease
                    gc.collect()
                finally:
                    os._exit(0)
            os.waitpid(pid, 0)
            try:
                with self.assertRaises(LeaseConflictError):
                    RunLease(path).acquire()
            finally:
                lease.release()

    def test_lease_setup_cleanup_failure_does_not_replace_stable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            handle = mock.Mock(descriptor=7)
            handle.release.side_effect = OSError("cleanup-sentinel")
            with mock.patch.object(LockHandle, "acquire_bound", return_value=handle), \
                    mock.patch("workflow_kernel.state.os.ftruncate", side_effect=OSError("setup-sentinel")), \
                    self.assertRaises(LeaseConflictError) as raised:
                RunLease(path).acquire()
            rendered = "".join(traceback.format_exception(
                type(raised.exception), raised.exception, raised.exception.__traceback__,
            ))
            self.assertNotIn("cleanup-sentinel", rendered)
            self.assertNotIn("setup-sentinel", rendered)

    def test_context_exit_preserves_body_error_when_release_also_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            body_error = RuntimeError("body-sentinel")
            with mock.patch.object(LockHandle, "release", side_effect=OSError("cleanup-sentinel")):
                with self.assertRaises(RuntimeError) as raised:
                    with RunLease(path):
                        raise body_error
            self.assertIs(raised.exception, body_error)

    def test_state_and_lease_binding_errors_are_normalized(self):
        sentinel = "never-render-state-binding"
        for constructor, error_type in (
            (lambda: StateStore("unused"), CorruptStateError),
            (lambda: RunLease("unused"), LeaseConflictError),
        ):
            with self.subTest(constructor=constructor), mock.patch(
                "workflow_kernel.state.bind_durable_path", side_effect=OSError(sentinel),
            ), self.assertRaises(error_type) as raised:
                constructor()
            self.assertIsNone(raised.exception.__cause__)
            self.assertNotIn(sentinel, "".join(traceback.format_exception(
                type(raised.exception), raised.exception, raised.exception.__traceback__,
            )))

    def test_load_rejects_state_replaced_during_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            path.write_bytes(encode_state(state))
            replacement = Path(directory) / "replacement.json"
            replacement.write_bytes(encode_state(state))
            original = RunState.from_dict

            def replace_then_parse(value):
                os.replace(replacement, path)
                return original(value)

            with mock.patch.object(RunState, "from_dict", side_effect=replace_then_parse), \
                    self.assertRaises(CorruptStateError):
                StateStore(path).load()

    def test_publish_rejects_state_replaced_before_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            replacement = Path(directory) / "replacement.json"
            replacement.write_text("replacement")
            original_fsync = PinnedDirectory.fsync

            def replace_then_fsync(directory):
                result = original_fsync(directory)
                os.replace(replacement, path)
                return result

            with RunLease(path) as lease, mock.patch.object(
                    PinnedDirectory, "fsync", autospec=True,
                    side_effect=replace_then_fsync), \
                    self.assertRaises(CorruptStateError):
                store.write(state, -1, lease=lease)
            self.assertEqual(path.read_text(), "replacement")

    def test_descriptor_read_and_stat_errors_are_stable_and_secret_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            path.write_bytes(encode_state(RunState.new(
                "run-1", "2026-07-14T00:00:00Z",
            )))
            sentinel = "never-render-descriptor-state-error"
            real_fstat = os.fstat
            for operation in ("read", "fstat"):
                if operation == "fstat":
                    calls = 0

                    def delayed(descriptor):
                        nonlocal calls
                        calls += 1
                        if calls == 2:
                            raise OSError(sentinel)
                        return real_fstat(descriptor)

                    patched = mock.patch("workflow_kernel.state.os.fstat", side_effect=delayed)
                else:
                    patched = mock.patch("workflow_kernel.state.os.read", side_effect=OSError(sentinel))
                with self.subTest(operation=operation), patched, \
                        self.assertRaises(CorruptStateError) as raised:
                    StateStore(path).load()
                rendered = "".join(traceback.format_exception(
                    type(raised.exception), raised.exception, raised.exception.__traceback__,
                ))
                self.assertIsNone(raised.exception.__cause__)
                self.assertNotIn(sentinel, rendered)

    def test_state_write_flush_fsync_and_close_errors_are_normalized(self):
        sentinel = "never-render-state-descriptor-matrix"

        class FailingWriter:
            def __init__(self, handle, operation):
                self.handle = handle
                self.operation = operation

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.handle.close()

            def write(self, value):
                if self.operation == "write":
                    raise OSError(sentinel)
                return self.handle.write(value)

            def flush(self):
                if self.operation == "flush":
                    raise OSError(sentinel)
                return self.handle.flush()

            def fileno(self):
                return self.handle.fileno()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            real_fdopen = os.fdopen
            for operation in ("write", "flush"):
                store = StateStore(path)
                lease = RunLease(path).acquire()
                try:
                    def failing_fdopen(descriptor, mode, closefd=True, operation=operation):
                        return FailingWriter(
                            real_fdopen(descriptor, mode, closefd=closefd), operation,
                        )

                    with mock.patch("workflow_kernel.state.os.fdopen", side_effect=failing_fdopen), \
                            self.assertRaises(CorruptStateError) as raised:
                        store.write(state, -1, lease=lease)
                finally:
                    lease.release()
                self.assertNotIn(sentinel, "".join(traceback.format_exception(
                    type(raised.exception), raised.exception, raised.exception.__traceback__,
                )))

            for operation, target in (("fsync", "os.fsync"), ("close", "os.close")):
                store = StateStore(path)
                lease = RunLease(path).acquire()
                try:
                    with self.subTest(operation=operation), mock.patch(
                        "workflow_kernel.state." + target, side_effect=OSError(sentinel),
                    ), self.assertRaises(CorruptStateError) as raised:
                        store.write(state, -1, lease=lease)
                finally:
                    lease.release()
                self.assertNotIn(sentinel, "".join(traceback.format_exception(
                    type(raised.exception), raised.exception, raised.exception.__traceback__,
                )))

    def test_run_lease_release_error_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            lease = RunLease(path).acquire()
            sentinel = "never-render-lease-release"
            with mock.patch.object(LockHandle, "release", side_effect=OSError(sentinel)), \
                    self.assertRaises(LeaseConflictError) as raised:
                lease.release()
            self.assertIsNone(raised.exception.__cause__)
            self.assertNotIn(sentinel, "".join(traceback.format_exception(
                type(raised.exception), raised.exception, raised.exception.__traceback__,
            )))

    def test_prepared_state_is_opaque_and_publishes_registry_owned_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            prepared = store.prepare(state)
            self.assertIs(type(prepared), PreparedState)
            self.assertFalse(hasattr(prepared, "__dict__"))
            self.assertFalse(hasattr(prepared, "state"))
            self.assertFalse(hasattr(prepared, "encoded"))
            self.assertFalse(hasattr(store, "_prepared"))
            for name, value in (("state", replace(state, revision=99)),
                                ("encoded", b"corrupt\n"),
                                ("_state", replace(state, revision=99)),
                                ("_encoded", b"corrupt\n")):
                with self.subTest(name=name), self.assertRaises((AttributeError, TypeError)):
                    object.__setattr__(prepared, name, value)
            with RunLease(path) as lease:
                store.publish(prepared, -1, lease=lease)
            self.assertEqual(store.load(), state)

    def test_prepared_state_captures_revision_and_bytes_before_caller_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            state = RunState.new("run-1", "2026-07-14T00:00:00Z")
            prepared = store.prepare(state)
            object.__setattr__(state, "revision", 99)
            object.__setattr__(state, "run_id", "mutated-after-prepare")
            with RunLease(path) as lease:
                evidence = store.publish(prepared, -1, lease=lease)
            self.assertEqual(evidence["revision"], 0)
            self.assertEqual(store.load().revision, 0)
            self.assertEqual(store.load().run_id, "run-1")

    def test_run_lease_and_state_store_capabilities_cannot_be_retargeted_or_shadowed(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            store = StateStore(first)
            lease = RunLease(first).acquire()
            try:
                for target, name, value in (
                    (lease, "state_path", second),
                    (lease, "path", second.with_suffix(".lease")),
                    (lease, "require_authorized", lambda *_: None),
                    (lease, "_handle", object()),
                    (store, "path", second),
                    (store, "_prepared", {}),
                ):
                    with self.subTest(name=name), self.assertRaises((AttributeError, TypeError)):
                        object.__setattr__(target, name, value)
                with self.assertRaises(TypeError):
                    RunLease.__init__(lease, second)
                with self.assertRaises(TypeError):
                    StateStore.__init__(store, second)
                with self.assertRaises(TypeError):
                    class ForgedLease(RunLease):
                        pass
                with self.assertRaises(TypeError):
                    class ForgedStore(StateStore):
                        pass
                with self.assertRaises(LeaseConflictError):
                    StateStore(second).write(
                        RunState.new("run-1", "2026-07-14T00:00:00Z"), -1, lease=lease,
                    )
                store.write(RunState.new("run-1", "2026-07-14T00:00:00Z"), -1, lease=lease)
            finally:
                lease.release()
            self.assertFalse(second.exists())

    def test_unissued_prepared_state_cannot_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            store = StateStore(path)
            unissued = object.__new__(PreparedState)
            with RunLease(path) as lease:
                with self.assertRaises(UnsafePayloadError):
                    store.publish(unissued, -1, lease=lease)
            self.assertFalse(path.exists())

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
                states = StateStore("run-state.json")
                events = EventStore(".")
                canonical_first = Path(first).resolve()
                self.assertEqual(events.path, canonical_first / "events.jsonl")
                self.assertEqual(states.path, canonical_first / "run-state.json")

                os.chdir(second)
                event = WorkflowEvent(
                    1, 0, "run-1", None, "run.initialized",
                    "2026-07-14T00:00:00Z", {"mode": "shadow"},
                )
                state = RunState.new("run-1", "2026-07-14T00:00:00Z")
                with RunLease(states.path) as lease:
                    events.append(event, 0, lease=lease)
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

    def test_garbage_collected_lease_releases_lock_for_reacquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-state.json"
            lease = RunLease(path).acquire()
            reference = weakref.ref(lease)
            del lease
            gc.collect()
            self.assertIsNone(reference())
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
                with self.assertRaises(LeaseConflictError) as raised:
                    StateStore(path).write(state, -1, lease=first)
                self.assertEqual(raised.exception.details["reason_code"], detail_digest("lease_identity_changed"))
                self.assertFalse(path.exists())
                StateStore(path).write(state, -1, lease=second)
            finally:
                first.release()
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
                with self.assertRaises(LeaseConflictError) as raised:
                    StateStore(path).write(state, -1, lease=first)
                self.assertEqual(raised.exception.details["reason_code"], detail_digest("lease_identity_changed"))
                self.assertFalse(path.exists())
                StateStore(path).write(state, -1, lease=second)
            finally:
                first.release()
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
            sentinel = "never-render-state-replace"
            with RunLease(path) as lease, mock.patch(
                    "workflow_kernel._files.os.rename", side_effect=OSError(sentinel)):
                with self.assertRaises(CorruptStateError) as raised:
                    store.write(original, original.revision, lease=lease)
            rendered = "".join(traceback.format_exception(
                type(raised.exception), raised.exception, raised.exception.__traceback__,
            ))
            self.assertIsNone(raised.exception.__cause__)
            self.assertNotIn(sentinel, rendered)
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

    def test_state_and_lease_rejections_do_not_retain_raw_path_causes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = "never-persist-state-path"
            state_path = root / sentinel
            state_path.symlink_to(root / "missing")
            state_path.with_name(state_path.name + ".lease").symlink_to(root / "missing-lease")
            for reject in (lambda: StateStore(state_path).load(),
                           lambda: RunLease(state_path).acquire()):
                with self.subTest(reject=reject), self.assertRaises((CorruptStateError, LeaseConflictError)) as raised:
                    reject()
                rendered = "".join(traceback.format_exception(
                    type(raised.exception), raised.exception, raised.exception.__traceback__,
                ))
                self.assertIsNone(raised.exception.__cause__)
                self.assertNotIn(sentinel, rendered)

    def test_lease_and_state_setup_errors_are_stable_and_secret_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = "never-render-filesystem-setup"
            blocker = root / sentinel
            blocker.write_text("not a directory")
            with self.assertRaises(LeaseConflictError) as lease_error:
                RunLease(blocker / "child" / "run-state.json").acquire()

            path = root / "run-state.json"
            store = StateStore(path)
            prepared = store.prepare(RunState.new("run-1", "2026-07-14T00:00:00Z"))
            with RunLease(path) as lease, mock.patch.object(
                    PinnedDirectory, "create_temporary", side_effect=OSError(sentinel)):
                with self.assertRaises(CorruptStateError) as state_error:
                    store.publish(prepared, -1, lease=lease)

            for raised in (lease_error.exception, state_error.exception):
                rendered = "".join(traceback.format_exception(
                    type(raised), raised, raised.__traceback__,
                ))
                self.assertIsNone(raised.__cause__)
                self.assertNotIn(sentinel, rendered)

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
