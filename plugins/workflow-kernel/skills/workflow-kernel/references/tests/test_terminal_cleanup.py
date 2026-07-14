import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from workflow_kernel.adapters.docker import DockerAdapter, DockerInventory, DockerResource
from workflow_kernel.resources import CommandResult, OwnedResourceLifecycle, ResourceKind, ResourceRegistry
from workflow_kernel.schema import InvalidSchemaError, RunStatus


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


class FakeRunner:
    def run(self, argv):
        return CommandResult(tuple(argv), 0, "", "")


class TerminalCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.registry = ResourceRegistry(Path(self.directory.name) / "resources.jsonl")
        self.adapter = DockerAdapter(FakeRunner(), now=lambda: NOW)
        labels = self.adapter.labels_for("run-1", "node-1", "chunk", "stop-remove")
        self.inventory = DockerInventory((DockerResource("ctr-1", ResourceKind.CONTAINER, labels, NOW),))
        creation = self.adapter.plan_create(("docker", "run", "alpine"), "run-1", "node-1", "chunk", "stop-remove")
        self.adapter.record_creation(self.registry, DockerInventory(()), self.inventory, creation)
        self.lifecycle = OwnedResourceLifecycle(self.adapter)

    def tearDown(self):
        self.directory.cleanup()

    def test_chunk_cleanup_is_automatic_only_after_all_boundary_evidence(self):
        with self.assertRaises(InvalidSchemaError):
            self.lifecycle.after_chunk(self.registry, self.inventory, "run-1", "node-1", True, True, True, False)
        plan = self.lifecycle.after_chunk(self.registry, self.inventory, "run-1", "node-1", True, True, True, True)
        self.assertEqual(("docker", "rm", "ctr-1"), plan.actions[0].argv)

    def test_every_terminal_status_reconciles_run(self):
        for status in (
            RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BLOCKED,
            RunStatus.CANCELLED, RunStatus.INTERRUPTED,
        ):
            plan = self.lifecycle.at_terminal(self.registry, self.inventory, "run-1", status)
            self.assertEqual("run-1", plan.scope.run_id)
        with self.assertRaises(InvalidSchemaError):
            self.lifecycle.at_terminal(self.registry, self.inventory, "run-1", RunStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
