import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class RuntimeCliTests(unittest.TestCase):
    def run_cli(self, *args, env_extra=None):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1]))
        if env_extra:
            env.update(env_extra)
        return subprocess.run([sys.executable, "-m", "workflow_kernel", *map(str, args)], text=True, capture_output=True, env=env, check=False)

    def test_observe_pipeline_writes_shadow_artifact_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature": "pipeline-1", "workflowClass": "feature", "executionMode": "codex_native",
                "chunks": [{"id": "chunk-a", "dependsOn": []}], "executionPlan": {"levels": [{"level": 0, "strategy": "sequential", "chunks": ["chunk-a"]}]},
            }))
            result = self.run_cli("observe-pipeline", "--manifest", manifest, "--receipts", FIXTURES / "pipeline-codex.json", "--state-dir", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            artifact = json.loads((root / "pipeline-shadow-observation.json").read_text())
            self.assertEqual(artifact["run_spec"]["workflow_class"], "feature")
            self.assertEqual(artifact["event_count"], 11)

    def test_metrics_and_invalid_input_exit_codes_are_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "metrics.json"
            good = self.run_cli("metrics", "--events", FIXTURES / "pipeline-claude.json", "--output", output)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(output.read_text())["tokens"], 1200)
            bad_input = Path(directory) / "bad.json"
            bad_input.write_text("not-json")
            bad = self.run_cli("metrics", "--events", bad_input, "--output", output)
            self.assertEqual(bad.returncode, 2)

    def test_compare_returns_five_for_parity_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pipeline-shadow-observation.json").write_text(json.dumps({"run_state": {
                "schema_version": 1, "revision": 0, "run_id": "pipeline-1", "mode": "shadow", "status": "planned",
                "created_at": "2026-07-14T00:00:00Z", "updated_at": "2026-07-14T00:00:00Z", "nodes": {}, "evidence": [], "cleanup_reconciled": False,
            }}))
            output = root / "parity.json"
            result = self.run_cli("compare", "--state-dir", root, "--authoritative-receipts", FIXTURES / "pipeline-claude.json", "--output", output)
            self.assertEqual(result.returncode, 5)
            self.assertFalse(json.loads(output.read_text())["safe_to_promote"])

    def test_compare_uses_predicted_receipt_semantics_not_evidence_membership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
            predicted = json.loads(json.dumps(receipts)); predicted[2]["status"] = "failed"
            from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
            events = translate_pipeline_receipts(predicted)
            (root / "pipeline-shadow-observation.json").write_text(json.dumps({
                "events": [event.to_dict() for event in events],
                "run_state": {"schema_version":1,"revision":len(events),"run_id":"pipeline-1","mode":"shadow","status":"running","created_at":events[0].occurred_at,"updated_at":events[-1].occurred_at,"nodes":{},"evidence":[event.payload["authoritative_receipt"] for event in events],"cleanup_reconciled":False},
            }))
            output = root / "parity.json"
            result = self.run_cli("compare", "--state-dir", root, "--authoritative-receipts", FIXTURES / "pipeline-claude.json", "--output", output)
            self.assertEqual(result.returncode, 5)
            self.assertFalse(json.loads(output.read_text())["semantic_match"])

    def test_json_output_rejects_symlink_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); victim = root / "victim"; victim.write_text("safe")
            output = root / "metrics.json"; output.symlink_to(victim)
            result = self.run_cli("metrics", "--events", FIXTURES / "pipeline-claude.json", "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(victim.read_text(), "safe")

    def test_cleanup_command_surface_and_plan_create(self):
        help_result = self.run_cli("--help")
        for command in ("plan-create", "plan-compose", "record-create", "plan-cleanup", "next-cleanup-step", "execute-cleanup-step", "record-cleanup", "plan-reconcile"):
            self.assertIn(command, help_result.stdout)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); argv = root / "argv.json"; output = root / "plan.json"
            argv.write_text(json.dumps(["docker", "run", "--name", "review-box", "image:latest"]))
            result = self.run_cli("plan-create", "--state-dir", root, "--run-id", "run-1", "--node-id", "chunk-1", "--lifecycle", "chunk", "--cleanup-policy", "stop-remove", "--argv-json", argv, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(output.read_text())
            self.assertTrue(plan["managed"])
            self.assertIn("com.designmachines.depot.run-id", plan["labels"])

    def test_runtime_resolver_ignores_cwd_and_rejects_symlink_escape(self):
        from workflow_kernel.cli import resolve_workflow_kernel_runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); depot = root / "depot"; pipeline = depot / "plugins" / "pipeline"
            runtime = depot / "plugins" / "workflow-kernel"; refs = runtime / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
            refs.mkdir(parents=True); pipeline.mkdir(parents=True)
            (runtime / ".claude-plugin").mkdir(); (runtime / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name":"workflow-kernel","version":"1.0.0"}))
            (refs / "__main__.py").write_text("")
            forged = root / "target" / "workflow_kernel"; forged.mkdir(parents=True); (forged / "__main__.py").write_text("")
            self.assertEqual(resolve_workflow_kernel_runtime(pipeline, home=root / "home"), refs.parent)
            escaped = depot / "plugins" / "workflow-kernel-escape"; escaped.symlink_to(root / "target", target_is_directory=True)
            self.assertNotEqual(resolve_workflow_kernel_runtime(pipeline, home=root / "home"), escaped)

    def test_stale_reconcile_ttl_is_effective_and_missing_lease_proof_blocks(self):
        from workflow_kernel.adapters.docker import (
            CREATED_LABEL, LIFECYCLE_LABEL, MANAGED_LABEL, NODE_LABEL,
            POLICY_LABEL, RUN_LABEL, DockerAdapter, DockerInventory,
            DockerResource, LeaseProof,
        )
        from workflow_kernel.cli import _stale_cleanup_plan
        from workflow_kernel.resources import CommandResult, ResourceKind

        now = datetime(2026, 7, 15, tzinfo=timezone.utc)
        created = now - timedelta(hours=48)
        labels = {
            MANAGED_LABEL: "true", RUN_LABEL: "old-run", NODE_LABEL: "chunk-1",
            CREATED_LABEL: created.isoformat().replace("+00:00", "Z"),
            LIFECYCLE_LABEL: "run", POLICY_LABEL: "remove-when-stopped",
        }
        inventory = DockerInventory((DockerResource(
            "container-1", ResourceKind.CONTAINER, labels, created,
        ),), source="managed_orphan_sweep")

        class Runner:
            def run(self, argv):
                return CommandResult(tuple(argv), 0, "", "")

        class InactiveLease:
            def read(self, run_id):
                return LeaseProof(run_id, False, True, now)

        proved = DockerAdapter(Runner(), now=lambda: now, lease_reader=InactiveLease())
        self.assertTrue(_stale_cleanup_plan(proved, inventory, 24).actions)
        retained = _stale_cleanup_plan(proved, inventory, 72)
        self.assertEqual(retained.dispositions[0].reason, "ttl_not_expired")
        blocked = _stale_cleanup_plan(DockerAdapter(Runner(), now=lambda: now), inventory, 24)
        self.assertFalse(blocked.actions)
        self.assertEqual(blocked.dispositions[0].reason, "lease_reader_unavailable")


if __name__ == "__main__":
    unittest.main()
