import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class PredictionAuthorityTests(unittest.TestCase):
    def run_cli(self, root, *args):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1]))
        return subprocess.run(
            [sys.executable, "-m", "workflow_kernel", *map(str, args)],
            cwd=root, env=env, text=True, capture_output=True, check=False,
        )

    def repository(self, directory):
        root = Path(directory) / "repo"
        root.mkdir()
        subprocess.run(["git", "init", "-q", root], check=True)
        state_dir = root / "plans" / "pipeline-1"
        state_dir.mkdir(parents=True)
        manifest = state_dir / "manifest.json"
        manifest.write_text(json.dumps({
            "feature": "pipeline-1", "workflowClass": "feature",
            "executionMode": "codex_native", "chunks": [],
        }))
        return root, state_dir, manifest

    def init_run(self, root, run_id="pipeline-1"):
        result = self.run_cli(
            root, "init", root / ".workflow-kernel" / "runs" / run_id,
            "--run-id", run_id, "--mode", "shadow",
            "--occurred-at", "2026-07-15T00:00:00Z",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def append_started(self, root, run_id="pipeline-1", sequence=2):
        event = json.dumps({
            "schema_version": 1, "sequence": sequence, "run_id": run_id,
            "node_id": None, "kind": "run.started",
            "occurred_at": "2026-07-15T00:00:02Z", "payload": {},
        })
        return self.run_cli(
            root, "append", root / ".workflow-kernel" / "runs" / run_id,
            "--event", event,
        )

    def test_identical_prediction_is_valid_only_when_bound_before_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root, state_dir, manifest = self.repository(directory)
            self.init_run(root)
            receipts = state_dir / "prediction.json"
            receipts.write_text((FIXTURES / "pipeline-codex.json").read_text())
            bound = self.run_cli(
                root, "bind-prediction", "--type", "pipeline",
                "--manifest", manifest, "--prediction-receipts", receipts,
                "--state-dir", state_dir,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            started = self.append_started(root)
            self.assertEqual(started.returncode, 0, started.stderr)
            authoritative = state_dir / "authoritative.json"
            authoritative.write_text(receipts.read_text())
            observed = self.run_cli(
                root, "observe-pipeline", "--manifest", manifest,
                "--receipts", authoritative, "--state-dir", state_dir,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            output = state_dir / "parity.json"
            compared = self.run_cli(
                root, "compare", "--state-dir", state_dir,
                "--authoritative-receipts", authoritative, "--output", output,
            )
            self.assertEqual(compared.returncode, 0, compared.stderr)
            self.assertEqual(json.loads(output.read_text())["reason"], "match")

    def test_binding_after_run_started_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root, state_dir, manifest = self.repository(directory)
            self.init_run(root)
            started = self.append_started(root, sequence=1)
            self.assertEqual(started.returncode, 0, started.stderr)
            result = self.run_cli(
                root, "bind-prediction", "--type", "pipeline",
                "--manifest", manifest,
                "--prediction-receipts", FIXTURES / "pipeline-codex.json",
                "--state-dir", state_dir,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_observe_rejects_missing_or_forged_lifecycle_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root, state_dir, manifest = self.repository(directory)
            self.init_run(root)
            prediction = state_dir / "prediction.json"
            values = json.loads((FIXTURES / "pipeline-codex.json").read_text())
            values[0]["prediction_basis"] = "ignored-field-is-not-authority"
            prediction.write_text(json.dumps(values))
            bound = self.run_cli(
                root, "bind-prediction", "--type", "pipeline",
                "--manifest", manifest, "--prediction-receipts", prediction,
                "--state-dir", state_dir,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            lifecycle = root / ".workflow-kernel" / "runs" / "pipeline-1"
            started = self.append_started(root, sequence=2)
            self.assertEqual(started.returncode, 0, started.stderr)
            event_path = lifecycle / "events.jsonl"
            lines = event_path.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            for mutation in (
                (lines[0], lines[2]),
                (lines[0], lines[2], lines[1]),
            ):
                event_path.write_text("\n".join(mutation) + "\n")
                result = self.run_cli(
                    root, "observe-pipeline", "--manifest", manifest,
                    "--receipts", FIXTURES / "pipeline-codex.json",
                    "--state-dir", state_dir,
                )
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
