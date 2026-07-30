"""Admission of broker-attested provider evidence for remote verification."""

from __future__ import annotations

import os

from .verification_errors import VerificationPlannerError
from .verification_planning import build_plan, validate_plan_identity
from .verification_repository import timestamp, validate_profile
from .verification_receipts import (
    RECEIPT_SCHEMA_VERSION, digest, receipt_key as validate_receipt_key,
    sign_receipt,
    validate_provider_attestation,
)


def record_provider_result(
    profile_document, repository_root, plan, *,
    approval, receipt_ledger, receipt_key: bytes, lane_id,
    provider_attestation, environment=None,
):
    """Import one broker-attested exact-head result for a remote-owned lane."""
    key = validate_receipt_key(receipt_key)
    if type(plan) is not dict:
        raise VerificationPlannerError("verification plan must be an object")
    attestation = validate_provider_attestation(provider_attestation, key)
    provider = attestation["provider"]
    head_commit = attestation["head_commit"]
    observed_at = timestamp(attestation["observed_at"], "observed_at")
    environment = dict(os.environ if environment is None else environment)
    request = plan.get("request", {})
    if request.get("head_commit") != head_commit:
        raise VerificationPlannerError(
            "provider result does not match the planned commit",
        )
    expected = build_plan(
        profile_document, repository_root, plan.get("profile_ref", ""),
        request.get("changed_paths", []), request.get("boundary"),
        request.get("risk"), receipt_ledger=receipt_ledger,
        receipt_key=key, approval=approval,
        head_commit=head_commit, environment=environment,
    )
    validate_plan_identity(plan, expected)
    lane = {item["id"]: item for item in expected["lanes"]}.get(lane_id)
    if (
        lane is None or lane["owner"] != provider
        or provider in {"local", "unresolved"}
        or lane["disposition"] != "remote"
    ):
        raise VerificationPlannerError(
            "provider result does not match a pending remote lane",
        )
    profile = validate_profile(profile_document)
    receipt = sign_receipt({
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "profile_digest": digest(profile),
        "lane_id": lane["id"],
        "tier": lane["tier"],
        "boundary": request["boundary"],
        "owner": lane["owner"],
        "required": lane["required"],
        "status": attestation["outcome"],
        "reason": "authenticated_provider_result",
        "command_digest": lane["command_digest"],
        "input_digest": lane["input_digest"],
        "cache_key": lane["cache_key"],
        "exit_code": attestation["exit_code"],
        "duration_seconds": 0.0,
        "source_receipt_digest": None,
        "stdout_digest": None,
        "stderr_digest": None,
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "head_commit": head_commit,
        "provider_run_id": attestation["provider_run_id"],
        "observed_at": observed_at,
        "evidence_digest": attestation["evidence_digest"],
    }, key)
    prior = [] if receipt_ledger is None else list(receipt_ledger["receipts"])
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "artifact_role": "repository_verification_receipts",
        "receipts": [*prior, receipt],
    }
