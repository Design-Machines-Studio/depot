import ast
import hashlib
import inspect
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from workflow_kernel import redaction, schema
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

    def test_error_message_catalog_covers_internal_kernel_errors(self):
        catalog = getattr(schema, "SAFE_ERROR_MESSAGES", frozenset())
        error_names = {
            "KernelError", "InvalidSchemaError", "CorruptEventError", "CorruptStateError",
            "SequenceConflictError", "RevisionConflictError", "LeaseConflictError",
            "IllegalTransitionError", "MissingEvidenceError", "UnsafePayloadError",
        }
        package = Path(schema.__file__).parent
        observed = set()
        for path in package.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if (not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name)
                        or node.func.id not in error_names or not node.args):
                    continue
                message = node.args[0]
                self.assertIsInstance(message, ast.Constant, path.name + ":" + str(node.lineno))
                self.assertIsInstance(message.value, str, path.name + ":" + str(node.lineno))
                observed.add(message.value)
        self.assertTrue(observed)
        self.assertEqual(observed - catalog, set())
        for message in catalog:
            error = UnsafePayloadError(message)
            self.assertEqual(error.message, message)
            self.assertEqual(error.args, (message,))
            self.assertEqual(str(error), message)

    def test_error_message_and_details_cannot_be_mutated_after_construction(self):
        message = "invalid string field"
        error = UnsafePayloadError(message, {"field": "safe"})
        sentinel = "never-persist-mutated-error"

        with self.assertRaises(AttributeError):
            error.message = sentinel
        with self.assertRaises(AttributeError):
            error.args = (sentinel,)
        with self.assertRaises(AttributeError):
            error._safe_message = sentinel
        with self.assertRaises(AttributeError):
            error.details = {"password": sentinel}
        with self.assertRaises(TypeError):
            error.details["password"] = sentinel
        with self.assertRaises(AttributeError):
            del error._safe_message
        with self.assertRaises(AttributeError):
            del error._details

        self.assertEqual(error.message, message)
        self.assertEqual(error.args, (message,))
        self.assertEqual(str(error), message)
        self.assertNotIn(sentinel, json.dumps(error.to_dict()))

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
        self.assertEqual(json.loads(receipt)["note"], normalized)
        self.assertEqual(state.run_id, normalized)
        for encoded in (encode_event(event), receipt, encode_state(state)):
            self.assertNotIn(sentinel.encode(), encoded)
            self.assertNotIn(b"example.invalid", encoded)
            self.assertNotIn(url.encode(), encoded)
            self.assertIn(digest.encode(), encoded)

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
        self.assertEqual(json.loads(receipt)["note"], normalized)
        self.assertEqual(state.run_id, normalized)
        self.assertEqual(encode_receipt(json.loads(receipt)), receipt)
        for encoded in (encode_event(event), receipt, encode_state(state)):
            self.assertNotIn(b"example.invalid", encoded)
            self.assertNotIn(b"never-persist-network", encoded)
            self.assertIn(first_digest.encode(), encoded)
            self.assertIn(second_digest.encode(), encoded)

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
            self.assertEqual(json.loads(receipt)["note"], normalized)
            self.assertEqual(state.run_id, normalized)
            for encoded in (encode_event(event), receipt, encode_state(state)):
                self.assertNotIn(url.encode(), encoded)
                self.assertNotIn(b"never-persist-", encoded)
                self.assertIn(digest.encode(), encoded)

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
        self.assertEqual(json.loads(receipt)["note"], normalized)
        self.assertEqual(state.run_id, normalized)
        self.assertEqual(encode_receipt(json.loads(receipt)), receipt)
        for encoded in (encode_event(event), receipt, encode_state(state)):
            self.assertNotIn(first.encode(), encoded)
            self.assertNotIn(second.encode(), encoded)
            self.assertIn(("<" + content_digest + ">").encode(), encoded)
            self.assertIn(("<" + url_digest + ">").encode(), encoded)

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

    def test_production_uri_helpers_return_only_domain_results(self):
        source = "See https://example.invalid/path now"
        self.assertIsInstance(redaction._normalize_uri_tokens(source), str)
        self.assertIsInstance(redaction._reject_remaining_uri_shapes("plain text"), type(None))
        self.assertIsInstance(redaction._uri_token_end(source, 4, 32), int)

    def test_uri_span_iterator_is_shared_domain_output(self):
        source = "See <https://one.example/path>, then (//two.example/report)."
        self.assertTrue(hasattr(redaction, "_iter_uri_token_spans"))
        spans = tuple(redaction._iter_uri_token_spans(source))
        tokens = tuple(source[start:end] for start, end, _ in spans)
        self.assertEqual(tokens, ("https://one.example/path", "//two.example/report"))

    def test_timestamp_has_a_raw_validator_without_string_mode_flag(self):
        self.assertTrue(hasattr(schema, "_validated_string"))
        self.assertNotIn("normalize_uris", inspect.signature(schema._string).parameters)
        timestamp = "2026-07-14T00:00:00Z"
        self.assertEqual(schema._timestamp(timestamp), timestamp)

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

    def test_multiple_embedded_urls_preserve_punctuation_and_are_idempotent(self):
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
        self.assertEqual(first_receipt, second_receipt)
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
