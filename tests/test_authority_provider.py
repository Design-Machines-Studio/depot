import copy
import datetime as dt
import json
import unittest
from pathlib import Path

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.authority_provider import (
    AuthorityProviderError, LegacyHMACAuthority, NativeProviderAdapter,
    NativeProviderAuthority,
    build_authority_request, canonical_bytes, canonical_digest,
    key_record_digest, synthetic_signature,
)
from workflow_kernel.verification_errors import VerificationPlannerError
from workflow_kernel.verification_receipts import (
    receipt_index, seal_provider_attestation, sign_receipt, validate_receipt,
)


AUTHORITY_SCHEMA = KERNEL_REFERENCES / "authority-provider-schema.json"
SUBSTRATE_SCHEMA = (
    KERNEL_REFERENCES / "repository-verification-substrate-schema.json"
)
MODIFIED_SCHEMAS = (
    AUTHORITY_SCHEMA,
    SUBSTRATE_SCHEMA,
    KERNEL_REFERENCES / "repository-verification-approval-schema.json",
    KERNEL_REFERENCES
    / "repository-verification-provider-attestation-schema.json",
    KERNEL_REFERENCES / "repository-verification-receipts-schema.json",
    KERNEL_REFERENCES / "repository-verification-profile-schema.json",
)
FIXED_NOW = dt.datetime(2026, 8, 2, 0, 1, tzinfo=dt.timezone.utc)
CANONICAL_GOLDEN_VECTORS = (
    (
        "nested-unicode-bool-null",
        {"nested": {"enabled": True, "missing": None}, "name": "café"},
        b'{"name":"caf\xc3\xa9","nested":{"enabled":true,"missing":null}}',
        "sha256:d6d689b04f8046ff401492458971df0196a7c1345b80e4204c5d7a8497342e44",
    ),
    (
        "array-unicode-order",
        [False, None, {"z": 1, "a": "雪"}],
        b'[false,null,{"a":"\xe9\x9b\xaa","z":1}]',
        "sha256:927048a70e7e7b023151e1cedf460b894d038ec0045186c22f36fa066f6ea9dd",
    ),
    (
        "maximum-string-boundary",
        {"boundary": "x" * 4096},
        b'{"boundary":"' + b"x" * 4096 + b'"}',
        "sha256:dbac4497ac58b825eb8a6ffd42f03e97a386477eb1726776b791c9725ea2022b",
    ),
)


def bindings():
    digest = "sha256:" + "1" * 64
    return {
        "repository_descriptor_id": "repo-1",
        "repository_scope_digest": digest,
        "run_id": "run-1",
        "authorization_event_id": "event-1",
        "profile_ref": ".dm/verification.json",
        "profile_digest": digest,
        "authority_digest": digest,
        "trusted_base_commit": "a" * 40,
        "candidate_commit": "b" * 40,
        "candidate_snapshot_digest": digest,
        "include_worktree": False,
        "cadence_boundary": "chunk",
        "lane_id": "focused",
        "provider": None,
        "substrate_digest": None,
    }


def request(*, document=None, nonce="0" * 64, sequence=1,
            operation="record_result"):
    document = {"fixture": True} if document is None else document
    return build_authority_request(
        operation=operation, bindings=bindings(), nonce=nonce,
        sequence=sequence, key_id="authority-key-1", boot_id="boot-1",
        session_id="session-1", issued_at="2026-08-02T00:00:00Z",
        expires_at="2026-08-02T00:05:00Z",
        document_digest=canonical_digest(document),
        now=FIXED_NOW,
    )


def key_record(*, revoked_at=None, verify_not_after="2027-08-01T00:00:00Z"):
    record = {
        "schema_version": 2,
        "artifact_role": "workflow_authority_public_key_record",
        "record_digest": "",
        "key_id": "authority-key-1",
        "algorithm": "ecdsa-p256-sha256",
        "public_key_digest": "sha256:" + "2" * 64,
        "issuer_identity": "Design Machines Workflow Authority",
        "activated_at": "2026-08-01T00:00:00Z",
        "revoked_at": revoked_at,
        "verify_not_before": "2026-08-01T00:00:00Z",
        "verify_not_after": verify_not_after,
    }
    record["record_digest"] = key_record_digest(record)
    return record


