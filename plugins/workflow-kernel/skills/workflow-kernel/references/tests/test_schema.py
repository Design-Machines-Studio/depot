import hashlib
import json
import unittest
from dataclasses import replace
from unittest import mock

from workflow_kernel import schema
from workflow_kernel.schema import (
    CorruptStateError,
    InvalidSchemaError,
    RunMode,
    RunState,
    RunStatus,
    UnsafePayloadError,
    WorkflowEvent,
)
from workflow_kernel.receipts import encode_receipt, evidence_receipt
from workflow_kernel.events import encode_event
from workflow_kernel.schema import NodeState
from workflow_kernel.state import encode_state


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

    def test_evidence_url_fragment_is_rejected_before_durable_encoding(self):
        sentinel = "never-persist-this-access-token"
        reference = "https://example.invalid/proof#access_token=" + sentinel
        with self.assertRaises(UnsafePayloadError):
            event = WorkflowEvent(1, 0, "run-1", None, "evidence.recorded",
                                  "2026-07-14T00:00:00Z", {"evidence": [reference]})
            encode_event(event)

    def test_evidence_url_rejects_empty_query_and_fragment_delimiters(self):
        for reference in ("https://example.invalid/proof?", "https://example.invalid/proof#"):
            with self.subTest(reference=reference), self.assertRaises(UnsafePayloadError):
                WorkflowEvent(1, 0, "run-1", None, "evidence.recorded",
                              "2026-07-14T00:00:00Z", {"evidence": [reference]})

    def test_url_evidence_is_normalized_before_event_and_receipt_output(self):
        sentinel = "never-persist-this-webhook-token"
        reference = "https://hooks.example.invalid/services/" + sentinel
        expected = "url-sha256:" + hashlib.sha256(reference.encode("utf-8")).hexdigest()

        event = WorkflowEvent(1, 0, "run-1", None, "evidence.recorded",
                              "2026-07-14T00:00:00Z", {"evidence": [reference]})
        receipt = evidence_receipt("run-1", "test", reference)

        self.assertEqual(event.payload["evidence"], (expected,))
        self.assertEqual(receipt["reference"], expected)
        for encoded in (encode_event(event), encode_receipt(receipt)):
            self.assertNotIn(sentinel.encode(), encoded)
            self.assertNotIn(reference.encode(), encoded)
            self.assertIn(expected.encode(), encoded)

    def test_url_values_are_normalized_under_arbitrary_event_payload_keys(self):
        sentinel = "never-persist-this-payload-token"
        source_url = "https://source.example.invalid/" + sentinel
        nested_url = "http://nested.example.invalid/" + sentinel
        source_digest = "url-sha256:" + hashlib.sha256(source_url.encode("utf-8")).hexdigest()
        nested_digest = "url-sha256:" + hashlib.sha256(nested_url.encode("utf-8")).hexdigest()

        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {
                                  "source_url": source_url,
                                  "metadata": {"arbitrary_name": nested_url},
                              })

        self.assertEqual(event.payload["source_url"], source_digest)
        self.assertEqual(event.payload["metadata"]["arbitrary_name"], nested_digest)
        encoded = encode_event(event)
        self.assertNotIn(sentinel.encode(), encoded)
        self.assertNotIn(b"source.example.invalid", encoded)
        self.assertNotIn(b"nested.example.invalid", encoded)

    def test_url_values_are_normalized_in_receipt_metadata(self):
        sentinel = "never-persist-this-metadata-token"
        source_url = "https://metadata.example.invalid/" + sentinel
        nested_url = "https://nested.example.invalid/" + sentinel
        source_digest = "url-sha256:" + hashlib.sha256(source_url.encode("utf-8")).hexdigest()
        nested_digest = "url-sha256:" + hashlib.sha256(nested_url.encode("utf-8")).hexdigest()

        receipt = evidence_receipt("run-1", "test", "receipt.json", metadata={
            "source_url": source_url,
            "nested": {"arbitrary_name": nested_url},
        })

        self.assertEqual(receipt["metadata"]["source_url"], source_digest)
        self.assertEqual(receipt["metadata"]["nested"]["arbitrary_name"], nested_digest)
        encoded = encode_receipt(receipt)
        self.assertNotIn(sentinel.encode(), encoded)
        self.assertNotIn(b"metadata.example.invalid", encoded)
        self.assertNotIn(b"nested.example.invalid", encoded)

    def test_url_value_policy_rejects_unsupported_schemes_and_preserves_prose(self):
        preserved = {
            "note": "See https://example.invalid/proof for context",
            "leading_url_prose": "https://example.invalid/proof is documented here",
            "local": "artifacts/review/report.json",
        }
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", preserved)
        self.assertEqual(event.to_dict()["payload"], preserved)

        for value in ("s3://bucket/report.json", "ftp://example.invalid/report.json"):
            with self.subTest(value=value), self.assertRaises(UnsafePayloadError):
                WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {"source_url": value})

    def test_url_values_are_normalized_in_state_identity_and_evidence(self):
        sentinel = "never-persist-this-state-identity"
        run_url = "https://runs.example.invalid/" + sentinel
        evidence_url = "https://artifacts.example.invalid/" + sentinel
        run_digest = "url-sha256:" + hashlib.sha256(run_url.encode("utf-8")).hexdigest()
        evidence_digest = "url-sha256:" + hashlib.sha256(evidence_url.encode("utf-8")).hexdigest()

        state = replace(RunState.new(run_url, "2026-07-14T00:00:00Z"),
                        evidence=(evidence_url,))

        self.assertEqual(state.run_id, run_digest)
        self.assertEqual(state.evidence, (evidence_digest,))
        encoded = encode_state(state)
        self.assertNotIn(sentinel.encode(), encoded)
        self.assertNotIn(b"runs.example.invalid", encoded)
        self.assertNotIn(b"artifacts.example.invalid", encoded)

    def test_url_evidence_is_normalized_by_direct_and_from_dict_state(self):
        sentinel = "never-persist-this-state-token"
        reference = "https://artifacts.example.invalid/download/" + sentinel
        expected = "url-sha256:" + hashlib.sha256(reference.encode("utf-8")).hexdigest()
        base = RunState.new("run-1", "2026-07-14T00:00:00Z")

        direct = replace(base, evidence=(reference,))
        data = base.to_dict()
        data["evidence"] = [reference]
        parsed = RunState.from_dict(data)

        for state in (direct, parsed):
            self.assertEqual(state.evidence, (expected,))
            encoded = encode_state(state)
            self.assertNotIn(sentinel.encode(), encoded)
            self.assertNotIn(reference.encode(), encoded)
            self.assertIn(expected.encode(), encoded)

    def test_evidence_reference_policy_accepts_safe_ids_and_rejects_unsafe_paths(self):
        digest = "sha256:" + "a" * 64
        for reference in ("receipt.json", "artifacts/review/report-01.json", digest):
            with self.subTest(allowed=reference):
                event = WorkflowEvent(1, 0, "run-1", None, "evidence.recorded",
                                      "2026-07-14T00:00:00Z", {"evidence": [reference]})
                self.assertEqual(event.payload["evidence"], (reference,))

        unsafe = ("", "/absolute/report.json", "../report.json", "artifacts/../report.json",
                  "artifacts\\report.json", "artifacts//report.json", "report\n.json",
                  "s3://bucket/report.json", "sha256:" + "A" * 64)
        for reference in unsafe:
            with self.subTest(rejected=reference), self.assertRaises(UnsafePayloadError):
                WorkflowEvent(1, 0, "run-1", None, "evidence.recorded",
                              "2026-07-14T00:00:00Z", {"evidence": [reference]})

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

    def test_direct_state_enforces_aggregate_evidence_boundary(self):
        self.assertTrue(hasattr(schema, "MAX_EVIDENCE_ITEMS"))
        base = RunState.new("run-1", "2026-07-14T00:00:00Z")
        with mock.patch.object(schema, "MAX_EVIDENCE_ITEMS", 2):
            boundary = replace(base, evidence=("run",), nodes={
                "n": NodeState("n", evidence=("node",)),
            })
            self.assertEqual(boundary.evidence, ("run",))
            with self.assertRaises(InvalidSchemaError) as raised:
                replace(boundary, evidence=("run", "overflow"))
        self.assertEqual(raised.exception.details["reason_code"], "evidence_limit_exceeded")
        self.assertEqual(raised.exception.details["limit_items"], 2)

    def test_state_from_dict_enforces_aggregate_evidence_boundary(self):
        self.assertTrue(hasattr(schema, "MAX_EVIDENCE_ITEMS"))
        data = RunState.new("run-1", "2026-07-14T00:00:00Z").to_dict()
        data["evidence"] = ["run"]
        data["nodes"] = {
            "n": {"node_id": "n", "status": "pending", "dependencies": [], "evidence": ["node"]},
        }
        with mock.patch.object(schema, "MAX_EVIDENCE_ITEMS", 2):
            self.assertEqual(RunState.from_dict(data).nodes["n"].evidence, ("node",))
            data["evidence"].append("overflow")
            with self.assertRaises(InvalidSchemaError) as raised:
                RunState.from_dict(data)
        self.assertEqual(raised.exception.details["reason_code"], "evidence_limit_exceeded")
        self.assertEqual(raised.exception.details["limit_items"], 2)
