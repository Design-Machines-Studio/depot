import hashlib
import io
import json
import logging
import pickle
import traceback
import unittest
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from unittest import mock

from tests import detail_digest, detail_key_digest
from workflow_kernel import receipts, redaction, schema
from workflow_kernel.schema import (
    CorruptStateError,
    InvalidSchemaError,
    RunMode,
    RunState,
    RunStatus,
    UnsafePayloadError,
    WorkflowEvent,
)
from workflow_kernel.receipts import encode_receipt, evidence_receipt, transition_receipt
from workflow_kernel.events import encode_event
from workflow_kernel.schema import NodeState
from workflow_kernel.state import encode_state


class CountingStr(str):
    """String wrapper sharing a test-only character-operation counter across slices."""

    def __new__(cls, value, counter=None):
        result = super().__new__(cls, value)
        result.counter = counter if counter is not None else [0]
        return result

    @property
    def operations(self):
        return self.counter[0]

    def __getitem__(self, key):
        self.counter[0] += 1
        result = super().__getitem__(key)
        if isinstance(result, str):
            return type(self)(result, self.counter)
        return result

    def __iter__(self):
        for character in super().__iter__():
            self.counter[0] += 1
            yield character

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

    def test_uncatalogued_error_messages_fall_back(self):
        exact = "https://example.invalid/never-persist-exact-message"
        embedded = "See https://example.invalid/never-persist-embedded-message now"
        network = "See <//example.invalid/never-persist-network-message>."
        values = (
            exact,
            embedded,
            network,
            "authorization=Bearer never-persist-authorization",
            "Bearer never-persist-bearer",
            "password=never-persist-password",
            "token=never-persist-token",
            "cookie=never-persist-cookie",
            "dsn=never-persist-dsn",
            "environment_value=never-persist-env",
            "parser rejected never-persist-parser-text at offset 4",
            "never-persist-arbitrary-plain-secret",
        )
        for source in values:
            error = UnsafePayloadError(source)
            self.assertEqual(error.to_dict()["error"]["message"], "workflow kernel error")
            self.assertEqual(str(error), "workflow kernel error")
            self.assertNotIn("never-persist", json.dumps(error.to_dict()))
            self.assertNotIn("never-persist", str(error))

    def test_error_messages_and_codes_are_owned_by_closed_enums(self):
        self.assertTrue(hasattr(schema, "ErrorMessage"))
        self.assertTrue(hasattr(schema, "ErrorCode"))
        message = schema.ErrorMessage.INVALID_STRING_FIELD
        error = UnsafePayloadError(message)
        self.assertEqual(error.message, "invalid string field")
        self.assertEqual(error.args, ("invalid string field",))
        self.assertEqual(error.code, "unsafe_payload")
        for enum_message in schema.ErrorMessage:
            candidate = schema.KernelError(enum_message)
            self.assertEqual(candidate.message, enum_message.value)
            self.assertEqual(candidate.args, (enum_message.value,))
        for error_type, enum_code in (
            (schema.KernelError, schema.ErrorCode.KERNEL_ERROR),
            (schema.InvalidSchemaError, schema.ErrorCode.INVALID_SCHEMA),
            (schema.CorruptEventError, schema.ErrorCode.CORRUPT_EVENT),
            (schema.CorruptStateError, schema.ErrorCode.CORRUPT_STATE),
            (schema.SequenceConflictError, schema.ErrorCode.SEQUENCE_CONFLICT),
            (schema.RevisionConflictError, schema.ErrorCode.REVISION_CONFLICT),
            (schema.LeaseConflictError, schema.ErrorCode.LEASE_CONFLICT),
            (schema.IllegalTransitionError, schema.ErrorCode.ILLEGAL_TRANSITION),
            (schema.MissingEvidenceError, schema.ErrorCode.MISSING_EVIDENCE),
            (schema.UnsafePayloadError, schema.ErrorCode.UNSAFE_PAYLOAD),
        ):
            self.assertEqual(error_type(schema.ErrorMessage.GENERIC).code, enum_code.value)

        raw = UnsafePayloadError("invalid string field")
        self.assertEqual(raw.message, "workflow kernel error")

    def test_error_envelope_is_the_single_frozen_public_boundary_value(self):
        error = UnsafePayloadError(schema.ErrorMessage.INVALID_STRING_FIELD, {"field": "safe"})
        envelope = error._envelope
        self.assertIsInstance(envelope, schema.ErrorEnvelope)
        self.assertEqual(envelope.code, schema.ErrorCode.UNSAFE_PAYLOAD)
        self.assertEqual(envelope.message, schema.ErrorMessage.INVALID_STRING_FIELD)
        self.assertIs(envelope.details, error.details)
        with self.assertRaises(FrozenInstanceError):
            envelope.code = schema.ErrorCode.KERNEL_ERROR

    def test_trusted_subclasses_are_allowed_but_base_serializer_reads_the_envelope(self):
        sentinel = "never-persist-trusted-subclass"

        class TrustedError(schema.UnsafePayloadError):
            def to_dict(self):
                return {"secret": sentinel}

        error = TrustedError(schema.ErrorMessage.INVALID_STRING_FIELD, {"field": sentinel})
        self.assertEqual(error.to_dict(), {"secret": sentinel})
        serialized = schema.serialize_kernel_error(error)
        self.assertEqual(serialized["error"]["code"], "unsafe_payload")
        self.assertNotIn(sentinel, json.dumps(serialized, sort_keys=True))
        self.assertEqual(schema.KernelError.to_dict(error), serialized)

    def test_base_exception_surfaces_contain_only_the_safe_message(self):
        sentinel = "never-persist-base-exception"
        error = UnsafePayloadError(sentinel, {"note": "Bearer " + sentinel})
        expected = "workflow kernel error"
        self.assertEqual(BaseException.args.__get__(error, type(error)), (expected,))
        round_trip = pickle.loads(pickle.dumps(error))
        self.assertEqual(round_trip.message, error.message)
        self.assertEqual(round_trip.code, error.code)
        self.assertNotIn(sentinel, json.dumps(round_trip.to_dict(), sort_keys=True))

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("workflow-kernel-safe-error-test")
        logger.setLevel(logging.ERROR)
        logger.addHandler(handler)
        try:
            logger.error("%r | %s", error, error)
        finally:
            logger.removeHandler(handler)

        surfaces = (
            repr(error), str(error), format(error), repr(error.__reduce__()),
            pickle.dumps(error).decode("latin-1"), stream.getvalue(),
        )
        for surface in surfaces:
            with self.subTest(surface=surface[:24]):
                self.assertNotIn(sentinel, surface)
        self.assertEqual(str(error), expected)

    def test_error_output_survives_public_and_envelope_mutation_attempts(self):
        message = schema.ErrorMessage.INVALID_STRING_FIELD
        error = UnsafePayloadError(message, {"field": "safe"})
        before = error.to_dict()
        sentinel = "never-persist-mutated-envelope"
        for name, value in (
            ("_envelope", sentinel), ("message", sentinel), ("code", sentinel),
            ("details", {"secret": sentinel}), ("args", (sentinel,)),
        ):
            with self.subTest(set=name), self.assertRaises(AttributeError):
                setattr(error, name, value)
            with self.subTest(delete=name), self.assertRaises(AttributeError):
                delattr(error, name)
        self.assertEqual(error.to_dict(), before)
        self.assertEqual(str(error), message.value)
        self.assertEqual(error.args, (message.value,))

    def test_error_messages_fail_closed_on_invalid_inputs(self):
        fallback = "workflow kernel error"
        values = (
            "data:text/plain,never-persist-unsupported-message",
            "https://example.invalid/proof?token=never-persist-query-message",
            "x" * (redaction.MAX_STRING_LENGTH + 1),
            "",
            None,
        )
        for value in values:
            error = UnsafePayloadError(value)
            self.assertEqual(error.to_dict()["error"]["message"], fallback)
            self.assertEqual(str(error), fallback)
            self.assertNotIn("never-persist", json.dumps(error.to_dict()))
            self.assertNotIn("never-persist", str(error))

    def test_untrusted_rejections_do_not_retain_raw_traceback_causes(self):
        sentinel = "never-persist-traceback-secret"
        invalid_url = "https://example.invalid:" + sentinel + "/proof"
        cases = (
            lambda: WorkflowEvent(1, 0, "run-1", None, "run.initialized", sentinel, {}),
            lambda: RunState.new(invalid_url, "2026-07-14T00:00:00Z"),
            lambda: WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                                  "2026-07-14T00:00:00Z", {"note": invalid_url}),
            lambda: evidence_receipt("run-1", "test", invalid_url),
        )
        for reject in cases:
            with self.subTest(reject=reject):
                with self.assertRaises((InvalidSchemaError, UnsafePayloadError)) as raised:
                    reject()
                rendered = "".join(traceback.format_exception(
                    type(raised.exception), raised.exception, raised.exception.__traceback__,
                ))
                self.assertIsNone(raised.exception.__cause__)
                self.assertNotIn(sentinel, rendered)

    def test_error_details_hash_every_nonsensitive_string_and_stay_frozen(self):
        sentinel = "never-persist-arbitrary-plain-secret"
        digest = detail_digest(sentinel)
        error = UnsafePayloadError("invalid string field", {
            "context": sentinel,
            "mode": sentinel,
            "field": sentinel,
            "path": sentinel,
            "nested": [sentinel, {"password": sentinel}],
            "count": 3,
            "enabled": True,
            "missing": None,
        })
        self.assertEqual(error.details[detail_key_digest("context")], digest)
        self.assertEqual(error.details["mode"], digest)
        self.assertEqual(error.details["field"], digest)
        self.assertEqual(error.details["path"], digest)
        nested = error.details[detail_key_digest("nested")]
        self.assertEqual(nested[0], digest)
        self.assertEqual(nested[1][detail_key_digest("password")], "[REDACTED]")
        self.assertEqual(error.details[detail_key_digest("count")], 3)
        self.assertIs(error.details[detail_key_digest("enabled")], True)
        self.assertIsNone(error.details["missing"])
        with self.assertRaises(TypeError):
            nested[1][detail_key_digest("other")] = sentinel
        encoded = json.dumps(error.to_dict(), sort_keys=True)
        self.assertNotIn(sentinel, encoded)
        self.assertIn(digest, encoded)

    def test_error_detail_mapping_keys_with_uri_material_fail_closed(self):
        sentinel = "never-persist-detail-key"
        error = UnsafePayloadError("invalid string field", {
            "https://example.invalid/" + sentinel: "value",
        })
        encoded = json.dumps(error.to_dict(), sort_keys=True)
        self.assertNotIn(sentinel, encoded)
        self.assertEqual(
            error.details,
            {detail_key_digest("https://example.invalid/" + sentinel): "[REDACTED]"},
        )

    def test_unknown_error_detail_keys_are_hashed_at_every_depth(self):
        arbitrary = "never-persist-arbitrary-label"
        secret = "secret_never-persist-detail-key"
        uri = "https://example.invalid/never-persist-detail-key"
        error = UnsafePayloadError(schema.ErrorMessage.INVALID_STRING_FIELD, {
            "field": "safe-known-key",
            arbitrary: {"layer": {uri: "value"}, secret: "value"},
        })
        encoded = json.dumps(error.to_dict(), sort_keys=True)
        self.assertIn("field", error.details)
        self.assertIn(detail_key_digest(arbitrary), error.details)
        nested = error.details[detail_key_digest(arbitrary)]
        self.assertIn(detail_key_digest(secret), nested)
        self.assertEqual(nested[detail_key_digest(secret)], "[REDACTED]")
        self.assertIn(detail_key_digest(uri), nested[detail_key_digest("layer")])
        self.assertNotIn("never-persist", encoded)
        self.assertNotIn("example.invalid", encoded)

    def test_public_metadata_digest_tokens_are_idempotent_and_collisions_fail_closed(self):
        plaintext = "never-persist-collision-label"
        digest_shaped = detail_key_digest(plaintext)
        error = UnsafePayloadError(schema.ErrorMessage.INVALID_STRING_FIELD, {
            plaintext: "first",
            digest_shaped: "second",
        })
        self.assertEqual(error.details, {"detail": "[UNSAFE]"})

        safe = redaction.sanitize_public_metadata({plaintext: "first"})
        self.assertEqual(redaction.sanitize_public_metadata(safe), safe)
        self.assertIn(digest_shaped, safe)

    def test_hostile_str_subclass_keys_cannot_forge_known_key_classification(self):
        sentinel = "never-persist-hostile-detail-label"

        class HostileKey(str):
            def __hash__(self):
                return hash("field")

            def __eq__(self, other):
                return other == "field"

            def __str__(self):
                return "forged-field"

            def encode(self, *_args, **_kwargs):
                return b"field"

        key = HostileKey(sentinel)
        error = UnsafePayloadError(schema.ErrorMessage.INVALID_STRING_FIELD, {key: "value"})
        encoded = json.dumps(error.to_dict(), sort_keys=True)
        self.assertNotIn(sentinel, encoded)
        self.assertNotIn("forged-field", encoded)
        self.assertIn(detail_key_digest(sentinel), error.details)

    def test_all_receipt_paths_share_the_public_metadata_policy(self):
        fixture = "never-print-this-fixture"
        state_digest = "sha256:" + "a" * 64
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z",
                              {"note": fixture, "api_token": fixture})
        generic = json.loads(encode_receipt({"note": fixture, "api_token": fixture}))
        transition = transition_receipt(event, state_digest)
        evidence = evidence_receipt("run-1", "test", "receipt.json", metadata={
            "note": fixture, "api_token": fixture,
        })

        self.assertNotIn(fixture, json.dumps(generic, sort_keys=True))
        for receipt in (transition, evidence):
            self.assertNotIn(fixture.encode(), receipt)
        self.assertEqual(generic[detail_key_digest("note")], detail_digest(fixture))
        self.assertEqual(generic[detail_key_digest("api_token")], "[REDACTED]")
        parsed_transition = json.loads(transition)
        payload = parsed_transition["event"]["payload"]
        self.assertEqual(payload[detail_key_digest("note")], detail_digest(fixture))
        self.assertEqual(payload[detail_key_digest("api_token")], "[REDACTED]")
        self.assertEqual(parsed_transition["state_digest"], state_digest)

        for invalid in ("raw-state", "sha256:" + "A" * 64, detail_digest("state"), None):
            with self.subTest(invalid=invalid), self.assertRaises(UnsafePayloadError):
                transition_receipt(event, invalid)

    def test_receipt_factories_return_final_canonical_bytes(self):
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {})
        for receipt in (
            evidence_receipt("run-1", "test", "receipt.json"),
            transition_receipt(event, "sha256:" + "a" * 64),
        ):
            with self.subTest(receipt=receipt):
                self.assertIs(type(receipt), bytes)
                self.assertTrue(receipt.endswith(b"\n"))
                parsed = json.loads(receipt)
                canonical = (json.dumps(parsed, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":")) + "\n").encode("utf-8")
                self.assertEqual(receipt, canonical)

    def test_receipt_bytes_are_immutable_and_have_no_object_state(self):
        receipt = evidence_receipt("run-1", "test", "receipt.json")
        before = bytes(receipt)

        with self.assertRaises(TypeError):
            receipt[0] = 0
        self.assertFalse(hasattr(receipt, "__dict__"))
        self.assertEqual(receipt, before)

    def test_transition_receipt_bytes_are_immutable_and_have_no_object_state(self):
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {})
        receipt = transition_receipt(event, "sha256:" + "a" * 64)
        before = bytes(receipt)

        with self.assertRaises(TypeError):
            receipt[0] = 0
        self.assertFalse(hasattr(receipt, "__dict__"))
        self.assertEqual(receipt, before)

    def test_evidence_receipt_is_repeatably_deterministic(self):
        values = [
            evidence_receipt("run-1", "test", "receipt.json", metadata={"count": 1})
            for _ in range(3)
        ]
        self.assertEqual(values, [values[0]] * 3)

    def test_transition_receipt_is_repeatably_deterministic(self):
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {})
        values = [transition_receipt(event, "sha256:" + "a" * 64) for _ in range(3)]
        self.assertEqual(values, [values[0]] * 3)

    def test_evidence_receipt_digest_covers_digest_free_canonical_payload(self):
        receipt = json.loads(evidence_receipt("run-1", "test", "receipt.json"))
        digest = receipt.pop("digest")
        digest_free = (json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")) + "\n").encode("utf-8")
        self.assertEqual(digest, "sha256:" + hashlib.sha256(digest_free).hexdigest())

    def test_evidence_receipt_sanitizes_one_stateful_projection(self):
        class StatefulMapping(Mapping):
            def __init__(self):
                self.reads = 0

            def __getitem__(self, key):
                if key != "note":
                    raise KeyError(key)
                self.reads += 1
                return "value-" + str(self.reads)

            def __iter__(self):
                return iter(("note",))

            def __len__(self):
                return 1

        nested = StatefulMapping()
        receipt = json.loads(evidence_receipt(
            "run-1", "test", "receipt.json", metadata={"nested": nested},
        ))
        digest = receipt.pop("digest")
        digest_free = (json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")) + "\n").encode("utf-8")

        self.assertEqual(nested.reads, 1)
        self.assertEqual(digest, "sha256:" + hashlib.sha256(digest_free).hexdigest())

    def test_factory_bytes_are_not_a_trusted_encode_receipt_input(self):
        receipt = evidence_receipt("run-1", "test", "receipt.json")
        with self.assertRaises(UnsafePayloadError):
            encode_receipt(receipt)

        raw = encode_receipt(json.loads(receipt))
        self.assertNotEqual(raw, receipt)
        self.assertNotIn("run_id", json.loads(raw))

    def test_evidence_receipt_contains_complete_final_payload(self):
        receipt = json.loads(evidence_receipt("run-1", "test", "receipt.json"))
        self.assertEqual(set(receipt), set(receipts.EVIDENCE_RECEIPT_FIELDS))
        self.assertRegex(receipt["digest"], r"\Asha256:[0-9a-f]{64}\Z")

    def test_transition_receipt_contains_complete_final_payload(self):
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {})
        receipt = json.loads(transition_receipt(event, "sha256:" + "a" * 64))
        self.assertEqual(set(receipt), set(receipts.TRANSITION_RECEIPT_FIELDS))
        self.assertEqual(set(receipt["event"]), set(schema.WORKFLOW_EVENT_FIELDS))

    def test_receipt_factory_bytes_are_scanner_ready_json(self):
        receipt = evidence_receipt("run-1", "test", "receipt.json")
        self.assertEqual(json.loads(receipt.decode("utf-8"))["receipt_type"], "evidence")

    def test_receipts_use_the_shared_redaction_traversal(self):
        encoded = encode_receipt({"note": "shared traversal"})
        self.assertEqual(json.loads(encoded)[detail_key_digest("note")],
                         detail_digest("shared traversal"))

    def test_raw_mapping_encode_receipt_runs_one_shared_traversal(self):
        with mock.patch("workflow_kernel.receipts.apply_json_policy",
                        wraps=redaction.apply_json_policy) as traversal:
            encoded = encode_receipt({"note": "one traversal"})

        self.assertEqual(traversal.call_count, 1)
        self.assertEqual(json.loads(encoded)[detail_key_digest("note")],
                         detail_digest("one traversal"))

    def test_raw_receipt_cannot_infer_safe_provenance_from_schema_shapes(self):
        receipt = evidence_receipt("run-1", "test", "receipt.json")
        raw = encode_receipt(json.loads(receipt))

        self.assertNotEqual(raw, receipt)
        self.assertNotIn("run_id", json.loads(raw))

    def test_raw_evidence_key_does_not_select_reference_schema_policy(self):
        source = "/caller-controlled/absolute-path.json"
        encoded = json.loads(encode_receipt({"evidence": [source]}))

        self.assertEqual(
            encoded[detail_key_digest("evidence")],
            [detail_digest(source)],
        )

    def test_raw_digest_key_and_marker_literals_are_re_digested(self):
        digest_key = detail_key_digest("caller-controlled-key")
        encoded = json.loads(encode_receipt({
            digest_key: "[REDACTED]",
            "marker": "[UNSAFE]",
            "api_token": "[UNSAFE]",
        }))

        self.assertEqual(encoded[detail_key_digest(digest_key)], detail_digest("[REDACTED]"))
        self.assertEqual(encoded[detail_key_digest("marker")], detail_digest("[UNSAFE]"))
        self.assertEqual(encoded[detail_key_digest("api_token")], "[REDACTED]")

    def test_receipt_sanitizer_composes_uri_normalization_and_value_digest_once(self):
        self.assertTrue(hasattr(receipts, "normalize_durable_string"))
        source = "See https://example.invalid/one-pass now"
        with mock.patch(
                "workflow_kernel.receipts.normalize_durable_string",
                wraps=redaction.normalize_durable_string,
        ) as normalize:
            encoded = encode_receipt({"note": source})

        self.assertEqual([call.args[0] for call in normalize.call_args_list].count(source), 1)
        normalized = redaction.normalize_durable_string(source)
        self.assertEqual(json.loads(encoded)[detail_key_digest("note")], detail_digest(normalized))

    def test_receipt_and_event_field_vocabularies_match_runtime_schemas(self):
        for name in ("ReceiptField", "EVIDENCE_RECEIPT_FIELDS", "TRANSITION_RECEIPT_FIELDS"):
            self.assertTrue(hasattr(receipts, name), name)
        self.assertTrue(hasattr(schema, "WORKFLOW_EVENT_FIELDS"))
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {})
        transition = transition_receipt(event, "sha256:" + "a" * 64)
        evidence = evidence_receipt("run-1", "test", "receipt.json")

        self.assertEqual(set(event.to_dict()), set(schema.WORKFLOW_EVENT_FIELDS))
        self.assertEqual(set(json.loads(transition)), set(receipts.TRANSITION_RECEIPT_FIELDS))
        self.assertEqual(set(json.loads(evidence)), set(receipts.EVIDENCE_RECEIPT_FIELDS))
        self.assertEqual({field.value for field in receipts.ReceiptField},
                         set(receipts.EVIDENCE_RECEIPT_FIELDS) | set(receipts.TRANSITION_RECEIPT_FIELDS))

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
        parsed_receipt = json.loads(receipt)

        self.assertEqual(event.payload["evidence"], (expected,))
        self.assertEqual(parsed_receipt["reference"], expected)
        for encoded in (encode_event(event), receipt):
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
        source_digest = detail_digest(redaction.normalize_durable_string(source_url))
        nested_digest = detail_digest(redaction.normalize_durable_string(nested_url))

        receipt = evidence_receipt("run-1", "test", "receipt.json", metadata={
            "source_url": source_url,
            "nested": {"arbitrary_name": nested_url},
        })

        metadata = json.loads(receipt)["metadata"]
        self.assertEqual(metadata[detail_key_digest("source_url")], source_digest)
        self.assertEqual(
            metadata[detail_key_digest("nested")][detail_key_digest("arbitrary_name")],
            nested_digest,
        )
        self.assertNotIn(sentinel.encode(), receipt)
        self.assertNotIn(b"metadata.example.invalid", receipt)
        self.assertNotIn(b"nested.example.invalid", receipt)

    def test_standalone_uri_and_content_id_whitespace_is_rejected_across_outputs(self):
        digest = "sha256:" + "a" * 64
        for value in (" https://example.invalid/proof ", " //example.invalid/proof ",
                      "\t" + digest, digest + "\n"):
            with self.subTest(event=value), self.assertRaises(UnsafePayloadError):
                WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {"source": value})
            with self.subTest(receipt=value), self.assertRaises(UnsafePayloadError):
                encode_receipt({"source": value})
            with self.subTest(state=value), self.assertRaises(UnsafePayloadError):
                RunState.new(value, "2026-07-14T00:00:00Z")

    def test_non_hierarchical_uri_schemes_fail_closed_across_outputs(self):
        for value in (
            "data:text/plain,never-persist-this-fixture",
            "javascript:alert(never-persist-this-fixture)",
            "mailto:never-persist-this-fixture@example.invalid",
            "urn:example:never-persist-this-fixture",
            "s3:bucket/never-persist-this-fixture",
        ):
            with self.subTest(event=value), self.assertRaises(UnsafePayloadError):
                WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {"source": value})
            with self.subTest(receipt=value), self.assertRaises(UnsafePayloadError):
                encode_receipt({"source": value})
            with self.subTest(state=value), self.assertRaises(UnsafePayloadError):
                RunState.new(value, "2026-07-14T00:00:00Z")

    def test_embedded_http_url_is_digested_across_event_receipt_and_state(self):
        sentinel = "never-persist-this-embedded-token"
        url = "https://example.invalid/proof/" + sentinel
        digest = "url-sha256:" + hashlib.sha256(url.encode("utf-8")).hexdigest()
        prose = "See " + url + " for context."
        normalized = "See " + digest + " for context."

        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {"note": prose})
        receipt = encode_receipt({"note": prose})
        state = RunState.new(prose, "2026-07-14T00:00:00Z")

        self.assertEqual(event.payload["note"], normalized)
        self.assertEqual(json.loads(receipt)[detail_key_digest("note")], detail_digest(normalized))
        self.assertEqual(state.run_id, normalized)
        for encoded in (encode_event(event), encode_state(state)):
            self.assertNotIn(sentinel.encode(), encoded)
            self.assertNotIn(b"example.invalid", encoded)
            self.assertNotIn(url.encode(), encoded)
            self.assertIn(digest.encode(), encoded)
        self.assertNotIn(sentinel.encode(), receipt)

    def test_network_path_urls_are_digested_across_event_receipt_and_state(self):
        first = "//one.example.invalid/proof/never-persist-network-one"
        second = "//two.example.invalid/report/never-persist-network-two"
        first_digest = "url-sha256:" + hashlib.sha256(first.encode("utf-8")).hexdigest()
        second_digest = "url-sha256:" + hashlib.sha256(second.encode("utf-8")).hexdigest()
        source = "Compare <" + first + ">, then (" + second + ")."
        normalized = "Compare <" + first_digest + ">, then (" + second_digest + ")."

        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {"note": source})
        receipt = encode_receipt({"note": source})
        state = RunState.new(source, "2026-07-14T00:00:00Z")

        self.assertEqual(event.payload["note"], normalized)
        self.assertEqual(json.loads(receipt)[detail_key_digest("note")], detail_digest(normalized))
        self.assertEqual(state.run_id, normalized)
        self.assertNotEqual(encode_receipt(json.loads(receipt)), receipt)
        for encoded in (encode_event(event), encode_state(state)):
            self.assertNotIn(b"example.invalid", encoded)
            self.assertNotIn(b"never-persist-network", encoded)
            self.assertIn(first_digest.encode(), encoded)
            self.assertIn(second_digest.encode(), encoded)
        self.assertNotIn(b"never-persist-network", receipt)

    def test_standalone_network_path_url_is_digested_and_idempotent(self):
        source = "//example.invalid/proof/never-persist-standalone"
        digest = "url-sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()

        self.assertEqual(redaction.normalize_durable_string(source), digest)
        self.assertEqual(redaction.normalize_durable_string(digest), digest)

    def test_unsafe_network_path_urls_fail_without_echoing_values(self):
        sentinel = "never-persist-network-credential"
        values = (
            "//user:" + sentinel + "@example.invalid/proof",
            "//example.invalid:invalid/proof/" + sentinel,
            "//example.invalid/proof?access_token=" + sentinel,
            "//example.invalid/proof#" + sentinel,
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(UnsafePayloadError) as event_error:
                    WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                                  "2026-07-14T00:00:00Z", {"note": value})
                with self.assertRaises(UnsafePayloadError) as receipt_error:
                    encode_receipt({"note": "See <" + value + "> now"})
                with self.assertRaises(UnsafePayloadError) as state_error:
                    RunState.new(value, "2026-07-14T00:00:00Z")
                for raised in (event_error, receipt_error, state_error):
                    self.assertNotIn(sentinel, json.dumps(raised.exception.to_dict()))

    def test_uri_prefix_punctuation_and_digits_cannot_bypass_durable_outputs(self):
        urls = (
            "https://example.invalid/never-persist-dot",
            "https://example.invalid/never-persist-hyphen",
            "https://example.invalid/never-persist-plus",
            "https://example.invalid/never-persist-digit",
            "https://example.invalid/never-persist-adjacent",
        )
        prefixes = (".", "-", "+", "7", "7.+-")
        for prefix, url in zip(prefixes, urls):
            digest = "url-sha256:" + hashlib.sha256(url.encode("utf-8")).hexdigest()
            source = "See " + prefix + url + " now"
            normalized = "See " + prefix + digest + " now"

            event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                                  "2026-07-14T00:00:00Z", {"note": source})
            receipt = encode_receipt({"note": source})
            state = RunState.new(source, "2026-07-14T00:00:00Z")

            self.assertEqual(event.payload["note"], normalized)
            self.assertEqual(json.loads(receipt)[detail_key_digest("note")], detail_digest(normalized))
            self.assertEqual(state.run_id, normalized)
            for encoded in (encode_event(event), encode_state(state)):
                self.assertNotIn(url.encode(), encoded)
                self.assertNotIn(b"never-persist-", encoded)
                self.assertIn(digest.encode(), encoded)
            self.assertNotIn(b"never-persist-", receipt)

    def test_prefixed_unsupported_uri_schemes_fail_closed_across_outputs(self):
        values = (
            "See +data:text/plain,never-persist-data now",
            "See -javascript:alert(never-persist-script) now",
            "See 7mailto:never-persist-mail@example.invalid now",
            "See .+-urn:example:never-persist-urn now",
        )
        for value in values:
            with self.subTest(event=value), self.assertRaises(UnsafePayloadError):
                WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {"note": value})
            with self.subTest(receipt=value), self.assertRaises(UnsafePayloadError):
                encode_receipt({"note": value})
            with self.subTest(state=value), self.assertRaises(UnsafePayloadError):
                RunState.new(value, "2026-07-14T00:00:00Z")

    def test_symmetric_delimiters_and_angle_content_ids_are_preserved(self):
        first = "https://one.example.invalid/path"
        second = "http://two.example.invalid/report"
        first_digest = "url-sha256:" + hashlib.sha256(first.encode("utf-8")).hexdigest()
        second_digest = "url-sha256:" + hashlib.sha256(second.encode("utf-8")).hexdigest()
        content_digest = "sha256:" + "a" * 64
        url_digest = "url-sha256:" + "b" * 64
        source = "Compare <" + first + ">, then \"([{<" + second + ">}])\"; keep <" + content_digest + "> and <" + url_digest + ">."
        normalized = "Compare <" + first_digest + ">, then \"([{<" + second_digest + ">}])\"; keep <" + content_digest + "> and <" + url_digest + ">."

        try:
            event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                                  "2026-07-14T00:00:00Z", {"note": source})
            receipt = encode_receipt({"note": source})
            state = RunState.new(source, "2026-07-14T00:00:00Z")
        except UnsafePayloadError as exc:
            self.fail("symmetric URI delimiters were treated as URI bytes: " + exc.code)

        self.assertEqual(event.payload["note"], normalized)
        self.assertEqual(json.loads(receipt)[detail_key_digest("note")], detail_digest(normalized))
        self.assertEqual(state.run_id, normalized)
        self.assertNotEqual(encode_receipt(json.loads(receipt)), receipt)
        for encoded in (encode_event(event), encode_state(state)):
            self.assertNotIn(first.encode(), encoded)
            self.assertNotIn(second.encode(), encoded)
            self.assertIn(("<" + content_digest + ">").encode(), encoded)
            self.assertIn(("<" + url_digest + ">").encode(), encoded)
        self.assertNotIn(first.encode(), receipt)
        self.assertNotIn(second.encode(), receipt)

    def test_no_space_colon_tokens_fail_closed_but_prose_labels_remain(self):
        preserved = "Note: see the local report"
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", {"note": preserved})
        self.assertEqual(event.payload["note"], preserved)

        rejected = "Note:see-the-local-report"
        with self.assertRaises(UnsafePayloadError):
            WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                          "2026-07-14T00:00:00Z", {"note": rejected})
        with self.assertRaises(UnsafePayloadError):
            encode_receipt({"note": rejected})
        with self.assertRaises(UnsafePayloadError):
            RunState.new(rejected, "2026-07-14T00:00:00Z")

    def test_maximum_length_uri_scans_have_bounded_character_operations(self):
        values = (
            CountingStr("a" * redaction.MAX_STRING_LENGTH),
            CountingStr(("//host.example/path " * 4_000)[:redaction.MAX_STRING_LENGTH]),
        )
        for source in values:
            normalized = redaction.normalize_durable_string(source)
            self.assertGreaterEqual(source.operations, len(source))
            self.assertLessEqual(source.operations, len(source) * 16)
            self.assertNotIn("host.example", normalized)

    def test_evidence_normalization_stops_at_the_shared_item_bound(self):
        calls = 0
        original = redaction.normalize_evidence_reference

        def counted(value):
            nonlocal calls
            calls += 1
            return original(value)

        with mock.patch("workflow_kernel.redaction.normalize_evidence_reference",
                        side_effect=counted):
            with self.assertRaises(TypeError):
                redaction.freeze_json({"evidence": ["a"] * 200}, max_items=3)
        self.assertLessEqual(calls, 3)

    def test_uri_bearing_mapping_keys_are_rejected_without_rewriting(self):
        sentinel = "never-persist-mapping-key"
        keys = (
            "https://example.invalid/" + sentinel,
            "data:text/plain," + sentinel,
            "//example.invalid/" + sentinel,
            "https://user:password@example.invalid/path?token=" + sentinel,
        )
        for key in keys:
            with self.subTest(key=key):
                with self.assertRaises(UnsafePayloadError) as event_error:
                    WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                                  "2026-07-14T00:00:00Z", {"nested": {key: "value"}})
                with self.assertRaises(UnsafePayloadError) as receipt_error:
                    encode_receipt({"nested": {key: "value"}})
                error = UnsafePayloadError("unsafe", {"nested": {key: "value"}})
                encoded_error = json.dumps(error.to_dict(), sort_keys=True)
                for raised in (event_error, receipt_error):
                    self.assertNotIn(sentinel, json.dumps(raised.exception.to_dict()))
                self.assertNotIn(sentinel, encoded_error)
                self.assertNotIn(key, encoded_error)

    def test_uri_mapping_key_collisions_reject_instead_of_rewriting(self):
        source = "https://example.invalid/never-persist-collision"
        digest = "url-sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()
        payload = {source: "unsafe", digest: "safe"}

        with self.assertRaises(UnsafePayloadError) as event_error:
            WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                          "2026-07-14T00:00:00Z", payload)
        with self.assertRaises(UnsafePayloadError) as receipt_error:
            encode_receipt(payload)
        for raised in (event_error, receipt_error):
            encoded = json.dumps(raised.exception.to_dict(), sort_keys=True)
            self.assertNotIn(source, encoded)
            self.assertNotIn("never-persist-collision", encoded)

    def test_uri_bearing_node_mapping_keys_are_rejected_from_state(self):
        keys = (
            "https://example.invalid/never-persist-state-key",
            "data:text/plain,never-persist-state-key",
            "//example.invalid/never-persist-state-key",
            "https://user:password@example.invalid/path?token=never-persist-state-key",
        )
        for key in keys:
            data = RunState.new("run-1", "2026-07-14T00:00:00Z").to_dict()
            data["nodes"] = {
                key: {"node_id": "safe-node", "status": "pending", "dependencies": [], "evidence": []},
            }

            with self.subTest(key=key), self.assertRaises(
                    (InvalidSchemaError, UnsafePayloadError)) as raised:
                RunState.from_dict(data)
            encoded = json.dumps(raised.exception.to_dict(), sort_keys=True)
            self.assertNotIn(key, encoded)
            self.assertNotIn("never-persist-state-key", encoded)

    def test_state_node_keys_use_one_post_init_invariant_boundary(self):
        data = RunState.new("run-1", "2026-07-14T00:00:00Z").to_dict()
        data["nodes"] = {
            "node-1": {"node_id": "node-1", "status": "pending", "dependencies": [], "evidence": []},
        }
        with mock.patch("workflow_kernel.schema.validate_durable_key",
                        wraps=schema.validate_durable_key) as validate:
            RunState.from_dict(data)
        node_key_calls = [call for call in validate.call_args_list if call.args == ("node-1",)]
        self.assertEqual(len(node_key_calls), 1)

    def test_multiple_embedded_urls_preserve_punctuation_and_raw_receipts_stay_untrusted(self):
        first = "https://one.example.invalid/path"
        second = "http://two.example.invalid/report"
        first_digest = "url-sha256:" + hashlib.sha256(first.encode("utf-8")).hexdigest()
        second_digest = "url-sha256:" + hashlib.sha256(second.encode("utf-8")).hexdigest()
        prose = "Compare \"" + first + "\", then (" + second + ")."
        normalized = "Compare \"" + first_digest + "\", then (" + second_digest + ")."

        first_event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                                    "2026-07-14T00:00:00Z", {"note": prose})
        second_event = WorkflowEvent.from_dict(first_event.to_dict())
        first_receipt = encode_receipt({"note": prose})
        second_receipt = encode_receipt(json.loads(first_receipt))

        self.assertEqual(first_event.payload["note"], normalized)
        self.assertEqual(second_event.payload["note"], normalized)
        self.assertNotEqual(first_receipt, second_receipt)
        self.assertEqual(encode_event(first_event), encode_event(second_event))

    def test_embedded_unsafe_and_unsupported_uris_fail_without_echoing_values(self):
        sentinel = "never-persist-this-unsafe-token"
        values = (
            "See https://user:" + sentinel + "@example.invalid/proof now",
            "See https://example.invalid/proof?access_token=" + sentinel + " now",
            "See https://example.invalid/proof#" + sentinel + " now",
            "See data:text/plain," + sentinel + " now",
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(UnsafePayloadError) as event_error:
                    WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                                  "2026-07-14T00:00:00Z", {"note": value})
                with self.assertRaises(UnsafePayloadError) as receipt_error:
                    encode_receipt({"note": value})
                with self.assertRaises(UnsafePayloadError) as state_error:
                    RunState.new(value, "2026-07-14T00:00:00Z")
                for raised in (event_error, receipt_error, state_error):
                    self.assertNotIn(sentinel, json.dumps(raised.exception.to_dict()))

    def test_non_uri_prose_and_local_paths_remain_unchanged(self):
        preserved = {
            "note": "See the proof for context",
            "local": "artifacts/review/report.json",
        }
        event = WorkflowEvent(1, 0, "run-1", None, "run.initialized",
                              "2026-07-14T00:00:00Z", preserved)
        self.assertEqual(event.to_dict()["payload"], preserved)

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
                  "s3://bucket/report.json", "sha256:" + "A" * 64,
                  "value-sha256:" + "a" * 64, "key-sha256:" + "a" * 64)
        for reference in unsafe:
            with self.subTest(rejected=reference), self.assertRaises(UnsafePayloadError):
                WorkflowEvent(1, 0, "run-1", None, "evidence.recorded",
                              "2026-07-14T00:00:00Z", {"evidence": [reference]})

    def test_corrupt_state_error_has_stable_public_code(self):
        self.assertEqual(CorruptStateError("bad state").code, "corrupt_state")

    def test_error_details_sensitive_and_uri_values_are_safely_contained(self):
        fixture = "never-print-this-credential"
        error = UnsafePayloadError("unsafe", {
            "authorization": "Bearer " + fixture,
            "reference": "https://user:" + fixture + "@example.invalid/proof",
        })
        encoded = json.dumps(error.to_dict(), sort_keys=True)
        self.assertNotIn(fixture, encoded)
        self.assertEqual(error.details[detail_key_digest("authorization")], "[REDACTED]")
        self.assertEqual(
            error.details[detail_key_digest("reference")],
            detail_digest("https://user:" + fixture + "@example.invalid/proof"),
        )

    def test_public_metadata_sanitizer_returns_plain_secret_safe_containers(self):
        sentinel = "never-persist-public-metadata"
        uri_key = "https://example.invalid/" + sentinel
        safe = redaction.sanitize_public_metadata({
            "note": "Bearer " + sentinel,
            "plain": sentinel,
            "api_token": sentinel,
            "marker": "[REDACTED]",
            "unsafe_marker": "[UNSAFE]",
            uri_key: "value",
        })
        encoded = json.dumps(safe, sort_keys=True)
        self.assertIs(type(safe), dict)
        self.assertNotIn(sentinel, encoded)
        self.assertEqual(safe[detail_key_digest("note")], detail_digest("Bearer " + sentinel))
        self.assertEqual(safe[detail_key_digest("plain")], detail_digest(sentinel))
        self.assertEqual(safe[detail_key_digest("api_token")], "[REDACTED]")
        self.assertEqual(safe[detail_key_digest("marker")], detail_digest("[REDACTED]"))
        self.assertEqual(safe[detail_key_digest("unsafe_marker")], detail_digest("[UNSAFE]"))
        self.assertIn(detail_key_digest(uri_key), safe)
        self.assertEqual(redaction.sanitize_public_metadata(safe), safe)

    def test_evidence_receipt_sanitizes_metadata_and_top_level_caller_strings(self):
        sentinel = "[REDACTED]"
        receipt = evidence_receipt(
            sentinel,
            "[UNSAFE]",
            "receipt.json",
            metadata={"note": sentinel, "plain": "[UNSAFE]", "api_token": sentinel},
        )
        parsed = json.loads(receipt)
        self.assertEqual(parsed["run_id"], detail_digest(sentinel))
        self.assertEqual(parsed["evidence_type"], detail_digest("[UNSAFE]"))
        self.assertEqual(parsed["metadata"][detail_key_digest("note")], detail_digest(sentinel))
        self.assertEqual(parsed["metadata"][detail_key_digest("plain")], detail_digest("[UNSAFE]"))
        self.assertEqual(parsed["metadata"][detail_key_digest("api_token")], "[REDACTED]")
        self.assertEqual(evidence_receipt(
            sentinel,
            "[UNSAFE]",
            "receipt.json",
            metadata={"note": sentinel, "plain": "[UNSAFE]", "api_token": sentinel},
        ), receipt)

        generic = encode_receipt({"note": "[UNSAFE]"})
        self.assertEqual(json.loads(generic)[detail_key_digest("note")], detail_digest("[UNSAFE]"))

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
        self.assertEqual(raised.exception.details["reason_code"], detail_digest("evidence_limit_exceeded"))
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
        self.assertEqual(raised.exception.details["reason_code"], detail_digest("evidence_limit_exceeded"))
        self.assertEqual(raised.exception.details["limit_items"], 2)