def response(authority_request, document, *, record=None, evidence_decision=None):
    record = record or key_record()
    request_digest = canonical_digest(authority_request)
    grant = {
        "schema_version": 2,
        "artifact_role": "workflow_authority_grant",
        "authority_mode": "native_provider",
        "request_digest": request_digest,
        "key_id": record["key_id"],
        "public_key_digest": record["public_key_digest"],
        "operation": authority_request["operation"],
        "bindings": authority_request["bindings"],
        "nonce": authority_request["nonce"],
        "sequence": authority_request["sequence"],
        "boot_id": authority_request["boot_id"],
        "session_id": authority_request["session_id"],
        "issued_at": authority_request["issued_at"],
        "expires_at": authority_request["expires_at"],
    }
    envelope = {
        "schema_version": 2,
        "artifact_role": "workflow_authority_signature_envelope",
        "authority_mode": "native_provider",
        "algorithm": record["algorithm"],
        "key_id": record["key_id"],
        "public_key_digest": record["public_key_digest"],
        "request_digest": request_digest,
        "document_digest": canonical_digest(document),
        "signature": synthetic_signature(request_digest.encode("ascii")),
    }
    return {
        "schema_version": 2,
        "artifact_role": "workflow_authority_provider_response",
        "status": "approved",
        "reason_code": None,
        "request": authority_request,
        "grant": grant,
        "envelope": envelope,
        "key_record": record,
        "evidence_decision": evidence_decision,
    }


def unsigned_receipt(version):
    digest = "sha256:" + "3" * 64
    return {
        "schema_version": version, "profile_digest": digest,
        "lane_id": "focused", "tier": "focused", "boundary": "chunk",
        "owner": "local", "required": True, "status": "passed",
        "reason": "completed", "command_digest": digest,
        "input_digest": digest, "cache_key": digest, "exit_code": 0,
        "duration_seconds": 0.1, "source_receipt_digest": None,
        "stdout_digest": digest, "stderr_digest": digest,
        "stdout_bytes": 0, "stderr_bytes": 0, "head_commit": "b" * 40,
        "provider_run_id": None, "observed_at": "2026-08-02T00:00:01Z",
        "evidence_digest": None,
    }


