"""Authenticated approval and receipt storage for repository verification."""

from __future__ import annotations

import hashlib
import hmac
import json
from .verification_contract import (
    AUTH_PATTERN, BOUNDARIES, COMMIT_PATTERN, DIGEST_PATTERN, OWNERS, TIERS,
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
RECEIPT_STATUSES = frozenset({
    "passed", "failed", "reused", "remote_pending", "blocked", "unavailable",
})
PROVIDER_ATTESTATION_KEYS = frozenset({
    "schema_version", "artifact_role", "provider", "provider_run_id",
    "head_commit", "evidence_digest", "observed_at", "outcome", "exit_code",
    "attestation_auth",
})


def canonical_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def receipt_key(value):
    if type(value) is not bytes or len(value) < 32:
        raise VerificationPlannerError(
            "verification receipt key must contain at least 32 bytes",
        )
    return value


def _hmac(document, field, key):
    payload = {name: value for name, value in document.items() if name != field}
    return "hmac-sha256:" + hmac.new(
        receipt_key(key), canonical_bytes(payload), hashlib.sha256,
    ).hexdigest()


def seal_approval(fields, key):
    result = {**fields, "approval_auth": ""}
    result["approval_auth"] = _hmac(result, "approval_auth", key)
    return result


def seal_provider_attestation(fields, key):
    """Seal provider-native evidence after trusted host verification.

    This primitive is for the host authority broker. Repository workflows only
    consume its output through ``record-verification-result``.
    """
    result = {**fields, "attestation_auth": ""}
    result["attestation_auth"] = _hmac(result, "attestation_auth", key)
    return result


def validate_provider_attestation(document, key):
    """Validate a broker-sealed, exact-head provider evidence decision."""
    if (
        type(document) is not dict
        or set(document) != set(PROVIDER_ATTESTATION_KEYS)
        or document.get("schema_version") != 1
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
        or type(document.get("attestation_auth")) is not str
        or AUTH_PATTERN.fullmatch(document["attestation_auth"]) is None
        or not hmac.compare_digest(
            document["attestation_auth"],
            _hmac(document, "attestation_auth", key),
        )
    ):
        raise VerificationPlannerError(
            "provider result is not attested by the host broker",
        )
    return document


def validate_approval_document(approval, expected, key):
    if (
        type(approval) is not dict
        or set(approval) != set(expected)
        or approval != expected
        or type(approval.get("approval_auth")) is not str
        or AUTH_PATTERN.fullmatch(approval["approval_auth"]) is None
        or not hmac.compare_digest(
            approval["approval_auth"], _hmac(approval, "approval_auth", key),
        )
    ):
        raise VerificationPlannerError(
            "verification profile is not approved by the host",
        )
    return approval


def receipt_auth(receipt, key):
    return _hmac(receipt, "receipt_auth", key)


def sign_receipt(receipt, key):
    result = {**receipt, "receipt_auth": ""}
    result["receipt_auth"] = receipt_auth(result, key)
    return result


def validate_receipt(receipt, key):
    if type(receipt) is not dict or set(receipt) != set(RECEIPT_KEYS):
        raise VerificationPlannerError("invalid verification receipt")
    digest_fields = {
        "profile_digest", "command_digest", "input_digest", "cache_key",
    }
    optional_digests = {
        "source_receipt_digest", "stdout_digest", "stderr_digest",
        "evidence_digest",
    }
    if (
        receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
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
        or type(receipt.get("receipt_auth")) is not str
        or AUTH_PATTERN.fullmatch(receipt["receipt_auth"]) is None
        or not hmac.compare_digest(
            receipt["receipt_auth"], receipt_auth(receipt, key),
        )
    ):
        raise VerificationPlannerError("invalid verification receipt")
    exit_code = receipt.get("exit_code")
    if exit_code is not None and type(exit_code) is not int:
        raise VerificationPlannerError("invalid verification receipt")
    if receipt["status"] == "passed" and (
        exit_code != 0 or receipt["source_receipt_digest"] is not None
    ):
        raise VerificationPlannerError("invalid passing verification receipt")
    return receipt


def receipt_index(receipt_ledger, key):
    if receipt_ledger is None:
        return {}
    if (
        type(receipt_ledger) is not dict
        or set(receipt_ledger)
        != {"schema_version", "artifact_role", "receipts"}
        or receipt_ledger.get("schema_version") != RECEIPT_SCHEMA_VERSION
        or receipt_ledger.get("artifact_role")
        != "repository_verification_receipts"
        or type(receipt_ledger.get("receipts")) is not list
    ):
        raise VerificationPlannerError("invalid verification receipt ledger")
    result = {}
    for receipt in receipt_ledger["receipts"]:
        receipt = validate_receipt(receipt, key)
        if receipt["status"] == "passed":
            result[receipt["cache_key"]] = receipt
    return result


def merge_receipt_ledgers(current, produced, baseline_count, key):
    """Merge concurrently published authenticated receipts without lost entries."""
    key = receipt_key(key)
    if type(baseline_count) is not int or baseline_count < 0:
        raise VerificationPlannerError("invalid receipt baseline")
    receipt_index(produced, key)
    produced_receipts = produced["receipts"]
    if baseline_count > len(produced_receipts):
        raise VerificationPlannerError("invalid receipt baseline")
    baseline = produced_receipts[:baseline_count]
    if current is None:
        current_receipts = list(baseline)
    else:
        receipt_index(current, key)
        current_receipts = list(current["receipts"])
        if (
            len(current_receipts) < baseline_count
            or current_receipts[:baseline_count] != baseline
        ):
            raise VerificationPlannerError(
                "verification receipt ledger history diverged",
            )
    seen = {receipt["receipt_auth"] for receipt in current_receipts}
    for receipt in produced_receipts[baseline_count:]:
        if receipt["receipt_auth"] not in seen:
            current_receipts.append(receipt)
            seen.add(receipt["receipt_auth"])
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "artifact_role": "repository_verification_receipts",
        "receipts": current_receipts,
    }
