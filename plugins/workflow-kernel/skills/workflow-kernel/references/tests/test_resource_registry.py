import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tests import detail_digest, schema_matches
from workflow_kernel.resources import (
    _CLEANUP_RECEIPT_AUTHORITY,
    CleanupDisposition,
    CleanupAction,
    CleanupReceipt,
    CleanupPlan,
    CleanupScope,
    ResourceDisposition,
    ResourceKind,
    ResourceRecord,
    ResourceRegistry,
)
from workflow_kernel.redaction import freeze_json
from workflow_kernel.schema import InvalidSchemaError


NOW = datetime(2026, 7, 15, 1, 2, 3, tzinfo=timezone.utc)


def record(resource_id="shared", *, kind=ResourceKind.CONTAINER, run_id="run-1"):
    return ResourceRecord(
        resource_id=resource_id,
        kind=kind,
        run_id=run_id,
        node_id="node-1",
        lifecycle="chunk",
        cleanup_policy="stop-remove",
        created_at=NOW,
        labels={"proof": "owned"},
    )


def disposition(value, state, reason):
    return ResourceDisposition(
        resource_id=value.resource_id,
        kind=value.kind,
        run_id=value.run_id,
        node_id=value.node_id,
        lifecycle=value.lifecycle,
        disposition=state,
        action="remove_exact_id",
        reason=reason,
        command=("docker", "rm", value.resource_id),
    )


def authoritative_receipt(value, outcome):
    after = () if outcome.disposition in {CleanupDisposition.REMOVED, CleanupDisposition.MISSING} else (
        value.kind.value + ":" + value.resource_id,
    )
    return CleanupReceipt(
        CleanupScope(value.run_id, value.node_id),
        (value.kind.value + ":" + value.resource_id,), after, (outcome,),
        _authority=_CLEANUP_RECEIPT_AUTHORITY,
    )


