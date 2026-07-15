import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tests import detail_digest, schema_matches
from workflow_kernel.resources import (
    CleanupDisposition,
    CleanupAction,
    CleanupReceipt,
    CleanupPlan,
    CleanupScope,
    ResourceDisposition,
    ResourceKind,
    ResourceRecord,
    ResourceRegistry,
    cleanup_proof_digest,
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
    )


def append_terminal_transaction(path, outcome):
    disposition_payload = {
        "resource_id": outcome.resource_id, "kind": outcome.kind.value,
        "run_id": outcome.run_id, "node_id": outcome.node_id,
        "lifecycle": outcome.lifecycle, "disposition": outcome.disposition.value,
        "action": outcome.action, "reason": outcome.reason,
        "command": list(outcome.command), "evidence": list(outcome.evidence),
    }
    frame = {
        "event": "transaction",
        "transaction_id": cleanup_proof_digest({
            "resource_id": outcome.resource_id, "reason": outcome.reason,
        }),
        "events": [{"event": "disposition", "disposition": disposition_payload}],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(frame, sort_keys=True) + "\n")


class ResourceRegistryTests(unittest.TestCase):
    def test_global_exact_lookup_reloads_before_returning_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            reader = ResourceRegistry(path)
            writer = ResourceRegistry(path)
            expected = record("shared", run_id="run-2")
            writer.register(expected)

            self.assertEqual(
                (expected, True),
                reader.resource_state_for_exact(ResourceKind.CONTAINER, "shared"),
            )

            append_terminal_transaction(
                path,
                disposition(expected, CleanupDisposition.REMOVED, "removed"),
            )
            self.assertEqual(
                (expected, False),
                reader.resource_state_for_exact(ResourceKind.CONTAINER, "shared"),
            )

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

    def test_preopened_registries_reload_terminal_transaction_and_reject_detached_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            first = ResourceRegistry(path)
            second = ResourceRegistry(path)
            value = record()
            first.register(value)
            removed = disposition(value, CleanupDisposition.REMOVED, "confirmed_removed")
            append_terminal_transaction(path, removed)
            self.assertEqual(removed, second.disposition_for(ResourceKind.CONTAINER, "shared"))
            with self.assertRaises(InvalidSchemaError) as caught:
                second.record_receipt(authoritative_receipt(
                    value, disposition(value, CleanupDisposition.MISSING, "later_missing"),
                ))
            self.assertEqual(
                detail_digest("cleanup_receipt_not_authoritative"),
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
            append_terminal_transaction(
                path, disposition(value, CleanupDisposition.REMOVED, "confirmed_removed"),
            )
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

    def test_registry_schema_rejects_fields_from_other_event_variants(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "resource-registry-schema.json").read_text()
        )
        payload = {
            "event": "registered",
            "resource": {
                "resource_id": "shared", "kind": "container",
                "run_id": "run-1", "node_id": "node-1",
                "lifecycle": "chunk", "cleanup_policy": "retain",
                "created_at": "2026-07-15T01:02:03Z",
                "dependent_node_ids": [], "labels": {},
            },
            "transaction_id": "sha256:" + "0" * 64,
        }
        self.assertFalse(schema_matches(payload, schema))

    def test_registry_schema_reserves_terminal_dispositions_for_transactions(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "resource-registry-schema.json").read_text()
        )
        disposition_payload = {
            "resource_id": "shared", "kind": "container",
            "run_id": "run-1", "node_id": "node-1", "lifecycle": "chunk",
            "disposition": "blocked", "action": "remove_exact_id",
            "reason": "retry", "command": ["docker", "rm", "shared"],
            "evidence": [],
        }
        standalone = {"event": "disposition", "disposition": disposition_payload}
        self.assertTrue(schema_matches(standalone, schema))
        standalone["disposition"] = {**disposition_payload, "disposition": "removed"}
        self.assertFalse(schema_matches(standalone, schema))
        transaction = {
            "event": "transaction", "transaction_id": "sha256:" + "0" * 64,
            "events": [standalone],
        }
        self.assertTrue(schema_matches(transaction, schema))

    def test_registry_schema_reserves_authority_consumption_for_transactions(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "resource-registry-schema.json").read_text()
        )
        consumed = {
            "event": "authority_consumed",
            "authority_id": "sha256:" + "1" * 64,
        }
        self.assertFalse(schema_matches(consumed, schema))
        self.assertTrue(schema_matches({
            "event": "transaction",
            "transaction_id": "sha256:" + "2" * 64,
            "events": [consumed],
        }, schema))

    def test_registry_schema_records_opaque_authority_issuance(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "resource-registry-schema.json").read_text()
        )
        issued = {
            "event": "authority_issued",
            "authority": {
                "authority_id": "sha256:" + "1" * 64,
                "authority_type": "command_result",
                "kind": "container", "resource_id": "shared",
                "run_id": "run-1", "node_id": "node-1",
                "capability_digest": "sha256:" + "2" * 64,
                "state_generation": "sha256:" + "3" * 64,
                "result_id": "sha256:" + "4" * 64,
                "issued_at": "2026-07-15T01:02:03Z",
                "expires_at": "2026-07-15T01:03:03Z",
            },
        }
        self.assertTrue(schema_matches(issued, schema))
        self.assertFalse(schema_matches({
            "event": "transaction", "transaction_id": "sha256:" + "5" * 64,
            "events": [issued],
        }, schema))

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

    def test_lock_replacement_aborts_original_transaction_before_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            first = ResourceRegistry(path)
            second = ResourceRegistry(path)
            original_append = first._append_unlocked

            def replace_lock(event):
                first.path.with_name(first.path.name + ".lock").unlink()
                second.register(ResourceRecord(
                    "replacement", ResourceKind.CONTAINER, "run-1", "node-1", "chunk",
                    "stop-remove", NOW, labels={"proof": "second"},
                ))
                original_append(event)

            first._append_unlocked = replace_lock
            with self.assertRaises(InvalidSchemaError):
                first.register(record())
            replayed = ResourceRegistry(path)
            self.assertEqual("replacement", replayed.resources_for("run-1")[0].resource_id)
            self.assertEqual("second", replayed.resources_for("run-1")[0].labels["proof"])
            self.assertEqual(1, len(path.read_text(encoding="utf-8").splitlines()))

    def test_journal_replacement_aborts_before_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            registry = ResourceRegistry(path)
            registry.register(record("first"))
            original_append = registry._append_unlocked

            def replace_journal(event):
                replacement = path.with_name("replacement.jsonl")
                replacement.write_text("", encoding="utf-8")
                os.replace(replacement, path)
                original_append(event)

            registry._append_unlocked = replace_journal
            with self.assertRaises(InvalidSchemaError):
                registry.register(record("second"))
            self.assertEqual("", path.read_text(encoding="utf-8"))

    def test_incomplete_final_transaction_frame_is_ignored_but_interior_corruption_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            ResourceRegistry(path).register(record())
            with path.open("ab") as handle:
                handle.write(b'{"event":"transaction","transaction_id":"sha256:')
            self.assertEqual(1, len(ResourceRegistry(path).resources_for("run-1")))
            with path.open("ab") as handle:
                handle.write(b'\n')
            with self.assertRaises(InvalidSchemaError):
                ResourceRegistry(path)

    def test_mutation_repairs_incomplete_final_frame_before_append(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.jsonl"
            registry = ResourceRegistry(path)
            registry.register(record("first"))
            with path.open("ab") as handle:
                handle.write(b'{"event":"registered","resource":')

            registry.register(record("second"))

            replayed = ResourceRegistry(path)
            self.assertEqual(
                {"first", "second"},
                {value.resource_id for value in replayed.resources_for("run-1")},
            )
            self.assertTrue(path.read_bytes().endswith(b"\n"))

    def test_cleanup_plan_dependencies_must_reference_an_earlier_action(self):
        base = CleanupAction(
            "shared", ResourceKind.CONTAINER, "remove", ("docker", "rm", "shared"),
            None, "run-1", "node-1", "chunk", "sha256:" + "1" * 64,
            ("proof",), {}, None, "sha256:" + "2" * 64,
        )
        for dependency in (0, 1, 2):
            dependent = CleanupAction(
                "second", ResourceKind.CONTAINER, "remove", ("docker", "rm", "second"),
                dependency, "run-1", "node-1", "chunk", "sha256:" + "3" * 64,
                ("proof",), {}, None, "sha256:" + "4" * 64,
            )
            actions = (dependent,) if dependency == 0 else (base, dependent)
            with self.subTest(dependency=dependency), self.assertRaises(InvalidSchemaError):
                CleanupPlan(CleanupScope("run-1", "node-1"), (), actions, ())

        valid = CleanupAction(
            "second", ResourceKind.CONTAINER, "remove", ("docker", "rm", "second"),
            0, "run-1", "node-1", "chunk", "sha256:" + "3" * 64,
            ("proof",), {}, None, "sha256:" + "4" * 64,
        )
        self.assertEqual(
            (base, valid),
            CleanupPlan(
                CleanupScope("run-1", "node-1"), (), (base, valid), (),
            ).actions,
        )

    def test_cleanup_plan_serialization_preserves_disposition_only_decisions(self):
        value = record()
        plan = CleanupPlan(
            CleanupScope("run-1", "node-1"), ("container:shared",), (),
            (disposition(value, CleanupDisposition.BLOCKED, "blocked"),),
        )
        payload = plan.to_dict()
        self.assertEqual("blocked", payload["dispositions"][0]["disposition"])
        schema = json.loads((Path(__file__).parents[1] / "cleanup-plan-schema.json").read_text())
        self.assertTrue(schema_matches(payload, schema))


if __name__ == "__main__":
    unittest.main()
