import base64
import copy
import json
import unittest
from datetime import datetime, timezone

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.provider_dispatch import (
    FROZEN_ALLOCATION_EXCHANGE,
    FROZEN_ALLOCATION_LIMITS,
    ProviderDispatchError,
    authority_hello_bytes,
    bind_allocation_request,
    canonical_json,
    dispatch_proposal_bytes,
    sha256,
    validate_authority_hello,
    validate_dispatch_proposal,
)


SCHEMA = KERNEL_REFERENCES / "provider-dispatch-allocation-schema.json"
VECTOR = KERNEL_REFERENCES.parents[4] / "tests" / "fixtures" / "provider-dispatch-allocation-v1.json"


class ProviderDispatchAllocationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vector = json.loads(VECTOR.read_text())
        cls.parts = [base64.b64decode(item) for item in cls.vector["parts_base64"]]
        cls.now = datetime(2026, 8, 3, 0, 1, tzinfo=timezone.utc)

    def assert_code(self, expected, operation):
        with self.assertRaises(ProviderDispatchError) as caught:
            operation()
        self.assertEqual(caught.exception.code, expected)

    def test_frozen_cross_language_bytes_and_schema(self):
        self.assertEqual(FROZEN_ALLOCATION_EXCHANGE["first_frame"], "daemon-u32be-canonical-authority_hello")
        self.assertEqual(FROZEN_ALLOCATION_EXCHANGE["next_frame"], "caller-u32be-canonical-dispatch_proposal")
        self.assertEqual(FROZEN_ALLOCATION_EXCHANGE["allocation_ordering"], "required-global-serialized-sequence")
        self.assertEqual(FROZEN_ALLOCATION_EXCHANGE["endpoint_discovery"], "required-fixed-trusted-endpoint-only")
        self.assertEqual(FROZEN_ALLOCATION_EXCHANGE["ancillary_descriptors"], "required-reject")
        hello = self.vector["hello"]
        proposal = self.vector["proposal"]
        self.assertEqual(sha256(authority_hello_bytes(hello, now=self.now)), self.vector["hello_sha256"])
        self.assertEqual(sha256(dispatch_proposal_bytes(proposal, self.parts)), self.vector["proposal_sha256"])
        self.assertEqual(proposal["authority_hello_sha256"], self.vector["hello_sha256"])
        request = bind_allocation_request(hello, proposal, self.parts, now=self.now)
        self.assertEqual(request["authority"]["nonce"], proposal["caller_nonce"])
        self.assertEqual(request["authority"]["allocation_hello_sha256"], self.vector["hello_sha256"])
        self.assertEqual(request["authority"]["dispatch_proposal_sha256"], self.vector["proposal_sha256"])
        wrong_digest = copy.deepcopy(proposal)
        wrong_digest["authority_hello_sha256"] = "sha256:" + "0" * 64
        self.assert_code(
            "terminal_binding_invalid",
            lambda: bind_allocation_request(hello, wrong_digest, self.parts, now=self.now),
        )
        other_hello = copy.deepcopy(hello)
        other_hello["connection_nonce_sha256"] = "sha256:" + "6" * 64
        self.assert_code(
            "terminal_binding_invalid",
            lambda: bind_allocation_request(other_hello, proposal, self.parts, now=self.now),
        )
        other_nonce = copy.deepcopy(proposal)
        other_nonce["caller_nonce"] = "caller-nonce-02"
        other_request = bind_allocation_request(hello, other_nonce, self.parts, now=self.now)
        self.assertEqual(other_request["authority"]["nonce"], other_nonce["caller_nonce"])
        self.assertEqual(
            other_request["authority"]["dispatch_proposal_sha256"],
            sha256(canonical_json(other_nonce)),
        )
        self.assertNotEqual(
            other_request["authority"]["dispatch_proposal_sha256"],
            request["authority"]["dispatch_proposal_sha256"],
        )
        schema = json.loads(SCHEMA.read_text())
        self.assertTrue(schema_matches(hello, schema))
        self.assertTrue(schema_matches(proposal, schema))
        ack = {"schema_version": 1, "protocol": hello["protocol"], "type": "consent_ack", "challenge_sha256": "sha256:" + "a" * 64}
        safe = {"schema_version": 1, "protocol": hello["protocol"], "type": "safe_error", "code": "authorization_declined", "exit_code": 71, "consumed": True, "network_attempted": False}
        self.assertTrue(schema_matches(ack, schema))
        self.assertTrue(schema_matches(safe, schema))
        safe["network_attempted"] = True
        self.assertFalse(schema_matches(safe, schema))

    def test_caller_cannot_add_or_override_host_allocation_fields(self):
        forbidden = (
            "sequence", "boot_id", "session_id", "issued_at", "expires_at",
            "prior_chain_digest", "connection_nonce_sha256",
            "daemon_build_sha256", "scanner_build_sha256", "policy_sha256",
            "limits",
        )
        for field in forbidden:
            with self.subTest(field=field):
                proposal = copy.deepcopy(self.vector["proposal"])
                proposal[field] = self.vector["hello"].get(field, {})
                self.assert_code("invalid_document", lambda: validate_dispatch_proposal(proposal, self.parts))

    def test_hello_requires_current_time_and_rejects_expiry_and_limit_downgrade(self):
        with self.assertRaises(TypeError):
            FROZEN_ALLOCATION_LIMITS["max_active_allocations"] = 2
        with self.assertRaises(TypeError):
            validate_authority_hello(self.vector["hello"])
        self.assert_code(
            "authorization_expired",
            lambda: validate_authority_hello(
                self.vector["hello"],
                now=datetime(2026, 8, 3, 0, 2, tzinfo=timezone.utc),
            ),
        )
        for mutation in (
            lambda value: value["limits"].update(max_active_allocations=2),
            lambda value: value["limits"].update(cancellation="release"),
            lambda value: value.update(expires_at="2026-08-03T00:03:00Z"),
            lambda value: value.update(sequence=0),
            lambda value: value.update(sequence=2**63),
        ):
            hello = copy.deepcopy(self.vector["hello"])
            mutation(hello)
            with self.assertRaises(ProviderDispatchError):
                validate_authority_hello(hello, now=self.now)

        overflow = copy.deepcopy(self.vector["hello"])
        overflow["sequence"] = 2**63
        allocation_schema = json.loads(SCHEMA.read_text())
        self.assertEqual(
            allocation_schema["$defs"]["authority_hello"]["properties"]["sequence"]["maximum"],
            2**63 - 1,
        )

    def test_proposal_rejects_wrong_hello_altered_order_bytes_and_non_utf8(self):
        proposal = copy.deepcopy(self.vector["proposal"])
        proposal["authority_hello_sha256"] = "sha256:" + "0" * 64
        # A different valid digest is structurally valid; composition must compare
        # it with the hello emitted on this same connection.
        self.assertEqual(validate_dispatch_proposal(proposal, self.parts), proposal)
        self.assertNotEqual(proposal["authority_hello_sha256"], sha256(canonical_json(self.vector["hello"])))
        self.assert_code("part_frame_mismatch", lambda: validate_dispatch_proposal(self.vector["proposal"], list(reversed(self.parts))))
        self.assert_code("part_frame_mismatch", lambda: validate_dispatch_proposal(self.vector["proposal"], [self.parts[0], b"\xff" * 10]))
        self.assert_code("part_frame_mismatch", lambda: validate_dispatch_proposal(self.vector["proposal"], self.parts[:1]))


if __name__ == "__main__":
    unittest.main()
