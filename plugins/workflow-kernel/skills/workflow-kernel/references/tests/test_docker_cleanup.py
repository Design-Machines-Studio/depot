import json
import os
import tempfile
import unittest
import workflow_kernel.resources as resource_models
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from tests import schema_matches
from workflow_kernel.adapters.docker import (
    DockerAdapter,
    DockerCreationPlan,
    DockerInventory,
    DockerResource,
    IncompleteNodeProof,
    LeaseProof,
)
from workflow_kernel.resources import (
    CleanupDisposition, CleanupReceipt, CleanupStepIdentity, CommandResult,
    ResourceDisposition,
    GuardedCommandResult, ResourceKind, ResourceRecord, ResourceRegistry,
    cleanup_proof_digest, cleanup_result_id, reseal_cleanup_action,
)
from workflow_kernel.schema import InvalidSchemaError, NodeStatus


NOW = datetime(2026, 7, 15, 1, 2, 3, tzinfo=timezone.utc)


def legacy_recomputed_authority_id(
    *, result, kind, resource_id, run_id, node_id, action_digest,
    state_generation, issued_at, expires_at,
):
    def timestamp(value):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return cleanup_proof_digest({
        "action_digest": action_digest,
        "owner": {"run_id": run_id, "node_id": node_id},
        "kind": kind.value, "resource_id": resource_id,
        "state_generation": state_generation,
        "result_id": cleanup_result_id(result.argv, result.exit_code),
        "issued_at": timestamp(issued_at),
        "expires_at": timestamp(expires_at),
    })


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
    inspect = (
        ("docker", "container", "inspect", resource_id)
        if kind is ResourceKind.CONTAINER else
        ("docker", kind.value, "inspect", resource_id)
    )
    return DockerInventory(
        (), key, key, "registered_exact",
        (CommandResult(inspect, 1, "", "Error: No such " + kind.value + ": " + resource_id),),
    )


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

    def test_network_and_volume_creation_parse_interspersed_option_values(self):
        cases = (
            (
                ("docker", "network", "create", "owned-net", "--driver", "bridge"),
                "owned-net",
            ),
            (
                ("docker", "volume", "create", "owned-vol", "--driver", "local"),
                "owned-vol",
            ),
            (
                ("docker", "network", "create", "--driver=bridge", "owned-net"),
                "owned-net",
            ),
            (
                ("docker", "volume", "create", "-dlocal", "owned-vol"),
                "owned-vol",
            ),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                plan = self.adapter.plan_create(
                    argv, "run-1", "node-1", "chunk", "stop-remove",
                )
                self.assertTrue(plan.managed)
                self.assertEqual(expected, plan.registration_intents[0].expected_name)

        ambiguous = self.adapter.plan_create(
            ("docker", "network", "create", "owned-net", "--unknown", "value"),
            "run-1", "node-1", "chunk", "stop-remove",
        )
        self.assertFalse(ambiguous.managed)
        self.assertEqual("ambiguous_docker_create_form", ambiguous.reason)

    def test_failed_compose_command_registers_only_correlated_partial_creation(self):
        config_argv = ("docker", "compose", "-f", "compose.yml", "config", "--format", "json")
        config = {
            "services": {"app": {"image": "app:1", "command": ["serve"]}, "worker": {"image": "worker:1"}},
            "networks": {}, "volumes": {},
        }
        runner = FakeRunner((CommandResult(config_argv, 0, json.dumps(config), ""),))
        adapter = DockerAdapter(runner, now=lambda: NOW, lease_reader=self.leases)
        plan = adapter.plan_compose(("docker", "compose", "-f", "compose.yml", "up"), "run-1", "node-1", "chunk", "stop-remove")
        materialized = json.loads(plan.compose_override_content)
        self.assertEqual({"labels"}, set(materialized["services"]["app"]))
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

    def test_stale_sweep_records_malformed_ownership_identifiers_without_aborting(self):
        created = NOW - timedelta(hours=25)
        variants = []
        for resource_id, changes in (
            ("incomplete", {"com.designmachines.depot.run-id": None}),
            ("whitespace", {"com.designmachines.depot.run-id": " run-1"}),
            ("overlong", {"com.designmachines.depot.node-id": "n" * 257}),
            ("bad-domain", {"com.designmachines.depot.lifecycle": "temporary"}),
        ):
            labels = owned_labels(created_at=created)
            for key, value in changes.items():
                if value is None:
                    labels.pop(key)
                else:
                    labels[key] = value
            variants.append(resource(resource_id, labels=labels, created_at=created))
        try:
            plan = self.adapter.plan_stale_sweep(
                DockerInventory(tuple(variants)), timedelta(hours=24),
            )
        except InvalidSchemaError:
            self.fail("malformed ownership labels must not abort a stale sweep")
        self.assertEqual((), plan.actions)
        self.assertEqual(
            {value.resource_id for value in variants},
            {value.resource_id for value in plan.dispositions},
        )
        self.assertTrue(all(
            value.disposition is CleanupDisposition.FOREIGN
            for value in plan.dispositions
        ))

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

        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        receipt = self.registry.record_guarded_results(
            self.adapter, plan, (guarded,), DockerInventory((value,)), exact_absent(),
        )
        removed = receipt.dispositions[0]
        self.assertEqual(CleanupDisposition.REMOVED, removed.disposition)
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
            self.adapter.revalidate_action(
                plan.actions[0], changed, registry=self.registry,
            )
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

    def test_revalidation_binds_argv_and_accepts_expected_stop_transition(self):
        value, _ = self.register(resource(running=True))
        plan = self.adapter.plan_chunk_cleanup(self.registry, DockerInventory((value,)), "run-1", "node-1")
        forged = replace(plan.actions[1], argv=("docker", "rm", "foreign-container"))
        stopped = replace(value, running=False)
        predecessor = CommandResult(plan.actions[0].argv, 0, "", "")
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                forged, stopped, predecessor_result=predecessor,
                registry=self.registry,
            )
        self.adapter.revalidate_action(
            plan.actions[1], stopped, predecessor_result=predecessor,
            action_index=1, registry=self.registry,
        )

    def test_revalidation_requires_same_fresh_terminal_dependency_snapshot(self):
        labels = owned_labels(lifecycle="run", cleanup_policy="remove-when-stopped")
        value = resource(labels=labels)
        record = ResourceRecord(
            value.resource_id, value.kind, "run-1", "node-1", "run",
            "remove-when-stopped", NOW, ("consumer",), labels,
        )
        registry = ResourceRegistry(Path(self.directory.name) / "dependent.jsonl")
        registry.register(record)
        terminal = IncompleteNodeProof(
            "run-1", (("consumer", NodeStatus.SUCCEEDED),), True, NOW,
        )
        plan = self.adapter.plan_reconcile_run(
            registry, DockerInventory((value,)), "run-1",
            incomplete_node_proof=terminal, terminal=True,
        )
        self.assertEqual(1, len(plan.actions))
        self.adapter.revalidate_action(
            plan.actions[0], value, registry=registry,
            incomplete_node_proof=terminal,
        )
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                plan.actions[0], value, registry=registry,
                incomplete_node_proof=IncompleteNodeProof(
                    "run-1", (("consumer", NodeStatus.PENDING),), True, NOW,
                ),
            )
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                plan.actions[0], value, registry=registry,
                incomplete_node_proof=IncompleteNodeProof(
                    "run-1", (("consumer", NodeStatus.SUCCEEDED),), True,
                    NOW - timedelta(minutes=2),
                ),
            )

    def test_revalidation_derives_dependency_proof_from_fresh_registry_record(self):
        labels = owned_labels(lifecycle="run", cleanup_policy="remove-when-stopped")
        value = resource(labels=labels)
        authoritative = ResourceRegistry(Path(self.directory.name) / "authoritative.jsonl")
        authoritative.register(ResourceRecord(
            value.resource_id, value.kind, "run-1", "node-1", "run",
            "remove-when-stopped", NOW, ("consumer",), labels,
        ))
        shadow = ResourceRegistry(Path(self.directory.name) / "shadow.jsonl")
        shadow.register(ResourceRecord(
            value.resource_id, value.kind, "run-1", "node-1", "run",
            "remove-when-stopped", NOW, (), labels,
        ))
        shadow_action = self.adapter.plan_reconcile_run(
            shadow, DockerInventory((value,)), "run-1", terminal=True,
        ).actions[0]

        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                shadow_action, value, registry=authoritative,
            )

        proof = IncompleteNodeProof(
            "run-1", (("consumer", NodeStatus.SUCCEEDED),), True, NOW,
        )
        authoritative_action = self.adapter.plan_reconcile_run(
            authoritative, DockerInventory((value,)), "run-1",
            incomplete_node_proof=proof, terminal=True,
        ).actions[0]
        self.adapter.revalidate_action(
            authoritative_action, value, registry=authoritative,
            incomplete_node_proof=proof,
        )

    def test_stale_orphan_revalidation_requires_explicit_orphan_mode(self):
        created = NOW - timedelta(hours=25)
        orphan = resource(
            "orphan", labels=owned_labels(created_at=created), created_at=created,
        )
        plan = self.adapter.plan_stale_sweep(
            DockerInventory((orphan,)), timedelta(hours=24),
        )
        empty_registry = ResourceRegistry(
            Path(self.directory.name) / "orphan-registry.jsonl",
        )
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                plan.actions[0], orphan, lease_proof=inactive_lease(),
                registry=empty_registry,
            )
        self.adapter.revalidate_action(
            plan.actions[0], orphan, lease_proof=inactive_lease(),
            registry=empty_registry, orphan_mode=True,
        )

        registered = ResourceRegistry(
            Path(self.directory.name) / "not-an-orphan.jsonl",
        )
        registered.register(ResourceRecord(
            orphan.resource_id, orphan.kind, "run-1", "node-1", "chunk",
            "stop-remove", created, ("consumer",), orphan.labels,
        ))
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                plan.actions[0], orphan, lease_proof=inactive_lease(),
                registry=registered, orphan_mode=True,
            )

        registered_elsewhere = ResourceRegistry(
            Path(self.directory.name) / "registered-elsewhere.jsonl",
        )
        other_labels = owned_labels(run_id="run-2")
        registered_elsewhere.register(ResourceRecord(
            orphan.resource_id, orphan.kind, "run-2", "node-1", "chunk",
            "stop-remove", NOW, labels=other_labels,
        ))
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                plan.actions[0], orphan, lease_proof=inactive_lease(),
                registry=registered_elsewhere, orphan_mode=True,
            )

    def test_dependent_cleanup_without_complete_node_proof_is_blocked(self):
        labels = owned_labels()
        value = resource(labels=labels)
        registry = ResourceRegistry(Path(self.directory.name) / "proof-missing.jsonl")
        registry.register(ResourceRecord(
            value.resource_id, value.kind, "run-1", "node-1", "chunk",
            "stop-remove", NOW, ("consumer",), labels,
        ))
        plan = self.adapter.plan_chunk_cleanup(
            registry, DockerInventory((value,)), "run-1", "node-1",
        )
        self.assertEqual((), plan.actions)
        self.assertEqual("incomplete_node_proof_missing", plan.dispositions[0].reason)
        incomplete = self.adapter.plan_chunk_cleanup(
            registry, DockerInventory((value,)), "run-1", "node-1",
            incomplete_node_proof=IncompleteNodeProof(
                "run-1", (("other", NodeStatus.SUCCEEDED),), True, NOW,
            ),
        )
        self.assertEqual((), incomplete.actions)
        self.assertEqual("dependent_node_status_missing", incomplete.dispositions[0].reason)
        with self.assertRaises(InvalidSchemaError):
            self.adapter.plan_chunk_cleanup(
                registry, DockerInventory((value,)), "run-1", "node-1",
                incomplete_node_proof=IncompleteNodeProof(
                    "run-1", (("consumer", NodeStatus.SUCCEEDED),), True,
                    NOW - timedelta(minutes=2),
                ),
            )

    def test_compose_preserves_base_files_but_override_contains_labels_only(self):
        config_argv = ("docker", "compose", "-f", "compose.yml", "config", "--format", "json")
        secret = "super-secret-password"
        config = {
            "services": {"app": {"image": "app:1", "environment": {"PASSWORD": secret}}},
            "networks": {}, "volumes": {},
        }
        runner = FakeRunner((CommandResult(config_argv, 0, json.dumps(config), ""),))
        adapter = DockerAdapter(runner, now=lambda: NOW)
        plan = adapter.plan_compose(
            ("docker", "compose", "-f", "compose.yml", "up"),
            "run-1", "node-1", "chunk", "stop-remove",
        )
        self.assertTrue(plan.managed)
        self.assertEqual("compose.yml", plan.argv[plan.argv.index("-f") + 1])
        self.assertNotIn(secret, plan.compose_override_content)
        override = json.loads(plan.compose_override_content)
        self.assertEqual({"labels"}, set(override["services"]["app"]))

    def test_compose_requires_base_file_and_rejects_caller_project_name(self):
        for argv, reason in (
            (("docker", "compose", "up"), "compose_file_required"),
            (("docker", "compose", "-f", "compose.yml", "-p", "foreign", "up"), "caller_project_name_forbidden"),
            (("docker", "compose", "-f", "compose.yml", "-p=foreign", "up"), "caller_project_name_forbidden"),
        ):
            plan = self.adapter.plan_compose(argv, "run-1", "node-1", "chunk", "stop-remove")
            self.assertFalse(plan.managed)
            self.assertEqual(reason, plan.reason)

    def test_compose_short_file_equals_is_an_explicit_base_file(self):
        config_argv = ("docker", "compose", "-f=compose.yml", "config", "--format", "json")
        config = {"services": {"app": {"image": "app:1"}}, "networks": {}, "volumes": {}}
        adapter = DockerAdapter(
            FakeRunner((CommandResult(config_argv, 0, json.dumps(config), ""),)),
            now=lambda: NOW,
        )

        plan = adapter.plan_compose(
            ("docker", "compose", "-f=compose.yml", "up"),
            "run-1", "node-1", "chunk", "stop-remove",
        )

        self.assertTrue(plan.managed)
        self.assertEqual((config_argv,), tuple(adapter.runner.calls))
        self.assertEqual("depot-run-1-node-1", plan.environment["COMPOSE_PROJECT_NAME"])
        self.assertIn("-f=compose.yml", plan.argv)

    def test_compose_attached_project_shorthand_cannot_override_kernel_identity(self):
        plan = self.adapter.plan_compose(
            ("docker", "compose", "-f", "compose.yml", "-pforeign", "up"),
            "run-1", "node-1", "chunk", "stop-remove",
        )
        self.assertFalse(plan.managed)
        self.assertEqual("caller_project_name_forbidden", plan.reason)

    def test_compose_attached_file_shorthand_is_an_explicit_base_file(self):
        config_argv = (
            "docker", "compose", "-fcompose.yml", "config", "--format", "json",
        )
        config = {
            "services": {"app": {"image": "app:1"}},
            "networks": {}, "volumes": {},
        }
        adapter = DockerAdapter(
            FakeRunner((CommandResult(config_argv, 0, json.dumps(config), ""),)),
            now=lambda: NOW,
        )
        plan = adapter.plan_compose(
            ("docker", "compose", "-fcompose.yml", "up"),
            "run-1", "node-1", "chunk", "stop-remove",
        )
        self.assertTrue(plan.managed)
        self.assertIn("-fcompose.yml", plan.argv)
        self.assertEqual((config_argv,), tuple(adapter.runner.calls))

    def test_remove_revalidation_requires_immediately_preceding_stop_index(self):
        value, _ = self.register(resource(running=True))
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        stopped = replace(value, running=False)
        predecessor = CommandResult(plan.actions[0].argv, 0, "", "")
        for dependency, action_index in ((None, 1), (0, 2)):
            forged = reseal_cleanup_action(
                plan.actions[1], requires_success_of=dependency,
            )
            with self.subTest(dependency=dependency, action_index=action_index), \
                    self.assertRaises(InvalidSchemaError):
                self.adapter.revalidate_action(
                    forged, stopped, predecessor_result=predecessor,
                    action_index=action_index, registry=self.registry,
                )

    def test_result_recording_rejects_reversed_dependency_trace(self):
        value, _ = self.register(resource(running=True))
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        first = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        second = self.registry.execute_guarded_action(
            self.adapter, plan, 1, replace(value, running=False),
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
            predecessor_result=first.result,
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (second, first),
                DockerInventory((value,)), exact_absent(),
            )

    def test_result_recording_rejects_trace_that_starts_after_action_zero(self):
        first, _ = self.register(resource("ctr-a"))
        second = resource("ctr-b")
        self.registry.register(ResourceRecord(
            second.resource_id, second.kind, "run-1", "node-1", "chunk",
            "stop-remove", NOW, labels=second.labels,
        ))
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((first, second)), "run-1", "node-1",
        )
        queried = tuple((value.kind, value.resource_id) for value in (first, second))
        after = DockerInventory(
            (), queried, queried, "registered_exact",
            tuple(CommandResult(
                ("docker", "container", "inspect", value.resource_id),
                1, "", "Error: No such container: " + value.resource_id,
            ) for value in (first, second)),
        )

        with self.assertRaises(InvalidSchemaError):
            self.adapter.record_results(
                plan, (CommandResult(plan.actions[1].argv, 0, "", ""),), after,
            )

    def test_transport_no_such_is_not_authoritative_absence(self):
        value, _ = self.register()
        inspect = ("docker", "container", "inspect", value.resource_id)
        runner = FakeRunner((CommandResult(
            inspect, 1, "", "Cannot connect: dial unix /var/run/docker.sock: no such file or directory",
        ),))
        adapter = DockerAdapter(runner, now=lambda: NOW)
        inventory = adapter.inventory_registered(tuple(self.registry.resources_for("run-1")))
        self.assertEqual((), inventory.absent)
        self.assertFalse(inventory.resources[0].inspect_ok)

    def test_caller_claimed_absence_and_mutated_receipt_cannot_retire(self):
        value, _ = self.register()
        key = ((ResourceKind.CONTAINER, value.resource_id),)
        claimed = DockerInventory((), key, key, "registered_exact")
        plan = self.adapter.plan_chunk_cleanup(self.registry, claimed, "run-1", "node-1")
        self.assertEqual(CleanupDisposition.BLOCKED, plan.dispositions[0].disposition)
        forged = CleanupReceipt(
            plan.scope, plan.before, (),
            (ResourceDisposition(
                value.resource_id, value.kind, "run-1", "node-1", "chunk",
                CleanupDisposition.REMOVED, "remove_exact_id", "forged",
                command=("docker", "rm", value.resource_id),
            ),),
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_receipt(forged)

    def test_registry_record_results_without_authority_cannot_retire(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(self.registry, DockerInventory((value,)), "run-1", "node-1")
        action = plan.actions[0]
        inspect = ("docker", "container", "inspect", value.resource_id)
        after = DockerInventory(
            (), ((ResourceKind.CONTAINER, value.resource_id),),
            ((ResourceKind.CONTAINER, value.resource_id),), "registered_exact",
            evidence=(CommandResult(inspect, 1, "", "Error: No such container: ctr-1"),),
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_results(
                self.adapter, plan, (CommandResult(action.argv, 0, "", ""),),
                DockerInventory((value,)), after,
            )
        self.assertEqual((value.resource_id,), tuple(
            item.resource_id for item in self.registry.resources_for("run-1", "node-1")
        ))
        frame = json.loads(self.registry.path.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual("registered", frame["event"])

    def test_guarded_recording_rejects_terminal_state_without_action_authority(self):
        value, _ = self.register()
        absent = exact_absent()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, absent, "run-1", "node-1",
        )
        self.assertEqual(CleanupDisposition.MISSING, plan.dispositions[0].disposition)

        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (), absent, absent,
            )
        self.assertEqual((value.resource_id,), tuple(
            item.resource_id for item in self.registry.resources_for("run-1", "node-1")
        ))

    def test_guarded_absence_observation_retires_missing_once(self):
        value, _ = self.register()
        absent = exact_absent()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, absent, "run-1", "node-1",
        )
        self.assertTrue(hasattr(self.registry, "observe_guarded_absence"))
        competing = ResourceRegistry(self.registry.path)
        inspected = []

        def inspect(argv):
            inspected.append(tuple(argv))
            with self.assertRaises(InvalidSchemaError):
                competing.record_disposition(ResourceDisposition(
                    value.resource_id, value.kind, "run-1", "node-1", "chunk",
                    CleanupDisposition.BLOCKED, "none", "concurrent_mutation",
                ))
            return CommandResult(
                tuple(argv), 1, "", "Error: No such container: " + value.resource_id,
            )

        observation = self.registry.observe_guarded_absence(
            self.adapter, plan, 0, inspect,
        )
        self.assertEqual(
            [("docker", "container", "inspect", value.resource_id)], inspected,
        )
        reopened = ResourceRegistry(self.registry.path)
        receipt = reopened.record_guarded_results(
            self.adapter, plan, (observation,), absent, absent,
        )
        self.assertEqual(CleanupDisposition.MISSING, receipt.dispositions[0].disposition)
        self.assertEqual((), reopened.resources_for("run-1", "node-1"))
        with self.assertRaises(InvalidSchemaError):
            reopened.record_guarded_results(
                self.adapter, plan, (observation,), absent, absent,
            )

    def test_guarded_recording_rejects_unmatched_terminal_state(self):
        first, _ = self.register(resource("ctr-a"))
        second = resource("ctr-b")
        self.registry.register(ResourceRecord(
            second.resource_id, second.kind, "run-1", "node-1", "chunk",
            "stop-remove", NOW, labels=second.labels,
        ))
        first_key = (first.kind, first.resource_id)
        second_key = (second.kind, second.resource_id)
        second_inspect = ("docker", "container", "inspect", second.resource_id)
        before = DockerInventory(
            (first,), (first_key, second_key), (second_key,), "registered_exact",
            (CommandResult(
                second_inspect, 1, "", "Error: No such container: " + second.resource_id,
            ),),
        )
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, before, "run-1", "node-1",
        )
        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, first,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        after = DockerInventory(
            (), (first_key, second_key), (first_key, second_key),
            "registered_exact", (
                CommandResult(
                    ("docker", "container", "inspect", first.resource_id), 1,
                    "", "Error: No such container: " + first.resource_id,
                ),
                CommandResult(
                    second_inspect, 1, "", "Error: No such container: " + second.resource_id,
                ),
            ),
        )

        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (guarded,), before, after,
            )
        self.assertEqual({first.resource_id, second.resource_id}, {
            item.resource_id for item in self.registry.resources_for("run-1", "node-1")
        })

    def test_cleanup_step_identity_orders_actions_before_terminal_observations(self):
        first, _ = self.register(resource("ctr-a"))
        second = resource("ctr-b")
        self.registry.register(ResourceRecord(
            second.resource_id, second.kind, "run-1", "node-1", "chunk",
            "stop-remove", NOW, labels=second.labels,
        ))
        second_key = (second.kind, second.resource_id)
        before = DockerInventory(
            (first,), ((first.kind, first.resource_id), second_key),
            (second_key,), "registered_exact", (CommandResult(
                ("docker", "container", "inspect", second.resource_id), 1,
                "", "Error: No such container: " + second.resource_id,
            ),),
        )
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, before, "run-1", "node-1",
        )
        self.assertTrue(hasattr(resource_models, "cleanup_step_identities"))
        steps = resource_models.cleanup_step_identities(plan)
        self.assertEqual([0, 1], [step.step_index for step in steps])
        self.assertEqual(
            ["command_action", "terminal_observation"],
            [step.step_type for step in steps],
        )
        self.assertEqual(1, len({step.plan_digest for step in steps}))

    def test_cleanup_step_identity_rejects_malformed_scalars(self):
        valid = "sha256:" + "0" * 64
        for digest in (None, 7, True, object()):
            with self.subTest(digest=digest), self.assertRaises(InvalidSchemaError):
                CleanupStepIdentity(digest, 0, "command_action")
        for index in (None, True, -1, "0"):
            with self.subTest(index=index), self.assertRaises(InvalidSchemaError):
                CleanupStepIdentity(valid, index, "command_action")
        for step_type in (None, 7, "command_result", ""):
            with self.subTest(step_type=step_type), self.assertRaises(InvalidSchemaError):
                CleanupStepIdentity(valid, 0, step_type)

    def test_cleanup_step_identity_rejects_duplicate_plan_steps(self):
        value, _ = self.register()
        action_plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        with self.assertRaises(InvalidSchemaError):
            resource_models.cleanup_step_identities(replace(
                action_plan,
                actions=(action_plan.actions[0], action_plan.actions[0]),
            ))

        missing_plan = self.adapter.plan_chunk_cleanup(
            self.registry, exact_absent(), "run-1", "node-1",
        )
        with self.assertRaises(InvalidSchemaError):
            resource_models.cleanup_step_identities(replace(
                missing_plan,
                dispositions=(
                    missing_plan.dispositions[0], missing_plan.dispositions[0],
                ),
            ))
        with self.assertRaises(InvalidSchemaError):
            resource_models.cleanup_step_identities(replace(
                action_plan,
                dispositions=(missing_plan.dispositions[0],),
            ))

    def test_terminal_authority_cannot_skip_an_unexecuted_command_step(self):
        first, _ = self.register(resource("ctr-a"))
        second = resource("ctr-b")
        third = resource("ctr-c")
        for value in (second, third):
            self.registry.register(ResourceRecord(
                value.resource_id, value.kind, "run-1", "node-1", "chunk",
                "stop-remove", NOW, labels=value.labels,
            ))
        third_key = (third.kind, third.resource_id)
        third_inspect = ("docker", "container", "inspect", third.resource_id)
        before = DockerInventory(
            (first, second),
            ((first.kind, first.resource_id), (second.kind, second.resource_id), third_key),
            (third_key,), "registered_exact", (CommandResult(
                third_inspect, 1, "", "Error: No such container: " + third.resource_id,
            ),),
        )
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, before, "run-1", "node-1",
        )
        self.assertEqual(2, len(plan.actions))
        first_authority = self.registry.execute_guarded_action(
            self.adapter, plan, 0, first,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        terminal_authority = self.registry.observe_guarded_absence(
            self.adapter, plan, 2,
            lambda argv: CommandResult(
                tuple(argv), 1, "", "Error: No such container: " + third.resource_id,
            ),
        )
        after = DockerInventory(
            (second,),
            ((first.kind, first.resource_id), (second.kind, second.resource_id), third_key),
            ((first.kind, first.resource_id), third_key), "registered_exact", (
                CommandResult(
                    ("docker", "container", "inspect", first.resource_id), 1,
                    "", "Error: No such container: " + first.resource_id,
                ),
                CommandResult(
                    third_inspect, 1, "", "Error: No such container: " + third.resource_id,
                ),
            ),
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (first_authority, terminal_authority),
                before, after,
            )

    def test_retired_record_cannot_reauthorize_stale_cleanup_action(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        action = plan.actions[0]
        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        self.registry.record_guarded_results(
            self.adapter, plan, (guarded,), DockerInventory((value,)), exact_absent(),
        )
        self.assertEqual((), self.registry.resources_for("run-1", "node-1"))

        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                action, value, registry=self.registry,
            )

    def test_guard_blocks_same_key_registration_during_revalidation_and_execution(self):
        created = NOW - timedelta(hours=25)
        orphan = resource(
            "reusable-volume", kind=ResourceKind.VOLUME,
            labels=owned_labels(created_at=created), created_at=created,
            use_known=True,
        )
        plan = self.adapter.plan_stale_sweep(
            DockerInventory((orphan,)), timedelta(hours=24),
        )
        competing = ResourceRegistry(self.registry.path)
        blocked = []

        def execute(argv):
            with self.assertRaises(InvalidSchemaError):
                competing.register(ResourceRecord(
                    orphan.resource_id, orphan.kind, "run-2", "node-2",
                    "chunk", "stop-remove", NOW,
                    labels=owned_labels(run_id="run-2"),
                ))
            blocked.append(True)
            return CommandResult(tuple(argv), 0, "", "")

        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, orphan, execute,
            lease_proof=inactive_lease(), orphan_mode=True,
        )

        self.assertIsInstance(guarded, GuardedCommandResult)
        self.assertTrue(blocked)
        self.assertEqual(plan.actions[0].argv, guarded.result.argv)

    def test_guard_allows_unrelated_key_and_releases_after_executor_failure(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        competing = ResourceRegistry(self.registry.path)
        unrelated = ResourceRecord(
            "other", ResourceKind.CONTAINER, "run-2", "node-2", "chunk",
            "stop-remove", NOW, labels=owned_labels(run_id="run-2"),
        )

        def execute_then_fail(_argv):
            competing.register(unrelated)
            raise RuntimeError("simulated executor crash")

        with self.assertRaisesRegex(RuntimeError, "simulated executor crash"):
            self.registry.execute_guarded_action(
                self.adapter, plan, 0, value, execute_then_fail,
            )
        self.assertEqual(unrelated, self.registry.resource_state_for_exact(
            unrelated.kind, unrelated.resource_id,
        )[0])

        # The failed callback released the exact-key guard.
        self.registry.record_disposition(ResourceDisposition(
            value.resource_id, value.kind, "run-1", "node-1",
            "chunk", CleanupDisposition.BLOCKED, "none",
            "executor_crashed",
        ))

    def test_guarded_result_is_generation_bound_expiring_and_single_use(self):
        clock = [NOW]
        registry = ResourceRegistry(
            Path(self.directory.name) / "guarded.jsonl",
            now=lambda: clock[0], authority_ttl=timedelta(seconds=5),
        )
        value = resource()
        registry.register(ResourceRecord(
            value.resource_id, value.kind, "run-1", "node-1", "chunk",
            "stop-remove", NOW, labels=value.labels,
        ))
        plan = self.adapter.plan_chunk_cleanup(
            registry, DockerInventory((value,)), "run-1", "node-1",
        )
        guarded = registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        registry.record_disposition(ResourceDisposition(
            value.resource_id, value.kind, "run-1", "node-1", "chunk",
            CleanupDisposition.BLOCKED, "none", "generation_changed",
        ))
        with self.assertRaises(InvalidSchemaError):
            registry.record_guarded_results(
                self.adapter, plan, (guarded,), DockerInventory((value,)),
                exact_absent(),
            )

        # A fresh authority can be consumed exactly once.
        fresh = registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        receipt = registry.record_guarded_results(
            self.adapter, plan, (fresh,), DockerInventory((value,)),
            exact_absent(),
        )
        self.assertEqual(CleanupDisposition.REMOVED, receipt.dispositions[-1].disposition)
        with self.assertRaises(InvalidSchemaError):
            registry.record_guarded_results(
                self.adapter, plan, (fresh,), DockerInventory((value,)),
                exact_absent(),
            )

        expiry_registry = ResourceRegistry(
            Path(self.directory.name) / "expiry.jsonl",
            now=lambda: clock[0], authority_ttl=timedelta(seconds=5),
        )
        expiry_registry.register(ResourceRecord(
            value.resource_id, value.kind, "run-1", "node-1", "chunk",
            "stop-remove", NOW, labels=value.labels,
        ))
        expiry_plan = self.adapter.plan_chunk_cleanup(
            expiry_registry, DockerInventory((value,)), "run-1", "node-1",
        )
        expiring = expiry_registry.execute_guarded_action(
            self.adapter, expiry_plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        clock[0] += timedelta(seconds=6)
        with self.assertRaises(InvalidSchemaError):
            expiry_registry.record_guarded_results(
                self.adapter, expiry_plan, (expiring,),
                DockerInventory((value,)), exact_absent(),
            )

    def test_guarded_result_rejects_caller_resealed_authority_id(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        resealed = replace(
            guarded, authority_id="sha256:" + "0" * 64,
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (resealed,), DockerInventory((value,)),
                exact_absent(),
            )

    def test_guarded_result_rejects_duplicate_authority_for_one_step(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (guarded, guarded),
                DockerInventory((value,)), exact_absent(),
            )

    def test_guarded_result_rejects_out_of_order_terminal_authorities(self):
        first, _ = self.register(resource("ctr-a"))
        second = resource("ctr-b")
        self.registry.register(ResourceRecord(
            second.resource_id, second.kind, "run-1", "node-1", "chunk",
            "stop-remove", NOW, labels=second.labels,
        ))
        keys = tuple((value.kind, value.resource_id) for value in (first, second))
        absent = DockerInventory(
            (), keys, keys, "registered_exact", tuple(CommandResult(
                ("docker", "container", "inspect", value.resource_id), 1, "",
                "Error: No such container: " + value.resource_id,
            ) for value in (first, second)),
        )
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, absent, "run-1", "node-1",
        )
        authorities = tuple(
            self.registry.observe_guarded_absence(
                self.adapter, plan, index,
                lambda argv: CommandResult(
                    tuple(argv), 1, "", "Error: No such container: " + argv[-1],
                ),
            )
            for index in range(2)
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, tuple(reversed(authorities)), absent, absent,
            )

    def test_guarded_result_rejects_cross_plan_authority_reuse(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        different_plan = replace(plan, before=plan.before + ("different-plan",))
        self.assertNotEqual(
            resource_models.cleanup_plan_digest(plan),
            resource_models.cleanup_plan_digest(different_plan),
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, different_plan, (guarded,),
                DockerInventory((value,)), exact_absent(),
            )

    def test_terminal_authority_is_extraneous_when_absence_no_longer_holds(self):
        value, _ = self.register()
        absent = exact_absent()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, absent, "run-1", "node-1",
        )
        observation = self.registry.observe_guarded_absence(
            self.adapter, plan, 0,
            lambda argv: CommandResult(
                tuple(argv), 1, "", "Error: No such container: " + value.resource_id,
            ),
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (observation,), absent,
                DockerInventory((value,)),
            )

    def test_issued_failure_authority_cannot_be_reused_as_success(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 17, "", "failed"),
        )
        forged = replace(
            guarded,
            result=CommandResult(guarded.result.argv, 0, "", ""),
        )
        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (forged,), DockerInventory((value,)),
                exact_absent(),
            )

    def test_guarded_authority_is_opaque_durable_registry_issuance(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        recomputed = legacy_recomputed_authority_id(
            result=guarded.result, kind=guarded.kind,
            resource_id=guarded.resource_id, run_id=guarded.run_id,
            node_id=guarded.node_id, action_digest=guarded.action_digest,
            state_generation=guarded.state_generation,
            issued_at=guarded.issued_at, expires_at=guarded.expires_at,
        )
        self.assertNotEqual(recomputed, guarded.authority_id)
        issued = json.loads(
            self.registry.path.read_text(encoding="utf-8").splitlines()[-1]
        )
        self.assertEqual("authority_issued", issued["event"])
        self.assertEqual(guarded.authority_id, issued["authority"]["authority_id"])
        self.assertEqual(
            guarded.step_identity.plan_digest,
            issued["authority"]["plan_digest"],
        )
        self.assertEqual(0, issued["authority"]["step_index"])
        self.assertEqual("command_action", issued["authority"]["step_type"])

        foreign = ResourceRegistry(Path(self.directory.name) / "foreign.jsonl")
        foreign.register(ResourceRecord(
            value.resource_id, value.kind, "run-1", "node-1", "chunk",
            "stop-remove", NOW, labels=value.labels,
        ))
        with self.assertRaises(InvalidSchemaError):
            foreign.record_guarded_results(
                self.adapter, plan, (guarded,), DockerInventory((value,)),
                exact_absent(),
            )

        reopened = ResourceRegistry(self.registry.path)
        receipt = reopened.record_guarded_results(
            self.adapter, plan, (guarded,), DockerInventory((value,)),
            exact_absent(),
        )
        self.assertEqual(CleanupDisposition.REMOVED, receipt.dispositions[-1].disposition)

    def test_recomputed_authority_without_registry_issuance_cannot_persist(self):
        value, _ = self.register()
        self.registry._now = lambda: NOW
        plan = self.adapter.plan_chunk_cleanup(
            self.registry, DockerInventory((value,)), "run-1", "node-1",
        )
        action = plan.actions[0]
        result = CommandResult(action.argv, 0, "", "")
        with self.registry._exclusive_lock():
            self.registry._reload_unlocked()
            generation = self.registry._state_generation_unlocked(
                (action.kind, action.resource_id),
            )
        issued_at = NOW
        expires_at = NOW + timedelta(minutes=1)
        forged = GuardedCommandResult(
            result, action.kind, action.resource_id, action.run_id,
            action.node_id, action.proof_digest, generation, issued_at,
            expires_at, legacy_recomputed_authority_id(
                result=result, kind=action.kind, resource_id=action.resource_id,
                run_id=action.run_id, node_id=action.node_id,
                action_digest=action.proof_digest,
                state_generation=generation, issued_at=issued_at,
                expires_at=expires_at,
            ), resource_models.cleanup_step_identities(plan)[0],
        )

        with self.assertRaises(InvalidSchemaError):
            self.registry.record_guarded_results(
                self.adapter, plan, (forged,), DockerInventory((value,)),
                exact_absent(),
            )

    def test_terminal_orphan_result_atomically_registers_and_retires(self):
        orphan_registry = ResourceRegistry(Path(self.directory.name) / "orphan.jsonl")
        orphan = resource("orphan-1")
        plan = self.adapter.plan_reconcile_run(
            orphan_registry, DockerInventory((orphan,), source="managed_orphan_sweep"),
            "run-1", terminal=True,
        )
        action = plan.actions[0]
        inspect = ("docker", "container", "inspect", "orphan-1")
        after = DockerInventory(
            (), ((ResourceKind.CONTAINER, "orphan-1"),),
            ((ResourceKind.CONTAINER, "orphan-1"),), "registered_exact",
            evidence=(CommandResult(inspect, 1, "", "Error: No such container: orphan-1"),),
        )
        guarded = orphan_registry.execute_guarded_action(
            self.adapter, plan, 0, orphan,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
            lease_proof=inactive_lease(), orphan_mode=True,
        )
        receipt = orphan_registry.record_guarded_results(
            self.adapter, plan, (guarded,),
            DockerInventory((orphan,), source="managed_orphan_sweep"), after,
        )
        self.assertEqual(CleanupDisposition.REMOVED, receipt.dispositions[0].disposition)
        self.assertEqual((), orphan_registry.resources_for("run-1"))

    def test_interrupted_result_frame_never_partially_retires(self):
        value, _ = self.register()
        plan = self.adapter.plan_chunk_cleanup(self.registry, DockerInventory((value,)), "run-1", "node-1")
        guarded = self.registry.execute_guarded_action(
            self.adapter, plan, 0, value,
            lambda argv: CommandResult(tuple(argv), 0, "", ""),
        )
        real_write = os.write
        wrote_partial = False

        def interrupt(descriptor, payload):
            nonlocal wrote_partial
            if not wrote_partial and bytes(payload).startswith(b'{"event":"transaction"'):
                wrote_partial = True
                real_write(descriptor, bytes(payload)[:31])
                raise OSError("simulated interrupted transaction write")
            return real_write(descriptor, payload)

        with mock.patch("workflow_kernel.resources.os.write", side_effect=interrupt):
            with self.assertRaises(InvalidSchemaError):
                self.registry.record_guarded_results(
                    self.adapter, plan, (guarded,), DockerInventory((value,)), exact_absent(),
                )
        replayed = ResourceRegistry(self.registry.path)
        self.assertEqual((value.resource_id,), tuple(
            item.resource_id for item in replayed.resources_for("run-1")
        ))

    def test_multi_resource_results_persist_as_one_transaction_frame(self):
        first = resource("ctr-1")
        self.register(first)
        second = resource("ctr-2")
        self.registry.register(ResourceRecord(
            "ctr-2", ResourceKind.CONTAINER, "run-1", "node-1", "chunk",
            "stop-remove", NOW, labels=second.labels,
        ))
        before = DockerInventory((first, second))
        plan = self.adapter.plan_chunk_cleanup(self.registry, before, "run-1", "node-1")
        keys = tuple((value.kind, value.resource_id) for value in (first, second))
        evidence = tuple(CommandResult(
            ("docker", "container", "inspect", value.resource_id), 1, "",
            "Error: No such container: " + value.resource_id,
        ) for value in (first, second))
        after = DockerInventory((), keys, keys, "registered_exact", evidence)
        resources = {
            (value.kind, value.resource_id): value for value in (first, second)
        }
        guarded = tuple(
            self.registry.execute_guarded_action(
                self.adapter, plan, index,
                resources[(action.kind, action.resource_id)],
                lambda argv: CommandResult(tuple(argv), 0, "", ""),
            )
            for index, action in enumerate(plan.actions)
        )
        receipt = self.registry.record_guarded_results(
            self.adapter, plan, guarded, before, after,
        )
        self.assertEqual(2, len(receipt.dispositions))
        lines = self.registry.path.read_text(encoding="utf-8").splitlines()
        frame = json.loads(lines[-1])
        self.assertEqual("transaction", frame["event"])
        self.assertEqual(4, len(frame["events"]))
        self.assertEqual(
            ["authority_consumed", "authority_consumed"],
            [event["event"] for event in frame["events"][:2]],
        )
        self.assertEqual((), ResourceRegistry(self.registry.path).resources_for("run-1"))


if __name__ == "__main__":
    unittest.main()
