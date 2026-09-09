import copy
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from workflow_kernel import live_observation as live
from workflow_kernel.codex_observation import project_codex_hook

STAMP = "2026-09-08T00:00:00Z"


def event(name="UserPromptSubmit", session="session-1", **kwargs):
    return project_codex_hook({"hook_event_name": name, "session_id": session,
        "source": "startup", "reason": "other", "turn_id": "turn-1", **kwargs},
        workspace="workspace-1", observed_at=STAMP)


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name) / "observations"
        self.parent.mkdir(mode=0o700)
        self.identity = live.parent_identity(self.parent)

    def publish(self, e):
        return live.publish_live_observation(self.parent, self.identity, e)

    def path(self, e):
        return self.parent / live.session_key(e) / "snapshot.json"

    def test_first_update_duplicate_conflict(self):
        a = event()
        first = self.publish(a)
        self.assertEqual(first["revision"], 1)
        self.assertEqual(self.publish(a), first)
        b = event("Stop")
        self.assertEqual(self.publish(b)["revision"], 2)
        bad = copy.deepcopy(a)
        bad["activity"] = "interrupted"
        with self.assertRaises(live.LiveObservationError):
            self.publish(bad)
        self.assertEqual(json.loads(self.path(a).read_bytes())["revision"], 2)

    def test_concurrent_hooks_do_not_lose_updates(self):
        events = [event() for _ in range(16)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(self.publish, events))
        last = json.loads(self.path(events[0]).read_bytes())
        self.assertEqual(last["revision"], 16)
        self.assertEqual({e["publication_id"] for e in last["recent_activity"]},
                         {e["publication_id"] for e in events})
        self.assertEqual(len(results), 16)

    def test_child_before_parent_and_nested(self):
        child = event("SubagentStart", agent_id="child")
        grandchild = event("SubagentStart", session="child", agent_id="grandchild")
        self.assertEqual(self.publish(grandchild)["relationships"]["parent"], "child")
        self.assertEqual(self.publish(child)["relationships"]["parent"], "session-1")
        self.publish(event("SessionStart"))
        self.assertEqual(len(list(self.parent.glob("*/snapshot.json"))), 3)
        conflict = event("SubagentStart", session="other-parent", agent_id="child")
        with self.assertRaises(live.LiveObservationError):
            self.publish(conflict)

    def test_resume_compaction_fork_and_distinct_attempts(self):
        items = [event("SessionStart"), event("SessionStart", source="resume"),
                 event("SessionStart", source="compact"), event(), event()]
        for n, e in enumerate(items, 1):
            e["facts"]["attempt"] = live.available("attempt-" + str(n), "explicit_binding")
            self.assertEqual(self.publish(e)["revision"], n)
        self.publish(event("SessionStart", session="fork"))
        self.assertEqual(len(list(self.parent.glob("*/snapshot.json"))), 2)

    def test_out_of_order_preserves_newer_recorded_attention(self):
        waiting = event("PermissionRequest")
        waiting["observed_at"] = "2026-09-08T00:00:10Z"
        self.publish(waiting)
        result = self.publish(event())
        self.assertEqual(live.observation_view(result)["attention"], "approval_required")
        self.assertEqual(result["revision"], 2)
        self.assertEqual(result["recent_activity"][-1]["activity"], "turn_submitted")

    def test_silence_read_failure_recovery_keep_waiting_and_outcome_separate(self):
        e = event("PermissionRequest")
        result = self.publish(e)
        now = dt.datetime.fromisoformat(STAMP.replace("Z", "+00:00"))
        self.assertEqual(live.observation_view(result, now)["contact"], "confirmed")
        stale = live.observation_view(result, now + dt.timedelta(seconds=31))
        self.assertEqual((stale["contact"], stale["execution"], stale["outcome"]),
                         ("unconfirmed", "waiting", "unknown"))
        self.assertEqual(live.observation_view(result, now, "failed")["contact"], "unconfirmed")
        self.assertEqual(live.observation_view(result, now)["read_health"], "ok")
        self.assertEqual(live.observation_view(self.publish(event("Stop")), now)["outcome"], "unknown")
        closed = self.publish(event("SessionEnd"))
        self.assertEqual(live.observation_view(closed, now)["session_state"], "closed")
        for outcome in ("success", "failure"):
            explicit = event()
            explicit.update(activity="outcome_reported", outcome=outcome)
            self.assertEqual(self.publish(explicit)["state"]["outcome"]["value"], outcome)

    def test_bounds_visible_no_session_eviction(self):
        state = None
        for _ in range(210):
            state = live.reduce_live_observation(state, event())
        self.assertLessEqual(len(live.encode(state)), 65536)
        self.assertLessEqual(len(state["recent_activity"]), 200)
        self.assertGreater(state["dropped_activity"], 0)
        self.assertEqual(state["diagnostics"], ["activity_truncated"])
        with mock.patch.object(live, "MAX_SESSIONS", 2):
            self.publish(event(session="one"))
            self.publish(event(session="two"))
            with self.assertRaises(live.LiveObservationError):
                self.publish(event(session="three"))
        self.assertEqual(len(list(self.parent.glob("*/snapshot.json"))), 2)
        self.assertEqual(json.loads((self.parent / "diagnostic.json").read_bytes())["code"], "session_limit")

    def test_private_fields_and_validation(self):
        e = event(prompt="SECRET", environment={"key": "SECRET"})
        self.assertNotIn(b"SECRET", live.encode(self.publish(e)))
        for raw in (b'{"a":1,"a":2}', b'{', b'{"a":NaN}', b'{"x":' + b'['*14 + b'0'+b']'*14+b'}', b'x'*262145):
            with self.assertRaises(live.LiveObservationError) as ctx:
                live.parse_bounded(raw)
            self.assertNotIn("SECRET", repr(ctx.exception))
        state = self.publish(e)
        for key, val in (("contract", "live-observation-v2"), ("revision", True), ("digest", "wrong")):
            bad = copy.deepcopy(state); bad[key] = val
            with self.assertRaises(live.LiveObservationError):
                live.validate_live_observation(bad)

    def test_symlinks_root_replacement_traversal_prefix(self):
        link = Path(self.temp.name) / "linked"
        link.symlink_to(self.parent, target_is_directory=True)
        for path in (link, str(self.parent) + "/../observations", str(self.parent) + "-other"):
            with self.assertRaises((live.LiveObservationError, OSError)):
                live.publish_live_observation(path, self.identity, event())
        moved = self.parent.with_name("original")
        self.parent.rename(moved); self.parent.mkdir(mode=0o700)
        with self.assertRaises(live.LiveObservationError):
            self.publish(event())
        self.assertEqual(list(moved.iterdir()), [])

    def test_symlink_fifo_device_and_hardlink_snapshots(self):
        e = event(); self.publish(e)
        path = self.path(e)
        path.unlink(); path.symlink_to("/dev/null")
        with self.assertRaises(live.LiveObservationError): self.publish(event())
        path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaises(live.LiveObservationError): self.publish(event())
        path.unlink()
        target = self.parent / "outside"; target.write_text("CANARY"); target.chmod(0o600)
        os.link(target, path)
        with self.assertRaises(live.LiveObservationError): self.publish(event())
        self.assertEqual(target.read_text(), "CANARY")
        with open("/dev/null", "rb") as device:
            with self.assertRaises(live.LiveObservationError): live.private_file(device.fileno())

    def test_failure_preserves_last_valid_and_atomic_replacement(self):
        e = event(); self.publish(e)
        old = self.path(e).read_bytes()
        for operation in ("replace", "fsync"):
            with mock.patch.object(live.os, operation, side_effect=OSError("PRIVATE_CANARY")):
                with self.assertRaises(live.LiveObservationError) as ctx:
                    self.publish(event())
            self.assertNotIn("PRIVATE_CANARY", repr(ctx.exception))
            self.assertEqual(old, self.path(e).read_bytes())
        done = threading.Event(); errors = []
        def reader():
            while not done.is_set():
                try: live.validate_live_observation(live.parse_bounded(self.path(e).read_bytes()))
                except Exception as ex: errors.append(type(ex).__name__)
        t = threading.Thread(target=reader); t.start()
        try:
            for _ in range(8): self.publish(event())
        finally: done.set(); t.join()
        self.assertEqual(errors, [])

    def test_containment_race_and_changing_read(self):
        e = event(); self.publish(e)
        with live.pinned_directory(self.parent) as (fd, verify):
            self.parent.rename(self.parent.with_name("moved"))
            self.parent.mkdir(mode=0o700)
            with self.assertRaises(live.LiveObservationError): verify()
        # A changing snapshot cannot become a validated read.
        self.parent = self.parent.with_name("moved")
        path = self.path(e)
        original_read = os.read
        def change(fd, size):
            result = original_read(fd, size)
            path.write_bytes(b"truncated")
            return result
        with live.pinned_directory(path.parent) as (fd, _):
            with mock.patch.object(live.os, "read", side_effect=change):
                with self.assertRaises(live.LiveObservationError): live.read_snapshot(fd)

    def test_out_of_order_overflow_and_old_publication_replay(self):
        latest = event("Stop")
        latest["observed_at"] = "2026-09-08T00:01:00Z"
        first = self.publish(latest)
        for _ in range(65):
            state = self.publish(event())
        self.assertGreater(state["dropped_activity"], 0)
        self.assertEqual(state["last_observed_at"], latest["observed_at"])
        self.assertEqual(live.observation_view(state)["last_activity"], "response_closed")
        self.assertEqual(self.publish(first), state)
        self.assertEqual(self.publish(state), state)

    def test_processes_open_parent_before_first_publication(self):
        import contextlib
        import multiprocessing
        context = multiprocessing.get_context("fork")
        barrier = context.Barrier(4)
        queue = context.Queue()
        original = live.pinned_directory
        def worker():
            @contextlib.contextmanager
            def synchronized(path):
                with original(path) as held:
                    barrier.wait(timeout=5)
                    yield held
            with mock.patch.object(live, "pinned_directory", synchronized):
                try: queue.put(self.publish(event())["revision"])
                except live.LiveObservationError as error: queue.put(error.code)
        processes = [context.Process(target=worker) for _ in range(4)]
        try:
            for process in processes: process.start()
            results = [queue.get(timeout=5) for _ in processes]
            self.assertEqual(sorted(results, key=str), [1, 2, 3, 4])
        finally:
            for process in processes:
                process.join(timeout=5)
                if process.is_alive(): process.terminate(); process.join(timeout=5)
            queue.close(); queue.join_thread()

    def test_delayed_known_fact_replaces_only_unknown_placeholder(self):
        newer = event()
        newer["observed_at"] = "2026-09-08T00:00:01Z"
        state = live.reduce_live_observation(None, newer)
        state = live.reduce_live_observation(state, event("SessionStart"))
        self.assertEqual(state["state"]["session_state"]["value"], "open")
