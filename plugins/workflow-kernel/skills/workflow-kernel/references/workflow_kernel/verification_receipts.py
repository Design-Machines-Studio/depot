"""Authenticated approval and receipt storage for repository verification."""

from __future__ import annotations

import hashlib
import json
from .authority_provider import (
    AuthorityProvider, LegacyHMACAuthority, NativeProviderAuthority,
)
from .verification_contract import (
    BOUNDARIES, COMMIT_PATTERN, DIGEST_PATTERN, OWNERS, TIERS,
)
from .verification_errors import VerificationPlannerError


RECEIPT_SCHEMA_VERSION = 1
RECEIPT_KEYS = frozenset({
    "schema_version", "profile_digest", "lane_id", "tier", "boundary",
    "owner", "required", "status", "reason", "command_digest",
    "input_digest", "cache_key", "exit_code", "duration_seconds",
    "source_receipt_digest", "stdout_digest", "stderr_digest",
    "stdout_bytes", "stderr_bytes", "head_commit", "provider_run_id",
    "observed_at", "evidence_digest", "receipt_auth",
})
RECEIPT_V2_KEYS = RECEIPT_KEYS - {"receipt_auth"} | {
    "authority_mode", "authority_provenance",
}
RECEIPT_STATUSES = frozenset({
    "passed", "failed", "reused", "remote_pending", "blocked", "unavailable",
})
PROVIDER_ATTESTATION_KEYS = frozenset({
    "schema_version", "artifact_role", "provider", "provider_run_id",
    "head_commit", "evidence_digest", "observed_at", "outcome", "exit_code",
    "attestation_auth",
})
PROVIDER_ATTESTATION_V2_KEYS = PROVIDER_ATTESTATION_KEYS - {"attestation_auth"} | {
    "authority_mode", "evidence_ref", "verifier_provenance",
    "authority_provenance",
}


def _validate_provider_provenance(document):
    evidence = document.get("verifier_provenance")
    if (
        type(evidence) is not dict
        or set(evidence) != {
            "schema_version", "artifact_role", "verifier_id",
            "verifier_key_id", "provider", "provider_run_id",
            "head_commit", "evidence_ref", "evidence_digest",
            "verified_at", "outcome", "exit_code",
        }
        or evidence.get("schema_version") != 2
        or evidence.get("artifact_role")
        != "workflow_authority_evidence_decision"
        or evidence.get("provider") != document.get("provider")
        or evidence.get("provider_run_id") != document.get("provider_run_id")
        or evidence.get("head_commit") != document.get("head_commit")
        or evidence.get("evidence_ref") != document.get("evidence_ref")
        or evidence.get("evidence_digest") != document.get("evidence_digest")
        or evidence.get("verified_at") != document.get("observed_at")
        or evidence.get("outcome") != document.get("outcome")
        or evidence.get("exit_code") != document.get("exit_code")
        or type(evidence.get("verifier_id")) is not str
        or not evidence["verifier_id"]
        or type(evidence.get("verifier_key_id")) is not str
        or not evidence["verifier_key_id"]
    ):
        raise VerificationPlannerError("provider_evidence_invalid")


def canonical_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def receipt_key(value):
    """Select the legacy v1 authority used by the stdin compatibility mode."""
    if isinstance(value, (LegacyHMACAuthority, NativeProviderAuthority)):
        return value
    if type(value) is not bytes or len(value) < 32:
        raise VerificationPlannerError(
            "verification receipt key must contain at least 32 bytes",
        )
    return value


def _authority(value):
    # Raw bytes can arrive only from the existing explicitly selected
    # --receipt-key-stdin compatibility path.  Production provider mode never
    # reaches this branch and provider failure never falls back to it.
    if type(value) is bytes:
        return LegacyHMACAuthority(value)
    if not isinstance(value, AuthorityProvider):
        raise VerificationPlannerError("explicit verification authority required")
    return value


def seal_approval(fields, authority, *, authority_request=None):
    authority = _authority(authority)
    if authority.mode == "legacy_hmac":
        return authority.seal(fields, "approval_auth", operation="approve_profile")
    return authority.seal(
        {**fields, "authority_mode": "native_provider"},
        "authority_provenance", operation="approve_profile", request=authority_request,
    )


def seal_provider_attestation(fields, authority, *, authority_request=None):
    """Seal provider-native evidence after trusted host verification.

    This primitive is for the host authority broker. Repository workflows only
    consume its output through ``record-verification-result``.
    """
    authority = _authority(authority)
    if authority.mode == "legacy_hmac":
        return authority.seal(
            fields, "attestation_auth", operation="provider_attestation",
        )
    _validate_provider_provenance(fields)
    return authority.seal(
        {**fields, "authority_mode": "native_provider"},
        "authority_provenance", operation="provider_attestation",
        request=authority_request,
    )


