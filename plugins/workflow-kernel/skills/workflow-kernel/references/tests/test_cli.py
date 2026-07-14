import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests import detail_digest, detail_key_digest
from workflow_kernel import cli
from workflow_kernel.cli import command_append, command_init, command_replay, command_validate
from workflow_kernel.schema import ErrorMessage, InvalidSchemaError, UnsafePayloadError


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).parents[1])
        return subprocess.run([sys.executable, "-m", "workflow_kernel", *args], text=True, capture_output=True, env=env, check=False)

    def test_help_lists_commands(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        for command in ("init", "validate", "append", "replay", "status"):
            self.assertIn(command, result.stdout)

    def test_init_append_replay_status_and_safe_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli("init", directory, "--run-id", "run-1", "--occurred-at", "2026-07-14T00:00:00Z").returncode, 0)
            state_path = Path(directory) / "run-state.json"
            self.assertEqual(json.loads(state_path.read_text())["mode"], "shadow")
            event_data = {
                "schema_version": 1, "sequence": 1, "run_id": "run-1", "node_id": None,
                "kind": "run.started", "occurred_at": "2026-07-14T00:00:01Z", "payload": {},
            }
            self.assertEqual(self.run_cli("append", directory, "--event", json.dumps(event_data)).returncode, 0)
            self.assertEqual(self.run_cli("replay", directory).returncode, 0)
            status = self.run_cli("status", directory)
            self.assertEqual(json.loads(status.stdout)["status"], "running")
            bad = self.run_cli("append", directory, "--event", '{"password":"fixture-secret"}')
            self.assertNotEqual(bad.returncode, 0)
            self.assertNotIn("fixture-secret", bad.stderr)

    def test_validate_rejects_missing_empty_and_state_without_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = self.run_cli("validate", directory)
            self.assertNotEqual(missing.returncode, 0)
            Path(directory, "events.jsonl").write_text("")
            empty = self.run_cli("validate", directory)
            self.assertNotEqual(empty.returncode, 0)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli("init", directory, "--run-id", "run-1", "--occurred-at", "2026-07-14T00:00:00Z").returncode, 0)
            Path(directory, "events.jsonl").write_text("")
            result = self.run_cli("validate", directory)
            self.assertNotEqual(result.returncode, 0)

    def test_argparse_error_does_not_echo_rejected_value(self):
        sentinel = "NEVER-PRINT-THIS-SECRET"
        result = self.run_cli("init", "/tmp/unused", "--run-id", "run-1",
                              "--occurred-at", "2026-07-14T00:00:00Z", "--mode", sentinel)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(sentinel, result.stderr)
        expected = detail_digest("invalid_argument")
        self.assertEqual(json.loads(result.stderr)["error"]["details"]["reason_code"], expected)

    def test_rejected_event_kind_is_hashed_in_public_error_details(self):
        sentinel = "never-persist-rejected-event-kind"
        digest = detail_digest(sentinel)
        with tempfile.TemporaryDirectory() as directory:
            initialized = self.run_cli(
                "init", directory, "--run-id", "run-1",
                "--occurred-at", "2026-07-14T00:00:00Z",
            )
            self.assertEqual(initialized.returncode, 0)
            event = {
                "schema_version": 1,
                "sequence": 1,
                "run_id": "run-1",
                "node_id": None,
                "kind": sentinel,
                "occurred_at": "2026-07-14T00:00:01Z",
                "payload": {},
            }
            rejected = self.run_cli("append", directory, "--event", json.dumps(event))
        self.assertEqual(rejected.returncode, 2)
        self.assertNotIn(sentinel, rejected.stderr)
        self.assertEqual(json.loads(rejected.stderr)["error"]["details"]["kind"], digest)

    def test_main_uses_base_owned_serializer_for_trusted_subclasses(self):
        sentinel = "never-persist-subclass-serializer"

        class TrustedError(UnsafePayloadError):
            def to_dict(self):
                return {"secret": sentinel}

        error = TrustedError(ErrorMessage.INVALID_STRING_FIELD, {"field": sentinel})
        parsed = SimpleNamespace(handler=mock.Mock(side_effect=error))
        with mock.patch("workflow_kernel.cli.parser") as parser, \
                mock.patch("workflow_kernel.cli._emit") as emit:
            parser.return_value.parse_args.return_value = parsed
            self.assertEqual(cli.main([]), 2)
        emitted = emit.call_args.args[0]
        self.assertEqual(emitted["error"]["code"], "unsafe_payload")
        self.assertNotIn(sentinel, json.dumps(emitted, sort_keys=True))

    def test_main_hashes_unknown_error_detail_keys(self):
        sentinel = "never-persist-cli-detail-key"
        error = UnsafePayloadError(ErrorMessage.INVALID_STRING_FIELD, {sentinel: "value"})
        parsed = SimpleNamespace(handler=mock.Mock(side_effect=error))
        with mock.patch("workflow_kernel.cli.parser") as parser, \
                mock.patch("workflow_kernel.cli._emit") as emit:
            parser.return_value.parse_args.return_value = parsed
            self.assertEqual(cli.main([]), 2)
        emitted = emit.call_args.args[0]
        self.assertIn(detail_key_digest(sentinel), emitted["error"]["details"])
        self.assertNotIn(sentinel, json.dumps(emitted))

    def test_append_normalizes_deeply_nested_json_without_traceback(self):
        nested = "[" * 1_200 + "0" + "]" * 1_200
        result = self.run_cli("append", "/tmp/workflow-kernel-unused", "--event", nested)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "invalid_schema")
        self.assertNotIn("Traceback", result.stderr)

    def test_validate_loads_materialized_state_once_on_mismatch(self):
        materialized = SimpleNamespace(revision=3)
        reconstructed = SimpleNamespace(revision=4)
        events = mock.Mock()
        events.validate.return_value = ((object(),), ())
        states = mock.Mock()
        states.path.exists.return_value = True
        states.load.return_value = materialized
        args = SimpleNamespace(directory="unused", recovery=False)
        with mock.patch("workflow_kernel.cli._paths", return_value=(mock.Mock(), events, states)), \
                mock.patch("workflow_kernel.cli._coordinated_run", return_value=mock.MagicMock()), \
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine:
            engine.return_value.reconstruct.return_value = reconstructed
            with self.assertRaises(InvalidSchemaError):
                command_validate(args)
        states.load.assert_called_once_with()

    def test_validate_holds_run_lease_across_ledger_and_state_observation(self):
        active = {"lease": False}

        class Lease:
            def __enter__(self):
                active["lease"] = True
                return self

            def __exit__(self, *_):
                active["lease"] = False

        def observed(value):
            if not active["lease"]:
                raise AssertionError("validation observed outside run lease")
            return value

        reconstructed = SimpleNamespace(revision=1)
        events = mock.Mock()
        events.validate.side_effect = lambda **_: observed(((object(),), ()))
        states = mock.Mock()
        states.path.exists.side_effect = lambda: observed(True)
        states.load.side_effect = lambda: observed(reconstructed)
        with mock.patch("workflow_kernel.cli._paths", return_value=(mock.Mock(), events, states)), \
                mock.patch("workflow_kernel.cli.RunLease", return_value=Lease()), \
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine, \
                mock.patch("workflow_kernel.cli._emit"):
            engine.return_value.reconstruct.return_value = reconstructed
            self.assertEqual(command_validate(SimpleNamespace(directory="unused", recovery=False)), 0)
        self.assertFalse(active["lease"])

    def test_documented_cache_resolver_is_quiet_with_only_codex_cache(self):
        skill = Path(__file__).parents[2] / "SKILL.md"
        snippet = skill.read_text().split("```sh\n", 1)[1].split("```", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            refs = Path(directory) / ".codex/plugins/cache/depot/workflow-kernel/0.1.0/skills/workflow-kernel/references"
            package = refs / "workflow_kernel"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("")
            (package / "__main__.py").write_text("print('codex-only-runtime')\n")
            caller = Path(directory) / "caller"
            conflicting = caller / "workflow_kernel"
            conflicting.mkdir(parents=True)
            (conflicting / "__init__.py").write_text("")
            (conflicting / "__main__.py").write_text("print('caller-runtime')\n")
            env = dict(os.environ, HOME=directory, PYTHONPATH=str(caller))
            result = subprocess.run(["zsh", "-c", snippet], cwd=caller, text=True,
                                    capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("codex-only-runtime", result.stdout)
        self.assertNotIn("caller-runtime", result.stdout)

    def test_replay_holds_run_lease_across_observation_and_publication(self):
        active = {"lease": False}

        class ObservedPath:
            def exists(self):
                self.assert_active()
                return True

            @staticmethod
            def assert_active():
                if not active["lease"]:
                    raise AssertionError("state observed outside run lease")

        class Lease:
            def __enter__(self):
                active["lease"] = True
                return self

            def __exit__(self, *_):
                active["lease"] = False

        state = mock.Mock(run_id="run-1", revision=1)
        state.status.value = "planned"
        events = mock.Mock()
        events.replay.side_effect = lambda: (ObservedPath.assert_active(), (object(),))[1]
        states = mock.Mock(path=ObservedPath())
        states.load.side_effect = lambda: (ObservedPath.assert_active(), state)[1]
        states.write.side_effect = lambda *_args, **_kwargs: (
            ObservedPath.assert_active(), {"directory_fsync": "completed"}
        )[1]
        with mock.patch("workflow_kernel.cli._paths", return_value=(mock.Mock(), events, states)), \
                mock.patch("workflow_kernel.cli.RunLease", return_value=Lease()), \
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine, \
                mock.patch("workflow_kernel.cli._emit"):
            engine.return_value.reconstruct.return_value = state
            self.assertEqual(command_replay(SimpleNamespace(directory="unused")), 0)
        self.assertFalse(active["lease"])
        states.prepare.assert_not_called()

    def test_append_observes_state_before_publishing_event(self):
        order = []
        event_data = {
            "schema_version": 1, "sequence": 1, "run_id": "run-1", "node_id": None,
            "kind": "run.started", "occurred_at": "2026-07-14T00:00:01Z", "payload": {},
        }
        events = mock.Mock()
        events.replay.return_value = (object(),)
        events.append.side_effect = lambda *_args, **_kwargs: order.append("event")
        current = mock.Mock(revision=1)
        states = mock.Mock()
        states.path.exists.return_value = True
        states.load.side_effect = lambda: (order.append("state"), current)[1]
        prepared = object()
        states.prepare.side_effect = lambda *_: (order.append("prepare"), prepared)[1]
        states.publish.side_effect = lambda *_args, **_kwargs: (
            order.append("publish"), {"directory_fsync": "completed"}
        )[1]
        next_state = mock.Mock(revision=2)
        next_state.status.value = "running"
        coordinator = mock.MagicMock()
        coordinator.__enter__.return_value = object()
        with mock.patch("workflow_kernel.cli._paths", return_value=(mock.Mock(), events, states)), \
                mock.patch("workflow_kernel.cli._coordinated_run", return_value=coordinator), \
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine, \
                mock.patch("workflow_kernel.cli._emit"):
            engine.return_value.reconstruct.return_value = mock.Mock()
            engine.return_value.apply.return_value = next_state
            self.assertEqual(command_append(SimpleNamespace(directory="unused", event=json.dumps(event_data))), 0)
        self.assertEqual(order, ["state", "prepare", "event", "publish"])
        self.assertIs(events.append.call_args.kwargs["lease"], coordinator.__enter__.return_value)
        states.publish.assert_called_once_with(prepared, 1, lease=coordinator.__enter__.return_value)
        states.write.assert_not_called()

    def test_append_state_prepare_preserves_prior_ledger_and_state(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch("workflow_kernel.cli._emit"):
            command_init(SimpleNamespace(directory=directory, run_id="run-1", mode="shadow",
                                         occurred_at="2026-07-14T00:00:00Z"))
            events_path = Path(directory) / "events.jsonl"
            state_path = Path(directory) / "run-state.json"
            before_events = events_path.read_bytes()
            before_state = state_path.read_bytes()
            event_data = {
                "schema_version": 1, "sequence": 1, "run_id": "run-1", "node_id": None,
                "kind": "evidence.recorded", "occurred_at": "2026-07-14T00:00:01Z",
                "payload": {"evidence": ["x" * 256]},
            }
            with mock.patch("workflow_kernel.state.MAX_STATE_BYTES", len(before_state) + 16):
                with self.assertRaises(UnsafePayloadError):
                    command_append(SimpleNamespace(directory=directory, event=json.dumps(event_data)))
            self.assertEqual(events_path.read_bytes(), before_events)
            self.assertEqual(state_path.read_bytes(), before_state)


if __name__ == "__main__":
    unittest.main()
