import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from workflow_kernel.cli import command_append, command_replay, command_validate
from workflow_kernel.schema import InvalidSchemaError


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
        self.assertEqual(json.loads(result.stderr)["error"]["details"]["reason_code"], "invalid_argument")

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
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine:
            engine.return_value.reconstruct.return_value = reconstructed
            with self.assertRaises(InvalidSchemaError):
                command_validate(args)
        states.load.assert_called_once_with()

    def test_documented_cache_resolver_is_quiet_with_only_codex_cache(self):
        skill = Path(__file__).parents[2] / "SKILL.md"
        snippet = skill.read_text().split("```sh\n", 1)[1].split("```", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            refs = Path(directory) / ".codex/plugins/cache/depot/workflow-kernel/0.1.0/skills/workflow-kernel/references"
            package = refs / "workflow_kernel"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("")
            (package / "__main__.py").write_text("print('codex-only-runtime')\n")
            env = dict(os.environ, HOME=directory)
            env.pop("PYTHONPATH", None)
            result = subprocess.run(["zsh", "-c", snippet], text=True, capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("codex-only-runtime", result.stdout)

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
        states.write.return_value = {"directory_fsync": "completed"}
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
        self.assertEqual(order, ["state", "event"])


if __name__ == "__main__":
    unittest.main()
