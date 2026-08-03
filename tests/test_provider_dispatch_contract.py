import copy
import json
import struct
import unittest

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.provider_dispatch import (
    EXIT_AUTHORIZATION_DECLINED, EXIT_DISCLOSURE_DECLINED,
    EXIT_PROVIDER_FAILURE, EXIT_RESULT_VERIFICATION, EXIT_UNKNOWN,
    EXIT_VERIFIED, FROZEN_EXCHANGE, FROZEN_TRUST_CHAIN, MAX_FRAME_BYTES,
    MAX_REQUEST_BYTES, MAPPING, OPERATION_FAMILY, PRODUCTION_INELIGIBLE_DOMAIN,
    PROTOCOL, SUBSTRATE_AUTHORITY, FakeBroker, ProviderDispatchError,
    build_openrouter_body, canonical_json, encode_request, frame32, frame64,
    parse_canonical_json, sha256, signature_input, validate_authority_binding,
    validate_exchange, validate_request, validate_result, validate_status,
    verify_terminal_result,
)


REQUEST_SCHEMA = KERNEL_REFERENCES / "provider-dispatch-request-schema.json"
RESULT_SCHEMA = KERNEL_REFERENCES / "provider-dispatch-result-schema.json"
STATUS_SCHEMA = KERNEL_REFERENCES / "provider-dispatch-status-schema.json"
EXCHANGE_SCHEMA = KERNEL_REFERENCES / "provider-dispatch-exchange-schema.json"
D = "sha256:" + "1" * 64
SIG = "ed25519:" + "A" * 86


def limits():
    return {
        "max_request_bytes": 8388608, "max_response_bytes": 8388608,
        "max_parts": 256, "max_pending_per_peer": 4,
        "max_pending_per_repository": 16, "max_pending_per_daemon": 64,
    }


def scope():
    return {
        "repository": "design-machines/depot", "run_id": "run-01",
        "lane": "assessment", "candidate": "candidate-01",
        "workload": "pipeline-assessment",
    }


def request(parts=(b"system\n", b"user \xf0\x9f\x8c\x8d\\\"\n"), roles=("system", "user")):
    return {
        "schema_version": 1, "protocol": PROTOCOL, "mapping": MAPPING,
        "operation_family": OPERATION_FAMILY,
        "substrate_authority": SUBSTRATE_AUTHORITY,
        "destination": "https://openrouter.ai", "method": "POST",
        "path": "/api/v1/chat/completions",
        "models": ["openai/gpt-5.6", "z-ai/glm-5.2"],
        "parts": [
            {"role": role, "content_length": len(raw), "content_sha256": sha256(raw)}
            for role, raw in zip(roles, parts, strict=True)
        ],
        "scope": scope(),
        "authority": {
            "daemon_build_sha256": D, "scanner_build_sha256": D,
            "policy_sha256": D, "nonce": "nonce-01", "sequence": 7,
            "boot_id": "boot-01", "session_id": "session-01",
            "connection_nonce_sha256": D,
            "issued_at": "2026-08-03T00:00:00Z",
            "expires_at": "2026-08-03T00:02:00Z",
        },
        "limits": limits(),
    }


def challenge(req, body):
    authority = req["authority"]
    return {
        "schema_version": 1, "protocol": PROTOCOL, "mapping": MAPPING,
        "operation_family": OPERATION_FAMILY,
        "substrate_authority": SUBSTRATE_AUTHORITY,
        "transaction_id": "transaction-01",
        "connection_nonce_sha256": authority["connection_nonce_sha256"],
        "peer_uid": 501, "peer_pid": 4321,
        "request_body_sha256": sha256(body),
        "destination": req["destination"], "method": req["method"],
        "path": req["path"], "models": req["models"], "scope": req["scope"],
        "daemon_build_sha256": authority["daemon_build_sha256"],
        "scanner_build_sha256": authority["scanner_build_sha256"],
        "policy_sha256": authority["policy_sha256"], "nonce": authority["nonce"],
        "sequence": authority["sequence"], "boot_id": authority["boot_id"],
        "session_id": authority["session_id"], "issued_at": authority["issued_at"],
        "expires_at": authority["expires_at"], "limits": req["limits"],
        "result_public_key": "fixture-result-key-01",
    }


