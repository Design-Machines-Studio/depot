import json
import unittest
from dataclasses import replace

from workflow_kernel.schema import (
    CorruptStateError,
    InvalidSchemaError,
    RunMode,
    RunState,
    RunStatus,
    UnsafePayloadError,
    WorkflowEvent,
)
from workflow_kernel.receipts import encode_receipt
from workflow_kernel.events import encode_event
from workflow_kernel.schema import NodeState


class SchemaTests(unittest.TestCase):
    def test_new_state_defaults_to_shadow(self):
        state = RunState.new("run-1", "2026-07-14T00:00:00Z")
        self.assertEqual(state.mode, RunMode.SHADOW)
        self.assertEqual(state.status, RunStatus.PLANNED)

    def test_event_parser_is_strict(self):
        valid = {
            "schema_version": 1, "sequence": 0, "run_id": "run-1",
            "node_id": None, "kind": "run.initialized",
            "occurred_at": "2026-07-14T00:00:00Z", "payload": {},
        }
        for field, value in (("schema_version", 2), ("sequence", True), ("sequence", -1)):
            candidate = dict(valid)
            candidate[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InvalidSchemaError):
                WorkflowEvent.from_dict(candidate)
        candidate = dict(valid, extra="unknown")
        with self.assertRaises(InvalidSchemaError):
            WorkflowEvent.from_dict(candidate)

    def test_unknown_enums_and_negative_revision_are_rejected(self):
        data = RunState.new("run-1", "2026-07-14T00:00:00Z").to_dict()
        data["mode"] = "automatic"
        with self.assertRaises(InvalidSchemaError):
            RunState.from_dict(data)
        data = RunState.new("run-1", "2026-07-14T00:00:00Z").to_dict()
        data["revision"] = -1
        with self.assertRaises(InvalidSchemaError):
            RunState.from_dict(data)

    def test_errors_are_machine_readable_and_redacted(self):
        error = UnsafePayloadError("unsafe", {"authorization": "Bearer fixture-secret", "field": "ok"})
        encoded = json.dumps(error.to_dict(), sort_keys=True)
        self.assertEqual(error.code, "unsafe_payload")
        self.assertNotIn("fixture-secret", encoded)
        self.assertIn("[REDACTED]", encoded)

    def test_recursive_redaction_covers_events_and_receipts(self):
        fixture = "never-print-this-fixture"
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z",
                              {"nested": [{"environment_value": fixture}], "api_token": fixture})
        event_json = json.dumps(event.to_dict(), sort_keys=True)
        receipt_json = encode_receipt({"event": event.to_dict(), "cookie": fixture}).decode()
        self.assertNotIn(fixture, event_json)
        self.assertNotIn(fixture, receipt_json)

    def test_event_payload_is_recursively_immutable_and_encoding_is_stable(self):
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z",
                              {"nested": {"items": ["one", "two"]}})
        with self.assertRaises(TypeError):
            event.payload["nested"]["items"][0] = "changed"
        self.assertEqual(encode_event(event), encode_event(event))

    def test_direct_schema_constructors_validate_and_freeze(self):
        with self.assertRaises(InvalidSchemaError):
            NodeState("")
        with self.assertRaises(InvalidSchemaError):
            RunState(1, -1, "run-1", RunMode.SHADOW, RunStatus.PLANNED,
                     "2026-07-14T00:00:00Z", "2026-07-14T00:00:00Z")

    def test_credential_bearing_evidence_references_are_rejected(self):
        unsafe = (
            "https://user:password@example.invalid/proof",
            "https://example.invalid/proof?access_token=never-print-this-fixture",
            "https://example.invalid/proof?signature=never-print-this-fixture",
        )
        for reference in unsafe:
            with self.subTest(reference=reference), self.assertRaises(UnsafePayloadError):
                WorkflowEvent(1, 0, "run-1", None, "evidence.recorded",
                              "2026-07-14T00:00:00Z", {"evidence": [reference]})
            with self.subTest(receipt=reference), self.assertRaises(UnsafePayloadError):
                encode_receipt({"reference": reference})

    def test_corrupt_state_error_has_stable_public_code(self):
        self.assertEqual(CorruptStateError("bad state").code, "corrupt_state")

    def test_error_details_value_error_is_safely_contained(self):
        fixture = "never-print-this-credential"
        error = UnsafePayloadError("unsafe", {
            "authorization": "Bearer " + fixture,
            "reference": "https://user:" + fixture + "@example.invalid/proof",
        })
        encoded = json.dumps(error.to_dict(), sort_keys=True)
        self.assertNotIn(fixture, encoded)
        self.assertEqual(error.details, {"detail": "[UNSAFE]"})

    def test_python_signature_errors_are_native_but_from_dict_is_stable(self):
        with self.assertRaises(TypeError):
            WorkflowEvent(1, 0)
        with self.assertRaises(InvalidSchemaError) as raised:
            WorkflowEvent.from_dict({})
        self.assertEqual(raised.exception.code, "invalid_schema")

    def test_dependency_graph_rejects_dangling_self_and_cycles(self):
        base = RunState.new("run-1", "2026-07-14T00:00:00Z")
        with self.assertRaises(InvalidSchemaError):
            replace(base, nodes={"a": NodeState("a", dependencies=("missing",))})

        def node(node_id, dependencies):
            return {"node_id": node_id, "status": "pending", "dependencies": dependencies, "evidence": []}

        for nodes in (
            {"a": node("a", ["a"])},
            {"a": node("a", ["b"]), "b": node("b", ["a"])},
        ):
            data = base.to_dict()
            data["nodes"] = nodes
            with self.subTest(nodes=nodes), self.assertRaises(InvalidSchemaError):
                RunState.from_dict(data)

    def test_untrusted_mapping_keys_fail_with_stable_schema_error(self):
        event_data = {
            "schema_version": 1, "sequence": 0, "run_id": "run-1", "node_id": None,
            "kind": "run.initialized", "occurred_at": "2026-07-14T00:00:00Z", "payload": {},
            1: "mixed-key",
        }
        state_data = RunState.new("run-1", "2026-07-14T00:00:00Z").to_dict()
        state_data[1] = "mixed-key"
        for parser, data in ((WorkflowEvent.from_dict, event_data), (RunState.from_dict, state_data)):
            with self.subTest(parser=parser.__qualname__), self.assertRaises(InvalidSchemaError) as raised:
                parser(data)
            self.assertEqual(raised.exception.code, "invalid_schema")
            self.assertEqual(raised.exception.message, "schema keys must be strings")

    def test_new_delegates_mode_validation_to_constructor(self):
        self.assertEqual(RunState.new("run-1", "2026-07-14T00:00:00Z", mode="enforce").mode, RunMode.ENFORCE)