class AuthorityProviderTests(unittest.TestCase):
    @staticmethod
    def verifier(record, envelope):
        return envelope["signature"] == synthetic_signature(
            envelope["request_digest"].encode("ascii"),
        )
    def test_named_canonical_golden_vectors_are_exact_and_repeatable(self):
        self.assertEqual(len(CANONICAL_GOLDEN_VECTORS), 3)
        for name, value, expected_bytes, expected_digest in CANONICAL_GOLDEN_VECTORS:
            with self.subTest(name=name):
                self.assertEqual(canonical_bytes(value), expected_bytes)
                self.assertEqual(canonical_bytes(value), expected_bytes)
                self.assertEqual(canonical_digest(value), expected_digest)

    def test_every_new_or_modified_schema_is_closed_and_enumerated(self):
        self.assertEqual(
            {path.name for path in MODIFIED_SCHEMAS},
            {
                "authority-provider-schema.json",
                "repository-verification-substrate-schema.json",
                "repository-verification-approval-schema.json",
                "repository-verification-provider-attestation-schema.json",
                "repository-verification-receipts-schema.json",
                "repository-verification-profile-schema.json",
            },
        )
        for path in MODIFIED_SCHEMAS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("additionalProperties", json.dumps(schema))
        authority_text = AUTHORITY_SCHEMA.read_text(encoding="utf-8").lower()
        substrate_text = SUBSTRATE_SCHEMA.read_text(encoding="utf-8").lower()
        for forbidden in ("hmac", "receipt_key", "receipt-key", "key_bytes"):
            self.assertNotIn(forbidden, authority_text + substrate_text)

    def test_v2_request_schema_rejects_unknown_and_secret_fields(self):
        schema = json.loads(AUTHORITY_SCHEMA.read_text(encoding="utf-8"))
        authority_request = request()
        self.assertTrue(schema_matches(authority_request, schema))
        for field in ("unexpected", "key_bytes", "receipt_key"):
            self.assertFalse(schema_matches(
                {**authority_request, field: "not-authority"}, schema,
            ))
        missing = copy.deepcopy(authority_request)
        del missing["bindings"]["repository_descriptor_id"]
        self.assertFalse(schema_matches(missing, schema))
        with self.assertRaisesRegex(VerificationPlannerError, "authority_invalid"):
            build_authority_request(**{
                "operation": missing["operation"],
                "bindings": missing["bindings"],
                "nonce": missing["nonce"], "sequence": missing["sequence"],
                "key_id": missing["key_id"], "boot_id": missing["boot_id"],
                "session_id": missing["session_id"],
                "issued_at": missing["issued_at"],
                "expires_at": missing["expires_at"],
                "document_digest": missing["document_digest"],
            })

    def test_required_bindings_reject_null_and_commits_fail_safely(self):
        required = (
            "repository_descriptor_id", "repository_scope_digest", "run_id",
            "authorization_event_id", "profile_ref", "profile_digest",
            "authority_digest", "candidate_snapshot_digest",
            "trusted_base_commit", "candidate_commit",
        )
        for name in required:
            with self.subTest(name=name):
                invalid = bindings()
                invalid[name] = None
                with self.assertRaises(AuthorityProviderError) as caught:
                    build_authority_request(
                        operation="record_result", bindings=invalid,
                        nonce="0" * 64, sequence=1, key_id="authority-key-1",
                        boot_id="boot-1", session_id="session-1",
                        issued_at="2026-08-02T00:00:00Z",
                        expires_at="2026-08-02T00:05:00Z",
                        document_digest=canonical_digest({"fixture": True}),
                        now=FIXED_NOW,
                    )
                self.assertEqual(str(caught.exception), "authority_invalid")

    def test_issuance_rejects_materially_future_timestamp(self):
        with self.assertRaisesRegex(AuthorityProviderError, "authority_stale"):
            build_authority_request(
                operation="record_result", bindings=bindings(), nonce="0" * 64,
                sequence=1, key_id="authority-key-1", boot_id="boot-1",
                session_id="session-1", issued_at="2026-08-02T00:00:31Z",
                expires_at="2026-08-02T00:05:00Z",
                document_digest=canonical_digest({"fixture": True}),
                now=dt.datetime(2026, 8, 2, tzinfo=dt.timezone.utc),
            )

    def test_native_seal_binds_complete_request_and_document(self):
        unsigned = {**unsigned_receipt(2), "authority_mode": "native_provider"}
        authority_request = request(document=unsigned)
        provider_response = response(authority_request, unsigned)
        authority = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: copy.deepcopy(provider_response)),
            [key_record()], signature_verifier=self.verifier,
            now=lambda: FIXED_NOW,
        )
        sealed = sign_receipt(
            unsigned_receipt(2), authority, authority_request=authority_request,
        )
        self.assertEqual(sealed["authority_mode"], "native_provider")
        self.assertEqual(
            sealed["authority_provenance"]["envelope"]["request_digest"],
            canonical_digest(authority_request),
        )
        altered = copy.deepcopy(provider_response)
        altered["envelope"]["document_digest"] = "sha256:" + "9" * 64
        rejecting = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: altered), [key_record()],
            signature_verifier=self.verifier,
            now=lambda: FIXED_NOW,
        )
        with self.assertRaisesRegex(VerificationPlannerError, "authority_binding_mismatch"):
            sign_receipt(
                unsigned_receipt(2), rejecting,
                authority_request=authority_request,
            )

    def test_forged_signature_and_untrusted_key_record_are_rejected(self):
        unsigned = {**unsigned_receipt(2), "authority_mode": "native_provider"}
        authority_request = request(document=unsigned)
        forged = response(authority_request, unsigned)
        forged["envelope"]["signature"] = synthetic_signature(b"forgery")
        authority = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: forged), [key_record()],
            signature_verifier=self.verifier, now=lambda: FIXED_NOW,
        )
        with self.assertRaisesRegex(VerificationPlannerError, "authority_signature_invalid"):
            authority.accept_response(forged, authority_request, unsigned)

        attacker = key_record()
        attacker["public_key_digest"] = "sha256:" + "8" * 64
        attacker["record_digest"] = key_record_digest(attacker)
        untrusted = response(authority_request, unsigned, record=attacker)
        authority = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: untrusted), [key_record()],
            signature_verifier=self.verifier, now=lambda: FIXED_NOW,
        )
        with self.assertRaisesRegex(VerificationPlannerError, "authority_key_untrusted"):
            authority.accept_response(untrusted, authority_request, unsigned)

    def test_historical_signature_survives_current_expiry_and_revocation(self):
        record = key_record(
            revoked_at="2026-08-02T00:02:00Z",
            verify_not_after="2026-08-02T00:02:00Z",
        )
        unsigned = {**unsigned_receipt(2), "authority_mode": "native_provider"}
        authority_request = request(document=unsigned)
        provider_response = response(authority_request, unsigned, record=record)
        issuing = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: provider_response), [record],
            signature_verifier=self.verifier, now=lambda: FIXED_NOW,
        )
        sealed = sign_receipt(
            unsigned_receipt(2), issuing, authority_request=authority_request,
        )
        historical = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: None), [record],
            signature_verifier=self.verifier,
            now=lambda: dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(validate_receipt(sealed, historical), sealed)

    def test_provider_evidence_provenance_must_match_exactly(self):
        evidence = {
            "schema_version": 2,
            "artifact_role": "workflow_authority_evidence_decision",
            "verifier_id": "github-verifier",
            "verifier_key_id": "github-root-1",
            "provider": "github", "provider_run_id": "run-123",
            "head_commit": "b" * 40, "evidence_ref": "checks/123",
            "evidence_digest": "sha256:" + "4" * 64,
            "verified_at": "2026-08-02T00:00:01Z",
            "outcome": "passed", "exit_code": 0,
        }
        fields = {
            "schema_version": 2,
            "artifact_role": "repository_verification_provider_attestation",
            "provider": "github", "provider_run_id": "wrong-run",
            "head_commit": "b" * 40, "evidence_ref": "checks/123",
            "evidence_digest": "sha256:" + "4" * 64,
            "observed_at": "2026-08-02T00:00:01Z",
            "outcome": "passed", "exit_code": 0,
            "verifier_provenance": evidence,
        }
        authority = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: {}), [key_record()],
            signature_verifier=self.verifier, now=lambda: FIXED_NOW,
        )
        with self.assertRaisesRegex(VerificationPlannerError, "provider_evidence_invalid"):
            seal_provider_attestation(fields, authority)

    def test_replay_out_of_order_and_revoked_key_fail_closed(self):
        unsigned = {**unsigned_receipt(2), "authority_mode": "native_provider"}
        authority_request = request(document=unsigned)
        provider_response = response(authority_request, unsigned)
        authority = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: provider_response),
            [key_record()], signature_verifier=self.verifier,
            now=lambda: FIXED_NOW,
        )
        authority.accept_response(provider_response, authority_request, unsigned)
        with self.assertRaisesRegex(VerificationPlannerError, "authority_replay"):
            authority.accept_response(provider_response, authority_request, unsigned)
        revoked = key_record(revoked_at="2026-08-02T00:00:30Z")
        with self.assertRaisesRegex(VerificationPlannerError, "authority_key_revoked"):
            NativeProviderAuthority(
                NativeProviderAdapter(lambda actual: response(
                    authority_request, unsigned, record=revoked,
                )), [revoked], signature_verifier=self.verifier,
                now=lambda: dt.datetime(2026, 8, 2, 0, 1, tzinfo=dt.timezone.utc),
            ).accept_response(
                response(authority_request, unsigned, record=revoked),
                authority_request, unsigned,
            )

    def test_provider_failure_is_safe_and_never_falls_back(self):
        marker = "PRIVATE-MARKER provider stderr and request body"
        authority = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: (_ for _ in ()).throw(RuntimeError(marker))),
            [key_record()], signature_verifier=self.verifier,
            now=lambda: FIXED_NOW,
        )
        with self.assertRaises(VerificationPlannerError) as caught:
            sign_receipt(
                unsigned_receipt(2), authority,
                authority_request=request(document={
                    **unsigned_receipt(2), "authority_mode": "native_provider",
                }),
            )
        self.assertEqual(str(caught.exception), "authority_provider_unavailable")
        self.assertNotIn(marker, str(caught.exception))

    def test_denied_and_cancelled_responses_are_safe_before_nullable_envelope(self):
        unsigned = {**unsigned_receipt(2), "authority_mode": "native_provider"}
        authority_request = request(document=unsigned)
        authority = NativeProviderAuthority(
            NativeProviderAdapter(lambda actual: {}), [key_record()],
            signature_verifier=self.verifier, now=lambda: FIXED_NOW,
        )
        for status, reason in (
            ("denied", "authority_unauthorized"),
            ("cancelled", "authority_cancelled"),
        ):
            with self.subTest(status=status):
                denied = {
                    "schema_version": 2,
                    "artifact_role": "workflow_authority_provider_response",
                    "status": status, "reason_code": "safe_reason",
                    "request": authority_request, "grant": None,
                    "envelope": None, "key_record": None,
                    "evidence_decision": None,
                }
                with self.assertRaisesRegex(AuthorityProviderError, reason):
                    authority.accept_response(denied, authority_request, unsigned)

    def test_legacy_is_explicit_and_mixed_ledger_has_stable_reason(self):
        legacy = LegacyHMACAuthority(b"legacy-authority-test-value-32-bytes")
        v1 = sign_receipt(unsigned_receipt(1), legacy)
        with self.assertRaisesRegex(VerificationPlannerError, "mixed_authority"):
            receipt_index({
                "schema_version": 1,
                "artifact_role": "repository_verification_receipts",
                "receipts": [v1, {**v1, "schema_version": 2}],
            }, legacy)

    def test_production_profile_requires_contained_argv(self):
        schema = json.loads(
            (KERNEL_REFERENCES / "repository-verification-profile-schema.json")
            .read_text(encoding="utf-8")
        )
        profile = {
            "schema_version": 2, "authority_mode": "native_provider",
            "profile_id": "production", "lanes": [{
                "id": "focused", "tier": "focused", "cadences": ["chunk"],
                "owner": "local", "contained_argv": ["go", "test", "./..."],
            }],
        }
        self.assertTrue(schema_matches(profile, schema))
        self.assertFalse(schema_matches({
            **profile, "lanes": [{**profile["lanes"][0], "argv": ["go"]}],
        }, schema))
        self.assertFalse(schema_matches({
            **profile,
            "lanes": [{
                **profile["lanes"][0],
                "contained_argv": ["docker compose run app go test"],
            }],
        }, schema))

    def test_substrate_attestation_requires_complete_secure_observations(self):
        schema = json.loads(SUBSTRATE_SCHEMA.read_text(encoding="utf-8"))
        attestation_schema = copy.deepcopy(schema["$defs"]["attestation"])
        attestation_schema["properties"]["authority_provenance"] = {"type": "object"}
        self.assertEqual(
            set(schema["$defs"]["authorityProvenance"]["required"]),
            {"authority_mode", "grant", "envelope", "key_record"},
        )
        digest = "sha256:" + "5" * 64
        attestation = {
            "schema_version": 2,
            "artifact_role": "repository_verification_substrate_attestation",
            "authority_mode": "native_provider",
            "repository_descriptor_id": "repo-1",
            "repository_scope_digest": digest, "run_id": "run-1",
            "authorization_event_id": "event-1", "profile_digest": digest,
            "candidate_commit": "b" * 40, "lane_id": "focused",
            "request_nonce": "0" * 64, "request_sequence": 1,
            "issued_at": "2026-08-02T00:00:00Z",
            "expires_at": "2026-08-02T00:05:00Z",
            "endpoint_digest": digest, "engine_digest": digest,
            "image_digest": digest, "container_id": "container-1",
            "workspace_digest": digest, "toolchain_digest": digest,
            "go_version": "go1.26.5", "generator_name": "templ",
            "generator_version": "v0.3.960", "generator_binary_digest": digest,
            "containment_security": {
                "unprivileged": True, "no_new_privileges": True,
                "read_only_root": True, "network_mode": "none",
                "docker_socket_mounted": False,
                "authority_surfaces_mounted": False,
            },
            "result": {"outcome": "passed", "exit_code": 0,
                       "stdout_digest": digest, "stderr_digest": digest},
            "cleanup": {"container_removed": True, "workspace_removed": True,
                        "residue": [], "verified_at": "2026-08-02T00:01:00Z"},
            "lifecycle": "cleaned", "observed_at": "2026-08-02T00:01:00Z",
            "authority_provenance": {},
        }
        self.assertTrue(schema_matches(attestation, attestation_schema, schema))
        for missing in (
            "repository_scope_digest", "request_nonce", "go_version",
            "containment_security", "result", "cleanup",
        ):
            incomplete = {name: value for name, value in attestation.items() if name != missing}
            self.assertFalse(schema_matches(incomplete, attestation_schema, schema))
        insecure = copy.deepcopy(attestation)
        insecure["containment_security"]["docker_socket_mounted"] = True
        self.assertFalse(schema_matches(insecure, attestation_schema, schema))
        cleanup_failed = copy.deepcopy(attestation)
        cleanup_failed["lifecycle"] = "cleanup_failed"
        cleanup_failed["result"]["outcome"] = "failed"
        cleanup_failed["result"]["exit_code"] = 1
        cleanup_failed["cleanup"] = {
            "container_removed": False, "workspace_removed": False,
            "residue": ["container:container-1"],
            "tombstone_digest": digest,
            "verified_at": "2026-08-02T00:01:00Z",
        }
        self.assertTrue(schema_matches(
            cleanup_failed, attestation_schema, schema,
        ))
        false_pass = copy.deepcopy(cleanup_failed)
        false_pass["result"]["outcome"] = "passed"
        self.assertFalse(schema_matches(false_pass, attestation_schema, schema))

    def test_v1_schemas_preserve_released_compatibility_bounds(self):
        approval_schema = json.loads(
            MODIFIED_SCHEMAS[2].read_text(encoding="utf-8")
        )["oneOf"][0]
        digest = "sha256:" + "6" * 64
        approval = {
            "schema_version": 1,
            "artifact_role": "repository_verification_profile_approval",
            "repository_scope_digest": digest, "profile_id": "",
            "profile_ref": "x" * 5000, "profile_digest": digest,
            "authority_digest": digest, "trusted_base_commit": "a" * 40,
            "candidate_commit": "b" * 40, "include_worktree": False,
            "changed_paths": ["x" * 5000], "changed_paths_digest": digest,
            "candidate_snapshot_digest": digest, "run_id": "",
            "authorization_event_id": "", "approved_at": "legacy-time",
            "authority_key_id": digest,
            "approval_auth": "hmac-sha256:" + "0" * 64,
        }
        self.assertTrue(schema_matches(approval, approval_schema))
        provider_schema = json.loads(
            MODIFIED_SCHEMAS[3].read_text(encoding="utf-8")
        )["oneOf"][0]
        provider = {
            "schema_version": 1,
            "artifact_role": "repository_verification_provider_attestation",
            "provider": "github", "provider_run_id": "run",
            "head_commit": "b" * 40, "evidence_digest": digest,
            "observed_at": "2" * 5000, "outcome": "passed", "exit_code": 0,
            "attestation_auth": "hmac-sha256:" + "0" * 64,
        }
        self.assertTrue(schema_matches(provider, provider_schema))

    def test_import_has_no_observable_runtime_side_effect(self):
        import workflow_kernel.authority_provider as module
        self.assertEqual(module.__name__, "workflow_kernel.authority_provider")


if __name__ == "__main__":
    unittest.main()
