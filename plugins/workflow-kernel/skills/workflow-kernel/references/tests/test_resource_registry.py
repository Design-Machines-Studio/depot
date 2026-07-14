import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tests import detail_digest, schema_matches
from workflow_kernel.resources import (
    CleanupDisposition,
    CleanupReceipt,
    CleanupScope,
    ResourceDisposition,
    ResourceKind,
    ResourceRecord,
    ResourceRegistry,
)
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


class ResourceRegistryTests(unittest.TestCase):
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
            registry.record_disposition(disposition(value, CleanupDisposition.REMOVED, "confirmed_removed"))
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
        encoded = json.dumps(payload, sort_keys=True)
        self.assertNotIn("top-secret", encoded)
        self.assertNotIn("hunter2", encoded)
        self.assertNotIn("x" * 100, encoded)
        self.assertNotIn("k" * 100, encoded)
        self.assertIn("value-sha256:", encoded)


if __name__ == "__main__":
    unittest.main()
