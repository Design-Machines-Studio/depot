import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from workflow_kernel.adapters.docker import DockerAdapter, DockerInventory, DockerResource, LeaseProof
from workflow_kernel.resources import CommandResult, CleanupDisposition, OwnedResourceLifecycle, ResourceKind, ResourceRegistry
from workflow_kernel.schema import InvalidSchemaError, RunStatus


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        return CommandResult(tuple(argv), 0, "", "")


class FakeLeaseReader:
    def read(self, run_id):
        return LeaseProof(run_id, False, True, NOW)


class TerminalCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.registry = ResourceRegistry(Path(self.directory.name) / "resources.jsonl")
        self.runner = FakeRunner()
        self.adapter = DockerAdapter(self.runner, now=lambda: NOW, lease_reader=FakeLeaseReader())
        labels = self.adapter.labels_for("run-1", "node-1", "chunk", "stop-remove")
        self.inventory = DockerInventory((DockerResource("ctr-1", ResourceKind.CONTAINER, labels, NOW),))
        creation = self.adapter.plan_create(("docker", "run", "alpine"), "run-1", "node-1", "chunk", "stop-remove")
        self.adapter.record_creation(
            self.registry, creation, CommandResult(creation.argv, 0, "ctr-1", ""),
            DockerInventory(()), self.inventory,
        )
        self.lifecycle = OwnedResourceLifecycle(self.adapter)

    def tearDown(self):
        self.directory.cleanup()

    def test_chunk_boundary_only_plans_and_never_executes(self):
        with self.assertRaises(InvalidSchemaError):
            self.lifecycle.after_chunk(self.registry, self.inventory, "run-1", "node-1", True, True, True, False)
        calls_before = tuple(self.runner.calls)
        plan = self.lifecycle.after_chunk(self.registry, self.inventory, "run-1", "node-1", True, True, True, True)
        self.assertEqual(("docker", "rm", "ctr-1"), plan.actions[0].argv)
        self.assertEqual(calls_before, tuple(self.runner.calls))

    def test_every_terminal_status_plans_reconciliation_and_receipt(self):
        for status in (
            RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BLOCKED,
            RunStatus.CANCELLED, RunStatus.INTERRUPTED,
        ):
            plan = self.lifecycle.at_terminal(self.registry, self.inventory, "run-1", status)
            action = plan.actions[0]
            key = ((ResourceKind.CONTAINER, "ctr-1"),)
            receipt = self.adapter.record_results(
                plan, (CommandResult(action.argv, 0, "", ""),),
                DockerInventory((), key, key, "registered_exact"),
            )
            self.assertTrue(receipt.scope.terminal)
            self.assertEqual(CleanupDisposition.REMOVED, receipt.dispositions[0].disposition)
            self.assertEqual((), receipt.after)
        with self.assertRaises(InvalidSchemaError):
            self.lifecycle.at_terminal(self.registry, self.inventory, "run-1", RunStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