def validate_provider_attestation(document, authority, *, authority_request=None):
    """Validate a broker-sealed, exact-head provider evidence decision."""
    authority = _authority(authority)
    version = document.get("schema_version") if type(document) is dict else None
    expected_keys = (
        PROVIDER_ATTESTATION_KEYS if version == 1
        else PROVIDER_ATTESTATION_V2_KEYS if version == 2 else frozenset()
    )
    if (
        type(document) is not dict
        or set(document) != set(expected_keys)
        or version != authority.write_schema_version
        or document.get("artifact_role")
        != "repository_verification_provider_attestation"
        or document.get("provider") not in OWNERS - {"local", "unresolved"}
        or type(document.get("provider_run_id")) is not str
        or not document["provider_run_id"]
        or type(document.get("head_commit")) is not str
        or COMMIT_PATTERN.fullmatch(document["head_commit"]) is None
        or type(document.get("evidence_digest")) is not str
        or DIGEST_PATTERN.fullmatch(document["evidence_digest"]) is None
        or type(document.get("observed_at")) is not str
        or not document["observed_at"]
        or document.get("outcome") not in {"passed", "failed"}
        or type(document.get("exit_code")) is not int
        or (
            document["outcome"] == "passed"
            and document["exit_code"] != 0
        )
        or (
            document["outcome"] == "failed"
            and document["exit_code"] == 0
        )
    ):
        raise VerificationPlannerError(
            "provider result is not attested by the host broker",
        )
    if version == 2:
        if type(document.get("evidence_ref")) is not str or not document["evidence_ref"]:
            raise VerificationPlannerError("provider_evidence_invalid")
        _validate_provider_provenance(document)
    field = "attestation_auth" if version == 1 else "authority_provenance"
    return authority.verify(
        document, field, operation="provider_attestation",
        request=authority_request,
    )


def validate_approval_document(approval, expected, authority, *, authority_request=None):
    authority = _authority(authority)
    field = (
        "approval_auth" if authority.write_schema_version == 1
        else "authority_provenance"
    )
    if (
        type(approval) is not dict
        or set(approval) != set(expected)
        or approval != expected
        or approval.get("schema_version") != authority.write_schema_version
    ):
        raise VerificationPlannerError(
            "verification profile is not approved by the host",
        )
    return authority.verify(
        approval, field, operation="approve_profile", request=authority_request,
    )


def receipt_auth(receipt, authority):
    authority = _authority(authority)
    if authority.mode != "legacy_hmac":
        raise VerificationPlannerError("mixed_authority")
    return authority.seal(
        {name: value for name, value in receipt.items() if name != "receipt_auth"},
        "receipt_auth", operation="record_result",
    )["receipt_auth"]


def sign_receipt(receipt, authority, *, authority_request=None):
    authority = _authority(authority)
    if authority.mode == "legacy_hmac":
        return authority.seal(receipt, "receipt_auth", operation="record_result")
    return authority.seal(
        {**receipt, "authority_mode": "native_provider"},
        "authority_provenance", operation="record_result",
        request=authority_request,
    )


def validate_receipt(receipt, authority, *, authority_request=None):
    authority = _authority(authority)
    version = receipt.get("schema_version") if type(receipt) is dict else None
    expected_keys = RECEIPT_KEYS if version == 1 else RECEIPT_V2_KEYS if version == 2 else frozenset()
    if (
        type(receipt) is not dict
        or set(receipt) != set(expected_keys)
        or version != authority.write_schema_version
    ):
        raise VerificationPlannerError("invalid verification receipt")
    digest_fields = {
        "profile_digest", "command_digest", "input_digest", "cache_key",
    }
    optional_digests = {
        "source_receipt_digest", "stdout_digest", "stderr_digest",
        "evidence_digest",
    }
    if (
        receipt.get("schema_version") != authority.write_schema_version
        or receipt.get("status") not in RECEIPT_STATUSES
        or receipt.get("tier") not in TIERS
        or receipt.get("boundary") not in BOUNDARIES
        or receipt.get("owner") not in OWNERS
        or type(receipt.get("required")) is not bool
        or type(receipt.get("reason")) is not str
        or type(receipt.get("duration_seconds")) not in {int, float}
        or receipt.get("duration_seconds", -1) < 0
        or type(receipt.get("stdout_bytes")) is not int
        or type(receipt.get("stderr_bytes")) is not int
        or receipt.get("stdout_bytes", -1) < 0
        or receipt.get("stderr_bytes", -1) < 0
        or any(
            type(receipt.get(field)) is not str
            or DIGEST_PATTERN.fullmatch(receipt[field]) is None
            for field in digest_fields
        )
        or any(
            receipt.get(field) is not None
            and (
                type(receipt[field]) is not str
                or DIGEST_PATTERN.fullmatch(receipt[field]) is None
            )
            for field in optional_digests
        )
        or receipt.get("head_commit") is not None
        and receipt["head_commit"] != "unresolved"
        and (
            type(receipt["head_commit"]) is not str
            or COMMIT_PATTERN.fullmatch(receipt["head_commit"]) is None
        )
        or receipt.get("provider_run_id") is not None
        and type(receipt["provider_run_id"]) is not str
        or receipt.get("observed_at") is not None
        and type(receipt["observed_at"]) is not str
    ):
        raise VerificationPlannerError("invalid verification receipt")
    exit_code = receipt.get("exit_code")
    if exit_code is not None and type(exit_code) is not int:
        raise VerificationPlannerError("invalid verification receipt")
    if receipt["status"] == "passed" and (
        exit_code != 0 or receipt["source_receipt_digest"] is not None
    ):
        raise VerificationPlannerError("invalid passing verification receipt")
    field = "receipt_auth" if version == 1 else "authority_provenance"
    if version == 2 and authority_request is None:
        authority_request = _request_from_provenance(receipt)
    return authority.verify(
        receipt, field, operation="record_result", request=authority_request,
    )


