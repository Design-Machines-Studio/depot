import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
