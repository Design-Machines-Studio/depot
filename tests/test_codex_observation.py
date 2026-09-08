import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from workflow_kernel.codex_observation import EVENTS, project_codex_hook
from workflow_kernel.live_observation import LiveObservationError, parent_identity, encode

CANARY = "PRIVATE_DISCARDED_CANARY"
ENV = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "plugins/workflow-kernel/skills/workflow-kernel/references")}


class CodexTests(unittest.TestCase):
    def test_every_discarded_field_and_child_model(self):
        private = ("prompt", "last_assistant_message", "tool_input", "tool_response",
                   "transcript_path", "agent_transcript_path", "cwd", "environment",
                   "credentials", "agent_type", "permission_mode", "tool_name", "raw_payload")
        for name in EVENTS:
            payload = {key: CANARY for key in private}
            payload.update(hook_event_name=name, session_id="parent", agent_id="child",
                           turn_id="turn-1", model="parent-model", source="resume", reason="other")
            event = project_codex_hook(payload, workspace="workspace")
            self.assertNotIn(CANARY.encode(), encode(event))
            self.assertEqual(event["outcome"], "unknown")
            self.assertIsNone(event["facts"]["source_timestamp"]["value"])
            self.assertIsNone(event["facts"]["event"]["value"])
            if name.startswith("Subagent"):
                self.assertEqual(event["facts"]["session"]["value"], "child")
                self.assertEqual(event["facts"]["parent"]["value"], "parent")
                self.assertIsNone(event["facts"]["model"]["value"])
                self.assertIsNone(event["facts"]["turn"]["value"])

    def test_unsupported_claims_are_not_native_facts(self):
        payload = dict(hook_event_name="Stop", session_id="session", success=True,
                       outcome="failure", provider="invented", timestamp="2000-01-01", parent_id="guess")
        event = project_codex_hook(payload, workspace="w")
        self.assertEqual(event["outcome"], "unknown")
        self.assertIsNone(event["facts"]["parent"]["value"])
        for key, value in (("schema_version", 2), ("hook_event_name", "Unknown"), ("session_id", "../escape")):
            with self.assertRaises(LiveObservationError):
                project_codex_hook({**payload, key: value}, workspace="w")

    def test_hook_cli_is_inert_on_success_and_every_error(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "obs"; parent.mkdir(mode=0o700)
            command = [sys.executable, "-m", "workflow_kernel", "codex-observation-hook",
                       "--parent", str(parent), "--identity", parent_identity(parent), "--workspace", "w"]
            valid = json.dumps(dict(hook_event_name="UserPromptSubmit", session_id="s",
                                    turn_id="t", prompt=CANARY)).encode()
            inputs = [valid, b'{', b'{"secret":"'+CANARY.encode()+b'","secret":0}',
                      CANARY.encode()*30000, b'{"private":' + b'['*14+b'0'+b']'*14+b'}']
            for raw in inputs:
                result = subprocess.run(command, input=raw, capture_output=True, env=ENV, timeout=3)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"{}\n", b""))
            self.assertEqual(len(list(parent.glob("*/snapshot.json"))), 1)
            for path in parent.rglob("*"):
                if path.is_file(): self.assertNotIn(CANARY.encode(), path.read_bytes())
            broken = command.copy(); broken[broken.index("--identity")+1] = "wrong"
            result = subprocess.run(broken, input=valid, capture_output=True, env=ENV, timeout=3)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"{}\n", b""))
            # No EOF: callback ingestion times out without waiting for the producer.
            proc = subprocess.Popen(command, env=ENV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                proc.stdin.write(b'{'); proc.stdin.flush()
                proc.wait(timeout=2)
                self.assertEqual(proc.stdout.read(), b"{}\n")
                self.assertEqual(proc.stderr.read(), b"")
            finally:
                proc.stdin.close(); proc.stdout.close(); proc.stderr.close()

    def test_validation_and_neutral_publication_cli(self):
        fixture = Path(__file__).parent / "fixtures/live-observation/event.json"
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "obs"; parent.mkdir(mode=0o700)
            command = [sys.executable, "-m", "workflow_kernel", "live-observation-publish",
                       "--parent", str(parent), "--identity", parent_identity(parent)]
            result = subprocess.run(command, input=fixture.read_bytes(), capture_output=True, env=ENV, timeout=3)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(result.stdout)
            validate = subprocess.run([sys.executable, "-m", "workflow_kernel", "live-observation-validate",
                                       str(parent / state["session_key"])], capture_output=True, env=ENV, timeout=3)
            self.assertEqual(validate.returncode, 0, validate.stderr)
            self.assertEqual(json.loads(validate.stdout), state)

    def test_deadline_skips_diagnostic_io(self):
        import contextlib
        import io
        import time
        from types import SimpleNamespace
        from unittest import mock
        from workflow_kernel import codex_observation as adapter
        args = SimpleNamespace(workspace="w", producer="p", parent="/unused", identity="0:0")
        started = time.monotonic()
        with mock.patch.object(adapter, "read_callback", side_effect=lambda: time.sleep(2)):
            with mock.patch("workflow_kernel.live_observation.publish_diagnostic") as diagnostic:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(adapter.hook_main(args), 0)
                diagnostic.assert_not_called()
        self.assertLess(time.monotonic() - started, 1.3)
        self.assertEqual(output.getvalue(), "{}\n")

    def test_malformed_hook_configuration_is_inert(self):
        result = subprocess.run([sys.executable, "-m", "workflow_kernel", "codex-observation-hook"],
                                input=b"PRIVATE_CANARY", capture_output=True, env=ENV, timeout=3)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"{}\n", b""))

    def test_schema_has_closed_availability_and_timestamp_facts(self):
        path = Path(__file__).resolve().parents[1] / "plugins/workflow-kernel/skills/workflow-kernel/references/live-observation-schema.json"
        schema = json.loads(path.read_bytes())
        branches = schema["$defs"]["timestamp_fact"]["oneOf"]
        self.assertEqual(branches[0]["properties"]["value"]["format"], "date-time")
        self.assertEqual(branches[0]["properties"]["reason"], {"type": "null"})
        self.assertEqual(branches[1]["properties"]["value"], {"type": "null"})
        self.assertEqual(branches[1]["properties"]["provenance"], {"type": "null"})

    def test_native_late_tool_return_does_not_reopen_interrupted_response(self):
        from workflow_kernel.live_observation import reduce_live_observation, observation_view
        state = None
        for index, name in enumerate(("UserPromptSubmit", "PreToolUse", "Interrupt", "PostToolUse")):
            e = project_codex_hook({"hook_event_name":name, "session_id":"s", "turn_id":"t",
                                   "tool_use_id":"call"}, workspace="w",
                                  observed_at=f"2026-09-08T00:00:0{index}Z")
            state = reduce_live_observation(state, e)
        view = observation_view(state)
        self.assertEqual(view["last_activity"], "tool_returned")
        self.assertEqual(view["execution"], "interrupted")
        self.assertEqual(view["response"], "closed")
        self.assertEqual(view["outcome"], "unknown")

    def test_unrelated_tool_return_does_not_resolve_approval(self):
        from workflow_kernel.live_observation import reduce_live_observation
        state = None
        for name in ("PermissionRequest", "PostToolUse"):
            e = project_codex_hook({"hook_event_name":name,"session_id":"s","turn_id":"t"},workspace="w")
            state = reduce_live_observation(state,e)
        self.assertEqual(state["state"]["attention"]["value"], "approval_required")
        self.assertEqual(state["state"]["execution"]["value"], "waiting")