def receipt_index(receipt_ledger, authority):
    authority = _authority(authority)
    if receipt_ledger is None:
        return {}
    if type(receipt_ledger) is dict and type(receipt_ledger.get("receipts")) is list:
        versions = {
            item.get("schema_version") for item in receipt_ledger["receipts"]
            if type(item) is dict
        }
        if (
            len(versions) > 1
            or versions and versions != {authority.write_schema_version}
        ):
            raise VerificationPlannerError("mixed_authority")
    if (
        type(receipt_ledger) is not dict
        or set(receipt_ledger)
        != (
            {"schema_version", "artifact_role", "receipts"}
            if authority.write_schema_version == 1
            else {"schema_version", "artifact_role", "authority_mode", "receipts"}
        )
        or receipt_ledger.get("schema_version") != authority.write_schema_version
        or receipt_ledger.get("artifact_role")
        != "repository_verification_receipts"
        or type(receipt_ledger.get("receipts")) is not list
    ):
        raise VerificationPlannerError("invalid verification receipt ledger")
    result = {}
    for receipt in receipt_ledger["receipts"]:
        receipt = validate_receipt(
            receipt, authority,
            authority_request=_request_from_provenance(receipt),
        )
        if receipt["status"] == "passed":
            result[receipt["cache_key"]] = receipt
    return result


def merge_receipt_ledgers(current, produced, baseline_count, authority):
    """Merge concurrently published authenticated receipts without lost entries."""
    authority = _authority(authority)
    if type(baseline_count) is not int or baseline_count < 0:
        raise VerificationPlannerError("invalid receipt baseline")
    receipt_index(produced, authority)
    produced_receipts = produced["receipts"]
    if baseline_count > len(produced_receipts):
        raise VerificationPlannerError("invalid receipt baseline")
    baseline = produced_receipts[:baseline_count]
    if current is None:
        current_receipts = list(baseline)
    else:
        receipt_index(current, authority)
        current_receipts = list(current["receipts"])
        if (
            len(current_receipts) < baseline_count
            or current_receipts[:baseline_count] != baseline
        ):
            raise VerificationPlannerError(
                "verification receipt ledger history diverged",
            )
    identity_field = (
        "receipt_auth" if authority.write_schema_version == 1
        else "authority_provenance"
    )
    seen = {digest(receipt[identity_field]) for receipt in current_receipts}
    for receipt in produced_receipts[baseline_count:]:
        identity = digest(receipt[identity_field])
        if identity not in seen:
            current_receipts.append(receipt)
            seen.add(identity)
    result = {
        "schema_version": authority.write_schema_version,
        "artifact_role": "repository_verification_receipts",
        "receipts": current_receipts,
    }
    if authority.write_schema_version == 2:
        result["authority_mode"] = "native_provider"
    return result


def _request_from_provenance(document):
    """Reconstruct the exact public request carried by a v2 grant."""
    if type(document) is not dict or document.get("schema_version") != 2:
        return None
    provenance = document.get("authority_provenance")
    grant = provenance.get("grant") if type(provenance) is dict else None
    if type(grant) is not dict:
        return None
    return {
        "schema_version": 2,
        "artifact_role": "workflow_authority_request",
        "operation": grant.get("operation"),
        "bindings": grant.get("bindings"),
        "nonce": grant.get("nonce"),
        "sequence": grant.get("sequence"),
        "key_id": grant.get("key_id"),
        "boot_id": grant.get("boot_id"),
        "session_id": grant.get("session_id"),
        "issued_at": grant.get("issued_at"),
        "expires_at": grant.get("expires_at"),
        "document_digest": provenance.get("envelope", {}).get("document_digest"),
    }
