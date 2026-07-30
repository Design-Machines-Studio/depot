"""Dependency-aware execution orchestration for repository verification plans."""

from __future__ import annotations

import os
from pathlib import Path

from .verification_planning import build_plan, validate_plan_identity
from .verification_errors import VerificationPlannerError
from .verification_execution import execution_environment, run_local_command
from .verification_repository import input_digests, validate_profile
from .verification_receipts import (
    RECEIPT_SCHEMA_VERSION, digest, receipt_index,
    receipt_key as validate_receipt_key, sign_receipt,
)


def _static_receipt(base, key, *, status, reason, exit_code=None,
                    source_receipt_digest=None):
    return sign_receipt({
        **base,
        "status": status,
        "reason": reason,
        "exit_code": exit_code,
        "duration_seconds": 0.0,
        "source_receipt_digest": source_receipt_digest,
        "stdout_digest": None,
        "stderr_digest": None,
        "stdout_bytes": 0,
        "stderr_bytes": 0,
    }, key)


def _dependency_failed(current, current_by_id, outcomes):
    active = (
        dependency for dependency in current["after"]
        if current_by_id[dependency]["disposition"]
        not in {"not_scheduled", "not_triggered"}
    )
    return any(outcomes.get(dependency) != "passed" for dependency in active)


def execute_plan(profile_document, repository_root, plan, *,
                 receipt_ledger=None, receipt_key=None,
                 approval=None, environment=None):
    """Execute host-approved local lanes and return an authenticated ledger."""
    key = validate_receipt_key(receipt_key)
    profile = validate_profile(profile_document)
    if type(plan) is not dict:
        raise VerificationPlannerError("verification plan must be an object")
    profile_digest = digest(profile)
    environment = dict(os.environ if environment is None else environment)
    request = plan.get("request", {})
    expected = build_plan(
        profile_document, repository_root, plan.get("profile_ref", ""),
        request.get("changed_paths", []), request.get("boundary"),
        request.get("risk"), receipt_ledger=receipt_ledger,
        receipt_key=key, approval=approval,
        head_commit=request.get("head_commit", "unresolved"),
        environment=environment,
    )
    validate_plan_identity(plan, expected)
    prior_receipts = [] if receipt_ledger is None else list(
        receipt_ledger["receipts"],
    )
    prior = receipt_index(receipt_ledger, key)
    receipts = []
    failed = False
    pending = False
    repository = Path(repository_root).resolve(strict=True)
    command_environment = execution_environment(profile, environment)
    profile_by_id = {lane["id"]: lane for lane in profile["lanes"]}
    current_by_id = {lane["id"]: lane for lane in expected["lanes"]}
    outcomes = {}
    for planned in plan["lanes"]:
        current = current_by_id[planned["id"]]
        profile_lane = profile_by_id[planned["id"]]
        disposition = current["disposition"]
        if disposition in {"not_scheduled", "not_triggered"}:
            outcomes[current["id"]] = "skipped"
            continue
        base = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "profile_digest": profile_digest,
            "lane_id": current["id"],
            "tier": current["tier"],
            "boundary": request["boundary"],
            "owner": current["owner"],
            "required": current["required"],
            "command_digest": current["command_digest"],
            "input_digest": current["input_digest"],
            "cache_key": current["cache_key"],
            "head_commit": request["head_commit"],
            "provider_run_id": None,
            "observed_at": None,
            "evidence_digest": None,
        }
        if _dependency_failed(current, current_by_id, outcomes):
            receipts.append(_static_receipt(
                base, key, status="blocked", reason="dependency_not_passed",
            ))
            outcomes[current["id"]] = "blocked"
            failed = failed or current["required"]
            continue
        if expected["status"] == "blocked" and disposition == "run":
            receipts.append(_static_receipt(
                base, key, status="blocked",
                reason="plan_blocked_by_required_lane",
            ))
            outcomes[current["id"]] = "blocked"
            failed = True
            continue
        if disposition == "reuse":
            source = prior[current["cache_key"]]
            receipts.append(_static_receipt(
                base, key, status="reused",
                reason="matching_passing_receipt", exit_code=0,
                source_receipt_digest=digest(source),
            ))
            outcomes[current["id"]] = "passed"
            continue
        if disposition in {"remote", "blocked", "unavailable"}:
            status = {
                "remote": "remote_pending",
                "blocked": "blocked",
                "unavailable": "unavailable",
            }[disposition]
            receipts.append(_static_receipt(
                base, key, status=status, reason=current["reason"],
            ))
            failed = failed or (
                disposition == "blocked" and current["required"]
            )
            pending = pending or (
                disposition == "remote" and current["required"]
            )
            outcomes[current["id"]] = status
            continue
        result = run_local_command(repository, {
            **profile_lane, "argv": current["argv"],
        }, command_environment)
        receipts.append(sign_receipt({**base, **result}, key))
        outcomes[current["id"]] = result["status"]
        failed = failed or (
            result["status"] == "failed" and current["required"]
        )
        if result["status"] == "passed" and profile_lane["mutates_repository"]:
            interim = {
                "schema_version": RECEIPT_SCHEMA_VERSION,
                "artifact_role": "repository_verification_receipts",
                "receipts": [*prior_receipts, *receipts],
            }
            refreshed = build_plan(
                profile_document, repository, plan["profile_ref"],
                request["changed_paths"], request["boundary"], request["risk"],
                receipt_ledger=interim, receipt_key=key,
                approval=approval, head_commit=request["head_commit"],
                environment=environment, _allow_declared_mutation=True,
            )
            current_by_id = {
                lane["id"]: lane for lane in refreshed["lanes"]
            }
            prior = receipt_index(interim, key)
    final_patterns = {
        tuple(profile_by_id[lane_id]["input_paths"])
        for lane_id, current in current_by_id.items()
        if current["input_digest"] is not None
        and profile_by_id[lane_id]["input_paths"]
    }
    final_digests = input_digests(repository, final_patterns)
    stale_final_inputs = [
        lane_id for lane_id, current in current_by_id.items()
        if current["input_digest"] is not None
        and profile_by_id[lane_id]["input_paths"]
        and final_digests[tuple(profile_by_id[lane_id]["input_paths"])]
        != current["input_digest"]
    ]
    if stale_final_inputs:
        failed = True
        stale_id = stale_final_inputs[0]
        receipts.append(sign_receipt({
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "profile_digest": profile_digest,
            "lane_id": stale_id,
            "tier": profile_by_id[stale_id]["tier"],
            "boundary": request["boundary"],
            "owner": profile_by_id[stale_id]["owner"],
            "required": True,
            "status": "failed",
            "reason": "undeclared_repository_mutation",
            "command_digest": current_by_id[stale_id]["command_digest"],
            "input_digest": current_by_id[stale_id]["input_digest"],
            "cache_key": current_by_id[stale_id]["cache_key"],
            "head_commit": request["head_commit"],
            "provider_run_id": None,
            "observed_at": None,
            "evidence_digest": None,
            "exit_code": None,
            "duration_seconds": 0.0,
            "source_receipt_digest": None,
            "stdout_digest": None,
            "stderr_digest": None,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
        }, key))
    ledger = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "artifact_role": "repository_verification_receipts",
        "receipts": [*prior_receipts, *receipts],
    }
    outcome = "failed" if failed else "pending" if pending else "complete"
    return ledger, outcome
