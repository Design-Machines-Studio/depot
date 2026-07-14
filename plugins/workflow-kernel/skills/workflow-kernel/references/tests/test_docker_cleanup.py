import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workflow_kernel.adapters.docker import DockerAdapter, DockerInventory, DockerResource
from workflow_kernel.resources import CleanupDisposition, CommandResult, ResourceKind, ResourceRegistry


NOW = datetime(2026, 7, 15, 1, 2, 3, tzinfo=timezone.utc)


class FakeRunner:
    def __init__(self, results=()):
        self.results = {result.argv: result for result in results}
        self.calls = []

    def run(self, argv):
        argv = tuple(argv)
        self.calls.append(argv)
        return self.results.get(argv, CommandResult(argv, 0, "", ""))


def owned_labels(*, lifecycle="chunk", created_at=NOW, cleanup_policy=None):
    return {
        "com.designmachines.depot.managed": "true",
        "com.designmachines.depot.run-id": "run-1",
        "com.designmachines.depot.node-id": "node-1",
        "com.designmachines.depot.created-at": created_at.isoformat().replace("+00:00", "Z"),
        "com.designmachines.depot.lifecycle": lifecycle,
        "com.designmachines.depot.cleanup-policy": cleanup_policy or "stop-remove",
    }


class DockerCreationTests(unittest.TestCase):
    def setUp(self):
        self.adapter = DockerAdapter(FakeRunner(), now=lambda: NOW)

    def test_supported_create_forms_inject_labels_before_creation(self):
        cases = (
            (("docker", "run", "alpine"), ResourceKind.CONTAINER),
            (("docker", "container", "create", "alpine"), ResourceKind.CONTAINER),
            (("docker", "network", "create", "net"), ResourceKind.NETWORK),
            (("docker", "volume", "create", "vol"), ResourceKind.VOLUME),
        )
        for argv, kind in cases:
            plan = self.adapter.plan_create(argv, "run-1", "node-1", "chunk", "stop-remove")
            self.assertTrue(plan.managed)
            self.assertEqual(kind, plan.registration_intents[0].kind)
            self.assertIn("--label", plan.argv)
            self.assertLess(plan.argv.index("--label"), len(plan.argv) - 1)

    def test_unsupported_create_form_is_unmanaged(self):
        plan = self.adapter.plan_create(("docker", "build", "."), "run-1", "node-1", "chunk", "stop-remove")
        self.assertFalse(plan.managed)
        self.assertEqual("unsupported_docker_create_form", plan.reason)

    def test_compose_inspection_generates_labeled_override_and_intents(self):
        config_argv = ("docker", "compose", "-f", "compose.yml", "config", "--format", "json")
        config = {"services": {"app": {"image": "x"}}, "networks": {"back": {}}, "volumes": {"data": {}}}
        runner = FakeRunner((CommandResult(config_argv, 0, json.dumps(config), ""),))
        plan = DockerAdapter(runner, now=lambda: NOW).plan_compose(
            ("docker", "compose", "-f", "compose.yml", "up", "-d"), "run-1", "node-1", "run", "retain"
        )
        self.assertTrue(plan.managed)
        self.assertEqual("depot-run-1-node-1", plan.project_name)
        override = json.loads(plan.compose_override_content)
        self.assertEqual("true", override["services"]["app"]["labels"]["com.designmachines.depot.managed"])
        self.assertEqual({ResourceKind.CONTAINER, ResourceKind.NETWORK, ResourceKind.VOLUME}, {x.kind for x in plan.registration_intents})

    def test_compose_external_resource_is_rejected_as_unmanaged(self):
        argv = ("docker", "compose", "config", "--format", "json")
        runner = FakeRunner((CommandResult(argv, 0, json.dumps({"services": {"app": {}}, "volumes": {"data": {"external": True}}}), ""),))
        plan = DockerAdapter(runner, now=lambda: NOW).plan_compose(
            ("docker", "compose", "up"), "run-1", "node-1", "run", "retain"
        )
        self.assertFalse(plan.managed)
        self.assertEqual("compose_external_resource", plan.reason)


class DockerCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.registry = ResourceRegistry(Path(self.directory.name) / "resources.jsonl")

    def tearDown(self):
        self.directory.cleanup()

    def test_record_creation_requires_complete_matching_labels(self):
        adapter = DockerAdapter(FakeRunner(), now=lambda: NOW)
        plan = adapter.plan_create(("docker", "run", "alpine"), "run-1", "node-1", "chunk", "stop-remove")
        after = DockerInventory((DockerResource("ctr-1", ResourceKind.CONTAINER, owned_labels(), NOW, running=False),))
        receipt = adapter.record_creation(self.registry, DockerInventory(()), after, plan)
        self.assertEqual(CleanupDisposition.REMOVED, receipt.dispositions[0].disposition)
        self.assertEqual("creation_registered", receipt.dispositions[0].reason)
        self.assertEqual("ctr-1", self.registry.resources_for("run-1")[0].resource_id)

    def test_current_chunk_cleanup_requires_registry_and_label_agreement(self):
        adapter = DockerAdapter(FakeRunner(), now=lambda: NOW)
        plan = adapter.plan_create(("docker", "run", "alpine"), "run-1", "node-1", "chunk", "stop-remove")
        inventory = DockerInventory((DockerResource("ctr-1", ResourceKind.CONTAINER, owned_labels(), NOW, running=True),))
        adapter.record_creation(self.registry, DockerInventory(()), inventory, plan)
        cleanup = adapter.plan_chunk_cleanup(self.registry, inventory, "run-1", "node-1")
        self.assertEqual(("docker", "stop", "--time", "10", "ctr-1"), cleanup.actions[0].argv)
        self.assertEqual(("docker", "rm", "ctr-1"), cleanup.actions[1].argv)
        self.assertFalse(any("prune" in action.argv for action in cleanup.actions))

        foreign = DockerInventory((DockerResource("ctr-1", ResourceKind.CONTAINER, {**owned_labels(), "com.designmachines.depot.node-id": "other"}, NOW),))
        blocked = adapter.plan_chunk_cleanup(self.registry, foreign, "run-1", "node-1")
        self.assertEqual(CleanupDisposition.FOREIGN, blocked.dispositions[0].disposition)
        self.assertEqual((), blocked.actions)

    def test_run_resource_waits_for_last_dependency(self):
        labels = owned_labels(lifecycle="run", cleanup_policy="stop-remove")
        resource = DockerResource("vol-1", ResourceKind.VOLUME, labels, NOW)
        adapter = DockerAdapter(FakeRunner(), now=lambda: NOW)
        plan = adapter.plan_create(("docker", "volume", "create", "vol"), "run-1", "node-1", "run", "stop-remove", dependent_node_ids=("node-2",))
        adapter.record_creation(self.registry, DockerInventory(()), DockerInventory((resource,)), plan)
        retained = adapter.plan_reconcile_run(self.registry, DockerInventory((resource,)), "run-1", active_node_ids=("node-2",))
        self.assertEqual(CleanupDisposition.RETAINED_FOR_DEPENDENCY, retained.dispositions[0].disposition)
        removed = adapter.plan_reconcile_run(self.registry, DockerInventory((resource,)), "run-1", active_node_ids=())
        self.assertEqual(("docker", "volume", "rm", "vol-1"), removed.actions[0].argv)

    def test_stale_sweep_is_strictly_older_never_stops_and_requires_complete_labels(self):
        adapter = DockerAdapter(FakeRunner(), now=lambda: NOW)
        boundary = DockerResource("boundary", ResourceKind.CONTAINER, owned_labels(created_at=NOW - timedelta(hours=24)), NOW - timedelta(hours=24), running=False)
        stale = DockerResource("stale", ResourceKind.CONTAINER, owned_labels(created_at=NOW - timedelta(hours=24, seconds=1)), NOW - timedelta(hours=24, seconds=1), running=False)
        incomplete = DockerResource("incomplete", ResourceKind.VOLUME, {"com.designmachines.depot.managed": "true"}, NOW - timedelta(days=2))
        cleanup = adapter.plan_stale_sweep(DockerInventory((boundary, stale, incomplete)), timedelta(hours=24), active_run_ids=())
        self.assertEqual(("docker", "rm", "stale"), cleanup.actions[0].argv)
        self.assertFalse(any(action.argv[:2] == ("docker", "stop") for action in cleanup.actions))
        dispositions = {item.resource_id: item for item in cleanup.dispositions}
        self.assertEqual(CleanupDisposition.RETAINED_FOR_DEPENDENCY, dispositions["boundary"].disposition)
        self.assertEqual(CleanupDisposition.FOREIGN, dispositions["incomplete"].disposition)

    def test_in_use_network_and_volume_are_retained(self):
        adapter = DockerAdapter(FakeRunner(), now=lambda: NOW)
        resources = (
            DockerResource("net-1", ResourceKind.NETWORK, owned_labels(), NOW, in_use=True),
            DockerResource("vol-1", ResourceKind.VOLUME, owned_labels(), NOW, in_use=True),
        )
        cleanup = adapter.plan_stale_sweep(DockerInventory(resources), timedelta(0), active_run_ids=())
        self.assertEqual((), cleanup.actions)
        self.assertTrue(all(x.disposition is CleanupDisposition.RETAINED_FOR_DEPENDENCY for x in cleanup.dispositions))

    def test_record_results_is_pure_and_idempotently_marks_missing(self):
        runner = FakeRunner()
        adapter = DockerAdapter(runner, now=lambda: NOW)
        created = NOW - timedelta(seconds=1)
        inventory = DockerInventory((DockerResource("ctr-1", ResourceKind.CONTAINER, owned_labels(created_at=created), created),))
        plan = adapter.plan_stale_sweep(inventory, timedelta(0), active_run_ids=())
        receipt = adapter.record_results(plan, (), DockerInventory(()))
        self.assertEqual([], runner.calls)
        self.assertEqual(CleanupDisposition.MISSING, receipt.dispositions[0].disposition)


if __name__ == "__main__":
    unittest.main()
