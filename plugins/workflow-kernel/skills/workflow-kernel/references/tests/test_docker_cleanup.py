import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests import schema_matches
from workflow_kernel.adapters.docker import (
    DockerAdapter,
    DockerCreationPlan,
    DockerInventory,
    DockerResource,
    LeaseProof,
)
from workflow_kernel.resources import CleanupDisposition, CommandResult, ResourceKind, ResourceRecord, ResourceRegistry
from workflow_kernel.schema import InvalidSchemaError


NOW = datetime(2026, 7, 15, 1, 2, 3, tzinfo=timezone.utc)


class FakeRunner:
    def __init__(self, results=()):
        self.results = {result.argv: result for result in results}
        self.calls = []

    def run(self, argv):
        argv = tuple(argv)
        self.calls.append(argv)
        return self.results.get(argv, CommandResult(argv, 0, "", ""))


class FakeLeaseReader:
    def __init__(self, proofs=None):
        self.proofs = proofs or {}
        self.calls = []

    def read(self, run_id):
        self.calls.append(run_id)
        value = self.proofs.get(run_id)
        if isinstance(value, Exception):
            raise value
        return value


def owned_labels(*, run_id="run-1", lifecycle="chunk", created_at=NOW, cleanup_policy="stop-remove"):
    return {
        "com.designmachines.depot.managed": "true",
        "com.designmachines.depot.run-id": run_id,
        "com.designmachines.depot.node-id": "node-1",
        "com.designmachines.depot.created-at": created_at.isoformat().replace("+00:00", "Z"),
        "com.designmachines.depot.lifecycle": lifecycle,
        "com.designmachines.depot.cleanup-policy": cleanup_policy,
    }


def resource(resource_id="ctr-1", *, kind=ResourceKind.CONTAINER, labels=None, created_at=NOW, **kwargs):
    return DockerResource(resource_id, kind, labels or owned_labels(created_at=created_at), created_at, **kwargs)


def inactive_lease(run_id="run-1"):
    return LeaseProof(run_id, active=False, readable=True, observed_at=NOW)


def exact_absent(kind=ResourceKind.CONTAINER, resource_id="ctr-1"):
    key = ((kind, resource_id),)
    return DockerInventory((), key, key, "registered_exact")


class DockerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.registry = ResourceRegistry(Path(self.directory.name) / "resources.jsonl")
        self.runner = FakeRunner()
        self.leases = FakeLeaseReader({"run-1": inactive_lease()})
        self.adapter = DockerAdapter(self.runner, now=lambda: NOW, lease_reader=self.leases)

    def tearDown(self):
        self.directory.cleanup()

    def register(self, value=None, *, plan=None, result=None):
        value = value or resource()
        plan = plan or self.adapter.plan_create(("docker", "run", "alpine"), "run-1", "node-1", "chunk", "stop-remove")
        result = result or CommandResult(plan.argv, 0, value.resource_id + "\n", "")
        receipt = self.adapter.record_creation(self.registry, plan, result, DockerInventory(()), DockerInventory((value,)))
        return value, receipt

    def test_raw_creation_injects_all_labels_and_truthfully_registers(self):
        for argv, kind in (
            (("docker", "run", "alpine"), ResourceKind.CONTAINER),
            (("docker", "container", "create", "alpine"), ResourceKind.CONTAINER),
            (("docker", "network", "create", "net"), ResourceKind.NETWORK),
            (("docker", "volume", "create", "vol"), ResourceKind.VOLUME),
        ):
            plan = self.adapter.plan_create(argv, "run-1", "node-1", "chunk", "stop-remove")
            self.assertTrue(plan.managed)
            self.assertEqual(6, plan.argv.count("--label"))
            self.assertEqual(kind, plan.registration_intents[0].kind)

        value, receipt = self.register()
        self.assertEqual((value.resource_id,), tuple(item.resource_id for item in receipt.registered))
        self.assertEqual((), receipt.dispositions)
        self.assertTrue(receipt.command_succeeded)

    def test_failed_compose_command_registers_only_correlated_partial_creation(self):
        config_argv = ("docker", "compose", "config", "--format", "json")
        config = {
            "services": {"app": {"image": "app:1", "command": ["serve"]}, "worker": {"image": "worker:1"}},
            "networks": {}, "volumes": {},
        }
        runner = FakeRunner((CommandResult(config_argv, 0, json.dumps(config), ""),))
        adapter = DockerAdapter(runner, now=lambda: NOW, lease_reader=self.leases)
        plan = adapter.plan_compose(("docker", "compose", "up"), "run-1", "node-1", "chunk", "stop-remove")
        materialized = json.loads(plan.compose_override_content)
        self.assertEqual("app:1", materialized["services"]["app"]["image"])
        self.assertEqual(["serve"], materialized["services"]["app"]["command"])
        labels = {**owned_labels(), "com.docker.compose.service": "app"}
        app = resource("app-id", labels=labels, name="depot-run-1-node-1-app-1")
        outcome = adapter.record_creation(
            self.registry, plan, CommandResult(plan.argv, 1, "", "failed"),
            DockerInventory(()), DockerInventory((app,)),
        )
        self.assertFalse(outcome.command_succeeded)
        self.assertEqual(("app-id",), tuple(item.resource_id for item in outcome.registered))
        missing = [item for item in outcome.dispositions if item.disposition is CleanupDisposition.MISSING]
        self.assertTrue(any("worker" in item.resource_id for item in missing))
        self.assertFalse(any(item.disposition is CleanupDisposition.REMOVED for item in outcome.dispositions))

    def test_creation_delta_with_wrong_expected_name_is_foreign(self):
        plan = self.adapter.plan_create(("docker", "network", "create", "expected"), "run-1", "node-1", "chunk", "stop-remove")
        actual = resource("net-id", kind=ResourceKind.NETWORK, name="different", in_use=False, use_known=True)
        outcome = self.adapter.record_creation(
            self.registry, plan, CommandResult(plan.argv, 0, "net-id", ""),
            DockerInventory(()), DockerInventory((actual,)),
        )
        self.assertEqual((), outcome.registered)
        self.assertEqual(CleanupDisposition.FOREIGN, outcome.dispositions[0].disposition)

    def test_raw_creation_correlates_result_id_and_normalizes_container_name(self):
        plan = self.adapter.plan_create(
            ("docker", "container", "create", "--name", "expected", "alpine"),
            "run-1", "node-1", "chunk", "stop-remove",
        )
        actual = resource("abcdef123456", name="/expected")
        accepted = self.adapter.record_creation(
            self.registry, plan, CommandResult(plan.argv, 0, "abcdef1234567890\n", ""),
            DockerInventory(()), DockerInventory((actual,)),
        )
        self.assertEqual(("abcdef123456",), tuple(item.resource_id for item in accepted.registered))

        foreign_registry = ResourceRegistry(Path(self.directory.name) / "wrong-result.jsonl")
        rejected = self.adapter.record_creation(
            foreign_registry, plan, CommandResult(plan.argv, 0, "different-id\n", ""),
            DockerInventory(()), DockerInventory((actual,)),
        )
        self.assertEqual((), rejected.registered)
        self.assertEqual(CleanupDisposition.FOREIGN, rejected.dispositions[0].disposition)

    def test_current_cleanup_requires_kind_id_and_nonempty_exact_label_snapshot(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(self.registry, DockerInventory((value,)), "run-1", "node-1")
        self.assertEqual(("docker", "rm", "ctr-1"), plan.actions[0].argv)

        empty_registry = ResourceRegistry(Path(self.directory.name) / "empty.jsonl")
        empty_registry.register(ResourceRecord(
            "ctr-1", ResourceKind.CONTAINER, "run-1", "node-1", "chunk", "stop-remove", NOW, labels={},
        ))
        denied = self.adapter.plan_chunk_cleanup(empty_registry, DockerInventory((value,)), "run-1", "node-1")
        self.assertEqual((), denied.actions)
        self.assertEqual(CleanupDisposition.FOREIGN, denied.dispositions[0].disposition)

        wrong_kind = DockerInventory((resource("ctr-1", kind=ResourceKind.VOLUME, in_use=False, use_known=True),))
        denied = self.adapter.plan_chunk_cleanup(self.registry, wrong_kind, "run-1", "node-1")
        self.assertEqual((), denied.actions)
        self.assertEqual(CleanupDisposition.BLOCKED, denied.dispositions[0].disposition)

    def test_inspection_failure_with_registry_proof_is_blocked(self):
        value, _ = self.register()
        failed = resource("ctr-1", labels=value.labels, inspect_ok=False)
        plan = self.adapter.plan_chunk_cleanup(self.registry, DockerInventory((failed,)), "run-1", "node-1")
        self.assertEqual((), plan.actions)
        self.assertEqual(CleanupDisposition.BLOCKED, plan.dispositions[0].disposition)
        self.assertEqual("docker_inspect_failed", plan.dispositions[0].reason)

    def test_stale_cleanup_requires_inactive_readable_fresh_lease(self):
        created = NOW - timedelta(hours=25)
        stale = resource("stale", labels=owned_labels(created_at=created), created_at=created)
        for proof in (
            None,
            LeaseProof("run-1", active=False, readable=False, observed_at=NOW),
            LeaseProof("run-1", active=True, readable=True, observed_at=NOW),
            LeaseProof("run-1", active=False, readable=True, observed_at=NOW - timedelta(minutes=2)),
        ):
            adapter = DockerAdapter(FakeRunner(), now=lambda: NOW, lease_reader=FakeLeaseReader({"run-1": proof}))
            plan = adapter.plan_stale_sweep(DockerInventory((stale,)), timedelta(hours=24))
            self.assertEqual((), plan.actions)
        allowed = self.adapter.plan_stale_sweep(DockerInventory((stale,)), timedelta(hours=24))
        self.assertEqual(("docker", "rm", "stale"), allowed.actions[0].argv)

    def test_stale_boundary_label_domains_and_inspected_creation_time_fail_closed(self):
        boundary_time = NOW - timedelta(hours=24)
        boundary = resource("boundary", labels=owned_labels(created_at=boundary_time), created_at=boundary_time)
        mismatch = resource("mismatch", labels=owned_labels(created_at=NOW - timedelta(hours=25)), created_at=NOW)
        invalid = resource("invalid", labels=owned_labels(created_at=NOW - timedelta(hours=25), cleanup_policy="typo"), created_at=NOW - timedelta(hours=25))
        plan = self.adapter.plan_stale_sweep(DockerInventory((boundary, mismatch, invalid)), timedelta(hours=24))
        self.assertEqual((), plan.actions)
        dispositions = {item.resource_id: item for item in plan.dispositions}
        self.assertEqual(CleanupDisposition.RETAINED_FOR_DEPENDENCY, dispositions["boundary"].disposition)
        self.assertEqual(CleanupDisposition.FOREIGN, dispositions["mismatch"].disposition)
        self.assertEqual(CleanupDisposition.FOREIGN, dispositions["invalid"].disposition)

    def test_stale_sweep_requires_both_label_and_inspected_age_to_exceed_ttl(self):
        label_created = NOW - timedelta(hours=24, seconds=1)
        inspected_created = NOW - timedelta(hours=23, minutes=59)
        candidate = resource(
            "ttl-straddle", labels=owned_labels(created_at=label_created),
            created_at=inspected_created,
        )
        plan = self.adapter.plan_stale_sweep(DockerInventory((candidate,)), timedelta(hours=24))
        self.assertEqual((), plan.actions)
        self.assertEqual("ttl_not_expired", plan.dispositions[0].reason)

    def test_lease_proof_rejects_truthy_bools_and_noncanonical_identity_timestamp(self):
        invalid = (
            dict(run_id="run-1", active=0, readable=True, observed_at=NOW),
            dict(run_id="run-1", active=False, readable=1, observed_at=NOW),
            dict(run_id=" run-1", active=False, readable=True, observed_at=NOW),
            dict(run_id="run-1", active=False, readable=True, observed_at=NOW.replace(tzinfo=None)),
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(InvalidSchemaError):
                LeaseProof(**values)

    def test_docker_models_reject_noncanonical_booleans_timestamps_and_inventory(self):
        with self.assertRaises(InvalidSchemaError):
            DockerResource(
                "ctr-1", ResourceKind.CONTAINER, owned_labels(),
                NOW.replace(tzinfo=None),
            )
        with self.assertRaises(InvalidSchemaError):
            DockerResource("ctr-1", ResourceKind.CONTAINER, owned_labels(), NOW, running=1)
        duplicate = resource()
        with self.assertRaises(InvalidSchemaError):
            DockerInventory((duplicate, duplicate))
        with self.assertRaises(InvalidSchemaError):
            DockerCreationPlan(("docker",), {}, "anything", (), managed=1)

    def test_stale_sweep_rejects_nonexact_lease_proof_type(self):
        class DerivedLeaseProof(LeaseProof):
            pass

        created = NOW - timedelta(hours=25)
        stale = resource("stale", labels=owned_labels(created_at=created), created_at=created)
        derived = object.__new__(DerivedLeaseProof)
        for name, value in inactive_lease().__dict__.items():
            object.__setattr__(derived, name, value)
        adapter = DockerAdapter(
            FakeRunner(), now=lambda: NOW,
            lease_reader=FakeLeaseReader({"run-1": derived}),
        )
        plan = adapter.plan_stale_sweep(DockerInventory((stale,)), timedelta(hours=24))
        self.assertEqual((), plan.actions)
        self.assertEqual("lease_proof_unreadable", plan.dispositions[0].reason)

        mutated = LeaseProof("run-1", False, True, NOW)
        object.__setattr__(mutated, "active", 0)
        adapter = DockerAdapter(
            FakeRunner(), now=lambda: NOW,
            lease_reader=FakeLeaseReader({"run-1": mutated}),
        )
        plan = adapter.plan_stale_sweep(DockerInventory((stale,)), timedelta(hours=24))
        self.assertEqual((), plan.actions)
        self.assertEqual("lease_proof_unreadable", plan.dispositions[0].reason)

    def test_volume_inventory_queries_container_mounts_and_unknown_use_blocks(self):
        volume_list = ("docker", "volume", "ls", "--filter", "label=com.designmachines.depot.managed=true", "--format", "{{.Name}}")
        inspect = ("docker", "volume", "inspect", "vol-1")
        use = ("docker", "ps", "-a", "--filter", "volume=vol-1", "--format", "{{.ID}}")
        inspected = [{"Name": "vol-1", "Labels": owned_labels(), "CreatedAt": NOW.isoformat()}]
        runner = FakeRunner((
            CommandResult(volume_list, 0, "vol-1\n", ""),
            CommandResult(inspect, 0, json.dumps(inspected), ""),
            CommandResult(use, 0, "container-1\n", ""),
        ))
        inventory = DockerAdapter(runner, now=lambda: NOW, lease_reader=self.leases).inventory()
        volume = next(item for item in inventory.resources if item.kind is ResourceKind.VOLUME)
        self.assertTrue(volume.use_known)
        self.assertTrue(volume.in_use)
        self.assertIn(use, runner.calls)

        unknown = resource("vol-2", kind=ResourceKind.VOLUME, in_use=False, use_known=False)
        registry = ResourceRegistry(Path(self.directory.name) / "unknown.jsonl")
        registry.register(ResourceRecord("vol-2", ResourceKind.VOLUME, "run-1", "node-1", "chunk", "stop-remove", NOW, labels=owned_labels()))
        blocked = self.adapter.plan_chunk_cleanup(registry, DockerInventory((unknown,)), "run-1", "node-1")
        self.assertEqual((), blocked.actions)
        self.assertEqual("resource_use_unknown", blocked.dispositions[0].reason)

    def test_result_recording_requires_success_and_preserves_removed(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(self.registry, DockerInventory((value,)), "run-1", "node-1")
        action = plan.actions[0]
        absent_without_result = self.adapter.record_results(plan, (), DockerInventory(()))
        self.assertEqual(CleanupDisposition.BLOCKED, absent_without_result.dispositions[0].disposition)

        receipt = self.adapter.record_results(
            plan, (CommandResult(action.argv, 0, "", ""),), exact_absent()
        )
        removed = receipt.dispositions[0]
        self.assertEqual(CleanupDisposition.REMOVED, removed.disposition)
        self.registry.record_receipt(receipt)
        self.assertEqual(CleanupDisposition.REMOVED, self.registry.disposition_for(ResourceKind.CONTAINER, "ctr-1").disposition)

        rerun = self.adapter.plan_chunk_cleanup(self.registry, DockerInventory(()), "run-1", "node-1")
        self.assertEqual((), rerun.actions)

    def test_missing_is_emitted_only_when_absent_before_plan(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry,
            exact_absent(),
            "run-1", "node-1",
        )
        self.assertEqual(CleanupDisposition.MISSING, plan.dispositions[0].disposition)
        self.assertEqual((), plan.actions)

    def test_registered_inventory_inspects_exact_ids_and_proves_absence(self):
        value, _ = self.register()
        inspect = ("docker", "container", "inspect", value.resource_id)
        runner = FakeRunner((CommandResult(inspect, 1, "", "Error: No such object: ctr-1"),))
        adapter = DockerAdapter(runner, now=lambda: NOW, lease_reader=self.leases)
        inventory = adapter.inventory_registered(tuple(self.registry.resources_for("run-1")))
        self.assertEqual((inspect,), tuple(runner.calls))
        self.assertEqual(((ResourceKind.CONTAINER, "ctr-1"),), inventory.absent)
        plan = adapter.plan_chunk_cleanup(self.registry, inventory, "run-1", "node-1")
        self.assertEqual(CleanupDisposition.MISSING, plan.dispositions[0].disposition)

    def test_malformed_network_inspect_containers_type_blocks_cleanup(self):
        list_argv = ("docker", "network", "ls", "--filter", "label=com.designmachines.depot.managed=true", "--format", "{{.ID}}")
        inspect = ("docker", "network", "inspect", "net-1")
        payload = [{
            "Name": "net-1", "Labels": owned_labels(), "Created": NOW.isoformat(),
            "State": {}, "Containers": ["attached"],
        }]
        runner = FakeRunner((
            CommandResult(("docker", "ps", "-a", "--filter", "label=com.designmachines.depot.managed=true", "--format", "{{.ID}}"), 0, "", ""),
            CommandResult(list_argv, 0, "net-1\n", ""),
            CommandResult(inspect, 0, json.dumps(payload), ""),
            CommandResult(("docker", "volume", "ls", "--filter", "label=com.designmachines.depot.managed=true", "--format", "{{.Name}}"), 0, "", ""),
        ))
        inventory = DockerAdapter(runner, now=lambda: NOW).inventory()
        self.assertFalse(inventory.resources[0].inspect_ok)

    def test_action_revalidation_and_result_models_fail_closed(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(self.registry, DockerInventory((value,)), "run-1", "node-1")
        changed = resource("ctr-1", labels=value.labels, in_use=True)
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(plan.actions[0], changed)
        with self.assertRaises(InvalidSchemaError):
            self.adapter.record_results(plan, [CommandResult(plan.actions[0].argv, 0, "", "")], exact_absent())
        mutated = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        object.__setattr__(mutated, "actions", (object(),))
        with self.assertRaises(InvalidSchemaError):
            self.adapter.record_results(mutated, (), exact_absent())
        schema = json.loads((Path(__file__).parents[1] / "cleanup-plan-schema.json").read_text())
        self.assertTrue(schema_matches(plan.to_dict(), schema))


if __name__ == "__main__":
    unittest.main()
