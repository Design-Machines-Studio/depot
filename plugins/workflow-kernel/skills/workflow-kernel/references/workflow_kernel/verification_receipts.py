"""Deterministic local receipt storage for repository verification."""

from __future__ import annotations

import hashlib
import json

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
    "stdout_bytes", "stderr_bytes", "head_commit",
})
RECEIPT_STATUSES = frozenset({
    "passed", "failed", "reused", "remote_pending", "blocked", "unavailable",
})


def canonical_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_receipt(receipt):
    if type(receipt) is not dict or set(receipt) != set(RECEIPT_KEYS):
        raise VerificationPlannerError("invalid verification receipt")
    digest_fields = {
        "profile_digest", "command_digest", "input_digest", "cache_key",
    }
    optional_digests = {
        "source_receipt_digest", "stdout_digest", "stderr_digest",
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
        or type(receipt.get("head_commit")) is not str
        or COMMIT_PATTERN.fullmatch(receipt["head_commit"]) is None
    ):
        raise VerificationPlannerError("invalid verification receipt")
    exit_code = receipt.get("exit_code")
    if exit_code is not None and type(exit_code) is not int:
        raise VerificationPlannerError("invalid verification receipt")
    if receipt["status"] == "passed" and (
        exit_code != 0 or receipt["source_receipt_digest"] is not None
    ):
        raise VerificationPlannerError("invalid passing verification receipt")
    if receipt["status"] == "reused" and (
        exit_code != 0 or receipt["source_receipt_digest"] is None
    ):
        raise VerificationPlannerError("invalid reused verification receipt")
    return receipt


def receipt_index(receipt_ledger):
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
        receipt = validate_receipt(receipt)
        if receipt["status"] == "passed" and receipt["owner"] == "local":
            result[receipt["cache_key"]] = receipt
    return result


def merge_receipt_ledgers(current, produced, baseline_count):
    """Merge concurrently published deterministic receipts without lost entries."""
    if type(baseline_count) is not int or baseline_count < 0:
        raise VerificationPlannerError("invalid receipt baseline")
    receipt_index(produced)
    produced_receipts = produced["receipts"]
    if baseline_count > len(produced_receipts):
        raise VerificationPlannerError("invalid receipt baseline")
    baseline = produced_receipts[:baseline_count]
    if current is None:
        current_receipts = list(baseline)
    else:
        receipt_index(current)
        current_receipts = list(current["receipts"])
        if (
            len(current_receipts) < baseline_count
            or current_receipts[:baseline_count] != baseline
        ):
            raise VerificationPlannerError(
                "verification receipt ledger history diverged",
            )
    seen = {digest(receipt) for receipt in current_receipts}
    for receipt in produced_receipts[baseline_count:]:
        receipt_digest = digest(receipt)
        if receipt_digest not in seen:
            current_receipts.append(receipt)
            seen.add(receipt_digest)
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "artifact_role": "repository_verification_receipts",
        "receipts": current_receipts,
    }
