import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from workflow_kernel.resources import (
    CleanupDisposition,
    ResourceKind,
    ResourceRecord,
    ResourceRegistry,
)
from workflow_kernel.schema import InvalidSchemaError
from tests import detail_digest


NOW = datetime(2026, 7, 15, 1, 2, 3, tzinfo=timezone.utc)


def record(resource_id="ctr-1", *, lifecycle="chunk", dependencies=()):
    return ResourceRecord(
        resource_id=resource_id,
        kind=ResourceKind.CONTAINER,
        run_id="run-1",
        node_id="node-1",
        lifecycle=lifecycle,
        cleanup_policy="stop-remove",
        created_at=NOW,
        dependent_node_ids=dependencies,
    )


class ResourceRegistryTests(unittest.TestCase):
    def test_registration_is_durable_replayable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            registry = ResourceRegistry(path)
            registry.register(record())
            registry.register(record())

            replayed = ResourceRegistry(path)
            self.assertEqual((record(),), replayed.resources_for("run-1", "node-1"))
            self.assertEqual(1, len(path.read_text().splitlines()))

    def test_conflicting_registration_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ResourceRegistry(Path(directory) / "resources.jsonl")
            registry.register(record())
            with self.assertRaises(InvalidSchemaError) as caught:
                registry.register(record(lifecycle="run"))
            self.assertEqual("workflow kernel operation failed", caught.exception.message)
            self.assertEqual(detail_digest("resource_registration_conflict"), caught.exception.details["reason_code"])

    def test_disposition_is_durable_and_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            registry = ResourceRegistry(path)
            registry.register(record("ctr-1"))
            registry.register(record("ctr-2", lifecycle="run", dependencies=("node-2",)))
            registry.record_disposition("ctr-1", CleanupDisposition.REMOVED, "removed_exact_id")

            replayed = ResourceRegistry(path)
            self.assertEqual(CleanupDisposition.REMOVED, replayed.disposition_for("ctr-1").disposition)
            self.assertEqual((record("ctr-2", lifecycle="run", dependencies=("node-2",)),), replayed.resources_for("run-1"))

    def test_registry_and_receipt_schemas_are_valid_json_schema_objects(self):
        root = Path(__file__).parents[1]
        for name in ("resource-registry-schema.json", "cleanup-receipt-schema.json"):
            schema = json.loads((root / name).read_text())
            self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
            self.assertEqual("object", schema["type"])
            self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