class ResourceRegistryTests(unittest.TestCase):
    def test_preopened_registries_cannot_interleave_conflicting_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            first = ResourceRegistry(path)
            second = ResourceRegistry(path)
            first.register(record())
            conflicting = ResourceRecord(
                "shared", ResourceKind.CONTAINER, "run-1", "node-1", "chunk",
                "stop-remove", NOW, dependent_node_ids=("node-2",), labels={"proof": "owned"},
            )
            with self.assertRaises(InvalidSchemaError) as caught:
                second.register(conflicting)
            self.assertEqual(
                detail_digest("resource_registration_conflict"),
                caught.exception.details["reason_code"],
            )
            self.assertEqual(1, len(path.read_text(encoding="utf-8").splitlines()))

    def test_preopened_registries_reload_history_before_terminal_disposition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            first = ResourceRegistry(path)
            second = ResourceRegistry(path)
            value = record()
            first.register(value)
            removed = disposition(value, CleanupDisposition.REMOVED, "confirmed_removed")
            first.record_receipt(authoritative_receipt(value, removed))
            self.assertEqual((removed,), second.record_receipt(authoritative_receipt(value, removed)))
            with self.assertRaises(InvalidSchemaError) as caught:
                second.record_receipt(authoritative_receipt(
                    value, disposition(value, CleanupDisposition.MISSING, "later_missing"),
                ))
            self.assertEqual(
                detail_digest("terminal_resource_disposition_immutable"),
                caught.exception.details["reason_code"],
            )
            self.assertEqual(2, len(path.read_text(encoding="utf-8").splitlines()))

    def test_identity_is_kind_plus_id_and_replays_both(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            registry = ResourceRegistry(path)
            registry.register(record(kind=ResourceKind.NETWORK))
            registry.register(record(kind=ResourceKind.VOLUME))
            replayed = ResourceRegistry(path)
            self.assertEqual(
                {ResourceKind.NETWORK, ResourceKind.VOLUME},
                {value.kind for value in replayed.resources_for(CleanupScope("run-1", "node-1"))},
            )

    def test_replay_rejects_conflicting_owner_like_live_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            registry = ResourceRegistry(path)
            registry.register(record())
            event = json.loads(path.read_text())
            event["resource"]["run_id"] = "foreign-run"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event) + "\n")
            with self.assertRaises(InvalidSchemaError) as caught:
                ResourceRegistry(path)
            self.assertEqual(detail_digest("resource_registration_conflict"), caught.exception.details["reason_code"])

    def test_attempt_history_reconciles_blocked_and_retained_but_retires_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            value = record()
            registry = ResourceRegistry(path)
            registry.register(value)
            registry.record_disposition(disposition(value, CleanupDisposition.BLOCKED, "remove_failed"))
            registry.record_disposition(disposition(value, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "active_node"))
            self.assertEqual((value,), registry.resources_for("run-1"))
            registry.record_receipt(authoritative_receipt(
                value, disposition(value, CleanupDisposition.REMOVED, "confirmed_removed"),
            ))
            self.assertEqual((), registry.resources_for("run-1"))
            self.assertEqual(3, len(registry.disposition_history(ResourceKind.CONTAINER, "shared")))
            with self.assertRaises(InvalidSchemaError):
                registry.record_disposition(disposition(value, CleanupDisposition.MISSING, "later_missing"))
            self.assertEqual(CleanupDisposition.REMOVED, ResourceRegistry(path).disposition_for(ResourceKind.CONTAINER, "shared").disposition)

    def test_disposition_owner_must_match_registered_kind_and_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ResourceRegistry(Path(directory) / "resources.jsonl")
            value = record()
            registry.register(value)
            wrong = ResourceDisposition(
                "shared", ResourceKind.CONTAINER, "foreign-run", "node-1", "chunk",
                CleanupDisposition.BLOCKED, "none", "wrong_owner",
            )
            with self.assertRaises(InvalidSchemaError):
                registry.record_disposition(wrong)

    def test_actual_cleanup_receipt_matches_schema_and_redacts_recursively(self):
        value = record()
        receipt = CleanupReceipt(
            scope=CleanupScope("run-1", "node-1", terminal=True),
            before=("container:shared",),
            after=("container:shared",),
            dispositions=(ResourceDisposition(
                value.resource_id, value.kind, value.run_id, value.node_id,
                value.lifecycle, CleanupDisposition.BLOCKED, "remove_exact_id",
                "command_failed", evidence=({"authorization": "Bearer top-secret", "nested": {"password": "hunter2"}, "k" * 1000: "value"}, "x" * 1000),
                command=("docker", "rm", "shared"), follow_up="retry exact ID",
            ),),
        )
        payload = receipt.to_dict()
        schema_path = Path(__file__).parents[1] / "cleanup-receipt-schema.json"
        schema = json.loads(schema_path.read_text())
        self.assertTrue(schema_matches(payload, schema))
        self.assertEqual(["container:shared"], payload["before"])
        self.assertEqual(["container:shared"], payload["after"])
        encoded = json.dumps(payload, sort_keys=True)
        self.assertNotIn("top-secret", encoded)
        self.assertNotIn("hunter2", encoded)
        self.assertNotIn("x" * 100, encoded)
        self.assertNotIn("k" * 100, encoded)
        self.assertIn("value-sha256:", encoded)

    def test_receipt_redacts_secret_shapes_across_identity_scope_and_reason(self):
        cycle = []
        cycle.append(cycle)
        receipt = CleanupReceipt(
            scope=CleanupScope("run-cookie=session-secret", "node-1", terminal=True),
            before=("container:postgres://user:password@host/db",),
            after=("container:API_TOKEN=top-secret",),
            dispositions=(ResourceDisposition(
                "authorization=Bearer id-secret", ResourceKind.CONTAINER,
                "run-cookie=session-secret", "node-1", "chunk",
                CleanupDisposition.BLOCKED, "none",
                "authorization=Bearer top-secret",
                evidence=(
                    {"cookie": "session=private", "dsn": "postgres://u:p@host/db"},
                    "DATABASE_URL=postgres://u:p@host/db",
                    "API_TOKEN=env-secret",
                    cycle,
                ),
            ),),
        )
        payload = receipt.to_dict()
        schema = json.loads((Path(__file__).parents[1] / "cleanup-receipt-schema.json").read_text())
        self.assertTrue(schema_matches(payload, schema))
        encoded = json.dumps(payload, sort_keys=True)
        for secret in ("session-secret", "password@host", "top-secret", "private", "u:p@host", "env-secret"):
            self.assertNotIn(secret, encoded)
        self.assertIn("value-sha256:", encoded)

    def test_runtime_models_reject_noncanonical_domains_and_duplicate_dependencies(self):
        with self.assertRaises(InvalidSchemaError):
            ResourceRecord(
                "shared", ResourceKind.CONTAINER, " run-1", "node-1", "chunk",
                "stop-remove", NOW, labels={},
            )
        with self.assertRaises(InvalidSchemaError):
            ResourceRecord(
                "shared", ResourceKind.CONTAINER, "run-1", "node-1", "chunk",
                "stop-remove", NOW, dependent_node_ids=("node-2", "node-2"), labels={},
            )
        with self.assertRaises(InvalidSchemaError):
            ResourceDisposition(
                "shared", ResourceKind.CONTAINER, "run-1", "node-1", "chunk",
                CleanupDisposition.BLOCKED, "arbitrary", "reason",
            )
        with self.assertRaises(InvalidSchemaError):
            CleanupScope("run-1", terminal=1)
        with self.assertRaises(InvalidSchemaError):
            CleanupAction(
                "shared", ResourceKind.CONTAINER, "destroy", ("docker", "rm", "shared"),
                run_id="run-1", node_id="node-1", lifecycle="chunk",
            )
        with self.assertRaises(InvalidSchemaError):
            CleanupPlan(CleanupScope("run-1"), ("container:shared", "container:shared"), (), ())

    def test_registry_and_receipt_schemas_match_runtime_action_and_identity_limits(self):
        registry_schema = json.loads((Path(__file__).parents[1] / "resource-registry-schema.json").read_text())
        receipt_schema = json.loads((Path(__file__).parents[1] / "cleanup-receipt-schema.json").read_text())
        resource = registry_schema["$defs"]["resource"]["properties"]
        persisted_disposition = registry_schema["$defs"]["disposition"]["properties"]
        receipt_disposition = receipt_schema["properties"]["dispositions"]["items"]["properties"]
        self.assertEqual(4096, resource["resource_id"]["maxLength"])
        self.assertEqual(256, resource["run_id"]["maxLength"])
        self.assertEqual(["none", "remove_exact_id"], persisted_disposition["action"]["enum"])
        self.assertEqual(["none", "remove_exact_id"], receipt_disposition["action"]["enum"])

    def test_receipt_digests_overdeep_cyclic_evidence_without_losing_schema(self):
        root = []
        cursor = root
        for _ in range(12):
            child = []
            cursor.append(child)
            cursor = child
        cursor.append(root)
        receipt = CleanupReceipt(
            CleanupScope("run-1", "node-1"), (), (),
            (ResourceDisposition(
                "shared", ResourceKind.CONTAINER, "run-1", "node-1", "chunk",
                CleanupDisposition.BLOCKED, "none", "unsafe_evidence", evidence=(root,),
            ),),
        )
        payload = receipt.to_dict()
        schema = json.loads((Path(__file__).parents[1] / "cleanup-receipt-schema.json").read_text())
        self.assertTrue(schema_matches(payload, schema))
        self.assertIn("value-sha256:", json.dumps(payload))

    def test_receipt_cycle_digest_does_not_weaken_strict_json_freezing(self):
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(TypeError):
            freeze_json(cycle)

    def test_registry_rejects_symlink_and_hardlink_journal_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real.jsonl"
            ResourceRegistry(real).register(record())
            alias = root / "alias.jsonl"
            alias.symlink_to(real)
            with self.assertRaises(InvalidSchemaError):
                ResourceRegistry(alias)
            hard = root / "hard.jsonl"
            os.link(real, hard)
            with self.assertRaises(InvalidSchemaError):
                ResourceRegistry(hard)

    def test_registry_replay_requires_exact_event_and_resource_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            ResourceRegistry(path).register(record())
            event = json.loads(path.read_text())
            del event["resource"]["dependent_node_ids"]
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaises(InvalidSchemaError):
                ResourceRegistry(path)

    def test_registry_normalizes_lock_failures_and_terminal_requires_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("workflow_kernel.resources.LockHandle.acquire_bound", side_effect=OSError("lock")):
                with self.assertRaises(InvalidSchemaError):
                    ResourceRegistry(Path(directory) / "resources.jsonl")
            registry = ResourceRegistry(Path(directory) / "other.jsonl")
            value = record()
            registry.register(value)
            with self.assertRaises(InvalidSchemaError):
                registry.record_disposition(disposition(value, CleanupDisposition.REMOVED, "forged"))

    def test_exact_collection_boundaries_reject_strings_and_lists(self):
        with self.assertRaises(InvalidSchemaError):
            ResourceRecord(
                "shared", ResourceKind.CONTAINER, "run-1", "node-1", "chunk",
                "stop-remove", NOW, dependent_node_ids="node-2", labels={},
            )
        with self.assertRaises(InvalidSchemaError):
            CleanupReceipt(CleanupScope("run-1"), [], (), ())


if __name__ == "__main__":
    unittest.main()