def result(req, chall, response=b'{"ok":true}'):
    return {
        "schema_version": 1, "protocol": PROTOCOL,
        "operation_family": OPERATION_FAMILY,
        "substrate_authority": SUBSTRATE_AUTHORITY,
        "outcome": "verified", "exit_code": 0,
        "request_body_sha256": chall["request_body_sha256"],
        "response_sha256": sha256(response), "response_length": len(response),
        "part_count": len(req["parts"]), "models": req["models"],
        "selected_model": req["models"][0], "provider": "openrouter",
        "scope": req["scope"], "sequence": req["authority"]["sequence"],
        "issued_at": req["authority"]["issued_at"],
        "completed_at": "2026-08-03T00:00:03Z",
        "challenge_sha256": sha256(canonical_json(chall)),
        "fido_assertion_sha256": D,
        "result_public_key_sha256": sha256(chall["result_public_key"].encode()),
        "cleanup": {"reservation": "consumed", "connection": "closed", "content_buffer": "discarded"},
        "signature": SIG,
    }


class ProviderDispatchContractTests(unittest.TestCase):
    """REQ-M0-01..11 and stable CHK-M0 vectors."""

    def setUp(self):
        self.parts = (b"system\n", b"user \xf0\x9f\x8c\x8d\\\"\n")
        self.request = request(self.parts)
        self.body = build_openrouter_body(self.request, self.parts)
        self.challenge = challenge(self.request, self.body)
        self.ack = {
            "schema_version": 1, "protocol": PROTOCOL, "type": "consent_ack",
            "challenge_sha256": sha256(canonical_json(self.challenge)),
        }
        self.response = b'{"ok":true}'
        self.result = result(self.request, self.challenge, self.response)

    def test_req_m0_01_request_and_challenge_bind_every_authority_field(self):
        validate_request(self.request, self.parts)
        validate_authority_binding(self.request, self.body, self.challenge, self.ack)
        for field in (
            "repository", "run_id", "lane", "candidate", "workload",
        ):
            mutation = copy.deepcopy(self.challenge)
            mutation["scope"][field] += "-changed"
            with self.subTest(field=field), self.assertRaisesRegex(ProviderDispatchError, "terminal_binding_invalid"):
                validate_authority_binding(self.request, self.body, mutation, self.ack)

    def test_req_m0_02_result_is_structurally_content_free(self):
        self.assertEqual(validate_result(self.result), self.result)
        forbidden = {"content", "prompt", "response", "credential", "api_key", "socket_path"}
        self.assertTrue(forbidden.isdisjoint(self.result))
        self.assertTrue(schema_matches(self.result, json.loads(RESULT_SCHEMA.read_text())))
        self.assertTrue(schema_matches(self.request, json.loads(REQUEST_SCHEMA.read_text())))

    def test_req_m0_03_dispatch_never_asserts_repository_substrate(self):
        for document in (self.request, self.result, self.challenge):
            self.assertEqual(document["operation_family"], "external_provider_dispatch")
            self.assertEqual(document["substrate_authority"], "not_asserted")
            self.assertNotIn("repository_verification", canonical_json(document).decode())

    def test_req_m0_04_openrouter_mapping_preserves_exact_order_and_text(self):
        expected = b'{"messages":[{"content":"system\\n","role":"system"},{"content":"user \xf0\x9f\x8c\x8d\\\\\\\"\\n","role":"user"}],"models":["openai/gpt-5.6","z-ai/glm-5.2"]}'
        self.assertEqual(self.body, expected)
        null_parts = (b"null", b"line1\nline2")
        mapped = build_openrouter_body(request(null_parts), null_parts)
        self.assertIn(b'"content":"null"', mapped)
        self.assertIn(b'"content":"line1\\nline2"', mapped)

    def test_req_m0_05_signature_projection_is_domain_separated_and_complete(self):
        terminal_input = signature_input("terminal", self.result)
        self.assertTrue(terminal_input.startswith(b"workflow-authority\x00provider-dispatch-v1\x00terminal\x00"))
        self.assertNotIn(b'"signature"', terminal_input)
        for marker in (b'"scope"', b'"challenge_sha256"', b'"fido_assertion_sha256"', b'"cleanup"'):
            self.assertIn(marker, terminal_input)

    def test_req_m0_06_fake_is_explicitly_production_ineligible(self):
        fake = FakeBroker("/tmp/provider-dispatch-test/socket")
        status = fake.status()
        self.assertFalse(fake.production_ready())
        self.assertFalse(status["production_ready"])
        self.assertEqual(status["fixture_domain"], PRODUCTION_INELIGIBLE_DOMAIN)
        self.assertTrue(schema_matches(status, json.loads(STATUS_SCHEMA.read_text())))
        for path in ("/run/workflow-authority", "/var/run/workflow-authority", "relative"):
            with self.subTest(path=path), self.assertRaises(ProviderDispatchError):
                FakeBroker(path)

    def test_req_m0_07_mutations_unknowns_malformed_and_bounds_reject(self):
        mutations = []
        for field in ("mapping", "destination", "method", "path", "operation_family", "substrate_authority"):
            item = copy.deepcopy(self.request); item[field] += "-changed"; mutations.append(item)
        item = copy.deepcopy(self.request); item["unknown"] = True; mutations.append(item)
        for mutation in mutations:
            with self.assertRaises(ProviderDispatchError):
                validate_request(mutation, self.parts)
        bad_parts = list(self.parts); bad_parts.reverse()
        with self.assertRaisesRegex(ProviderDispatchError, "part_frame_mismatch"):
            validate_request(self.request, bad_parts)
        changed_models = copy.deepcopy(self.challenge); changed_models["models"].reverse()
        with self.assertRaisesRegex(ProviderDispatchError, "terminal_binding_invalid"):
            validate_authority_binding(self.request, self.body, changed_models, self.ack)

    def test_req_m0_08_public_diagnostics_never_echo_hostile_text(self):
        hostile = b'{"secret":"sk-fixture-do-not-echo","secret":1}'
        with self.assertRaises(ProviderDispatchError) as caught:
            parse_canonical_json(hostile)
        self.assertEqual(str(caught.exception), "invalid_document")
        self.assertNotIn("fixture", str(caught.exception))

    def test_req_m0_09_complete_positive_vector_bytes_are_frozen(self):
        request_bytes = encode_request(self.request, self.parts)
        challenge_bytes = frame32(canonical_json(self.challenge))
        ack_bytes = frame32(canonical_json(self.ack))
        content_bytes = frame64(self.response)
        terminal_bytes = frame32(canonical_json(self.result))
        vector = request_bytes + challenge_bytes + ack_bytes + content_bytes + terminal_bytes
        self.assertEqual(struct.unpack(">I", request_bytes[:4])[0], len(canonical_json(self.request)))
        self.assertEqual(sha256(vector), "sha256:601c9c609a32a737879d7cca4b7909461c9b103af2750db45a85f7f682b104f1")
        self.assertEqual(EXIT_VERIFIED, 0)
        self.assertEqual(FROZEN_EXCHANGE["fd3"]["kind"], "inherited-anonymous-pipe")
        self.assertFalse(FROZEN_EXCHANGE["retrieve"])
        fake = FakeBroker("/tmp/provider-dispatch-test/socket")
        self.assertEqual(
            fake.complete_exchange(
                self.request, self.parts, self.challenge, self.ack,
                self.response, self.result,
            ),
            vector,
        )

        golden_variants = {}
        for name, parts, roles, response in (
            ("null", (b"null", b"line1\nline2"), ("system", "user"), b"null"),
            ("max", (b"x" * MAX_FRAME_BYTES,), ("user",), b"x" * 8388608),
        ):
            req = request(parts, roles)
            body = build_openrouter_body(req, parts)
            chall = challenge(req, body)
            ack = {
                "schema_version": 1, "protocol": PROTOCOL, "type": "consent_ack",
                "challenge_sha256": sha256(canonical_json(chall)),
            }
            terminal = result(req, chall, response)
            golden_variants[name] = sha256(fake.complete_exchange(
                req, parts, chall, ack, response, terminal,
            ))
        self.assertEqual(golden_variants, {
            "null": "sha256:9860384f26a0df1879bdc90e00bcdb614f28400df182265b22730ad417b9873b",
            "max": "sha256:60f7e6702c1bce64f38de03142fbdf0292606b4ec10aa35a5255215adf68d201",
        })

    def test_req_m0_10_cross_connection_stale_build_policy_and_result_mismatch_reject(self):
        cases = {}
        for field in ("connection_nonce_sha256", "daemon_build_sha256", "scanner_build_sha256", "policy_sha256"):
            mutation = copy.deepcopy(self.challenge)
            mutation[field] = "sha256:" + "2" * 64
            cases[field] = mutation
        for name, mutation in cases.items():
            with self.subTest(name=name), self.assertRaises(ProviderDispatchError):
                validate_authority_binding(self.request, self.body, mutation, self.ack)
        mismatch = copy.deepcopy(self.result); mismatch["response_length"] += 1
        with self.assertRaisesRegex(ProviderDispatchError, "terminal_binding_invalid"):
            verify_terminal_result(self.request, self.challenge, self.response, mismatch)

    def test_req_m0_11_hmac_envelope_and_receipt_key_downgrades_are_absent(self):
        frozen = canonical_json(FROZEN_TRUST_CHAIN)
        for rejected in (b"authority-envelope-v1", b"hmac", b"receipt-key"):
            self.assertIn(rejected, frozen)
        for document in (self.request, self.challenge, self.result):
            self.assertTrue({"auth_mode", "receipt_key", "hmac"}.isdisjoint(document))

    def test_chk_m0_02_canonical_json_boundaries(self):
        self.assertEqual(parse_canonical_json(canonical_json(self.request)), self.request)
        cases = (
            b'{"a":1,"a":2}', b'{"n":1.0}', b'{"n":NaN}', b'{"n":01}',
            b'{"a": 1}', b'\xff', b'[' * 17 + b'0' + b']' * 17,
        )
        for raw in cases:
            with self.subTest(raw=raw[:20]), self.assertRaises(ProviderDispatchError):
                parse_canonical_json(raw)
        with self.assertRaisesRegex(ProviderDispatchError, "frame_too_large"):
            parse_canonical_json(b" " * (MAX_FRAME_BYTES + 1))

    def test_chk_m0_03_negative_vector_codes_and_state_outcomes(self):
        expected = {
            "disclosure_decline": (EXIT_DISCLOSURE_DECLINED, "disclosure_declined", False, True),
            "fido_decline": (EXIT_AUTHORIZATION_DECLINED, "authorization_declined", False, True),
            "operator_expiry": (EXIT_AUTHORIZATION_DECLINED, "authorization_expired", False, True),
            "provider_timeout_after_send": (EXIT_UNKNOWN, "provider_result_unknown", True, True),
            "response_mismatch": (EXIT_RESULT_VERIFICATION, "result_verification_failed", True, True),
            "close_before_ack": (EXIT_AUTHORIZATION_DECLINED, "consent_connection_invalid", False, True),
            "close_after_send": (EXIT_UNKNOWN, "provider_result_unknown", True, True),
            "cross_connection_reuse": (EXIT_AUTHORIZATION_DECLINED, "authorization_replayed", False, True),
            "provider_failure": (EXIT_PROVIDER_FAILURE, "provider_failure", True, True),
        }
        self.assertEqual(set(expected), {
            "disclosure_decline", "fido_decline", "operator_expiry",
            "provider_timeout_after_send", "response_mismatch", "close_before_ack",
            "close_after_send", "cross_connection_reuse", "provider_failure",
        })
        for exit_code, code, network, consumed in expected.values():
            self.assertIn(code, FakeBroker("/tmp/fake/socket").status(code)["last_error_code"])
            self.assertIs(type(network), bool); self.assertTrue(consumed)
            self.assertIn(exit_code, {71, 72, 73, 74, 75})

    def test_chk_m0_04_exchange_tombstone_is_nonretrievable(self):
        exchange = {
            "schema_version": 1, "protocol": PROTOCOL, "state": "tombstone",
            "request": self.request, "request_body_sha256": sha256(self.body),
            "challenge": self.challenge, "consent_ack": None, "result": None,
            "safe_error": "consent_connection_invalid", "consumed": True,
            "network_attempted": False, "response_retrievable": False,
        }
        self.assertEqual(validate_exchange(exchange), exchange)
        mutation = copy.deepcopy(exchange); mutation["response_retrievable"] = True
        with self.assertRaisesRegex(ProviderDispatchError, "exchange_state_invalid"):
            validate_exchange(mutation)

    def test_chk_m0_05_flood_rejects_before_response_allocation(self):
        oversized = request(parts=(b"x",), roles=("user",))
        oversized["parts"] = oversized["parts"] * 257
        with self.assertRaisesRegex(ProviderDispatchError, "bounds_exceeded"):
            validate_request(oversized)
        with self.assertRaisesRegex(ProviderDispatchError, "frame_too_large"):
            frame64(b"x" * (MAX_REQUEST_BYTES + 1))

    def test_chk_m0_06_max_legal_part_and_request_budget(self):
        raw = b"x" * MAX_FRAME_BYTES
        req = request(parts=(raw,), roles=("user",))
        body = build_openrouter_body(req, (raw,))
        self.assertLessEqual(len(body), MAX_REQUEST_BYTES)
        self.assertEqual(len(encode_request(req, (raw,))), 4 + len(canonical_json(req)) + 8 + len(raw))


if __name__ == "__main__":
    unittest.main()
