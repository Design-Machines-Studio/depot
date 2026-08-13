"""Dependency-aware execution for one fresh repository verification plan."""

from __future__ import annotations

import os
from pathlib import Path

from .verification_errors import VerificationPlannerError
from .verification_execution import execution_environment, run_local_command
from .verification_contract import digest
from .verification_planning import build_plan, validate_plan_identity
from .verification_repository import (
    execution_digest, input_digests, validate_profile,
)


RESULT_SCHEMA_VERSION = 1


def _static_result(base, *, status, reason, exit_code=None):
    return {
        **base,
        "status": status,
        "reason": reason,
        "exit_code": exit_code,
        "duration_seconds": 0.0,
        "stdout_digest": None,
        "stderr_digest": None,
        "stdout_bytes": 0,
        "stderr_bytes": 0,
    }


def _dependency_failed(current, current_by_id, outcomes):
    active = (
        dependency for dependency in current["after"]
        if current_by_id[dependency]["disposition"]
        not in {"not_scheduled", "not_triggered"}
    )
    return any(outcomes.get(dependency) != "passed" for dependency in active)


def _execution_closure_matches(profile, repository, environment, expected):
    try:
        return execution_digest(profile, repository, environment) == expected
    except VerificationPlannerError:
        return False


def execute_plan(profile_document, repository_root, plan, *, environment=None):
    """Revalidate and execute one plan without persistent result reuse."""
    profile = validate_profile(profile_document)
    if type(plan) is not dict:
        raise VerificationPlannerError("verification plan must be an object")
    profile_digest = digest(profile)
    environment = dict(os.environ if environment is None else environment)
    request = plan.get("request", {})
    expected = build_plan(
        profile_document, repository_root, plan.get("profile_ref", ""), None,
        request.get("boundary"), request.get("risk"),
        base_commit=request.get("base_commit"),
        head_commit=request.get("head_commit", "unresolved"),
        include_worktree=request.get("include_worktree", False),
        environment=environment,
    )
    validate_plan_identity(plan, expected)
    results = []
    failed = False
    pending = False
    repository = Path(repository_root).resolve(strict=True)
    command_environment = execution_environment(profile, environment)
    profile_by_id = {lane["id"]: lane for lane in profile["lanes"]}
    current_by_id = {lane["id"]: lane for lane in expected["lanes"]}
    outcomes = {}
    expected_closure = expected["execution_closure_digest"]
    for planned in plan["lanes"]:
        current = current_by_id[planned["id"]]
        profile_lane = profile_by_id[planned["id"]]
        disposition = current["disposition"]
        if disposition in {"not_scheduled", "not_triggered"}:
            outcomes[current["id"]] = "skipped"
            continue
        base = {
            "lane_id": current["id"],
            "tier": current["tier"],
            "owner": current["owner"],
            "required": current["required"],
            "command_digest": current["command_digest"],
            "input_digest": current["input_digest"],
        }
        if _dependency_failed(current, current_by_id, outcomes):
            results.append(_static_result(
                base, status="blocked", reason="dependency_not_passed",
            ))
            outcomes[current["id"]] = "blocked"
            failed = failed or current["required"]
            continue
        if expected["status"] == "blocked" and disposition == "run":
            results.append(_static_result(
                base, status="blocked",
                reason="plan_blocked_by_required_lane",
            ))
            outcomes[current["id"]] = "blocked"
            failed = True
            continue
        if disposition in {"remote", "blocked", "unavailable"}:
            status = {
                "remote": "remote_pending",
                "blocked": "blocked",
                "unavailable": "unavailable",
            }[disposition]
            results.append(_static_result(
                base, status=status, reason=current["reason"],
            ))
            failed = failed or (
                disposition == "blocked" and current["required"]
            )
            pending = pending or (
                disposition == "remote" and current["required"]
            )
            outcomes[current["id"]] = status
            continue
        if not _execution_closure_matches(
            profile, repository, environment, expected_closure,
        ):
            results.append(_static_result(
                base, status="failed", reason="execution_closure_changed",
            ))
            outcomes[current["id"]] = "failed"
            failed = True
            break
        result = run_local_command(repository, {
            **profile_lane, "argv": current["argv"],
        }, command_environment)
        if not _execution_closure_matches(
            profile, repository, environment, expected_closure,
        ):
            result = {
                **result, "status": "failed",
                "reason": "execution_closure_changed",
            }
        results.append({**base, **result})
        outcomes[current["id"]] = result["status"]
        failed = failed or (
            result["status"] == "failed" and current["required"]
        )
        if result["reason"] == "execution_closure_changed":
            failed = True
            break
        if result["status"] == "passed" and profile_lane["mutates_repository"]:
            refreshed = build_plan(
                profile_document, repository, plan["profile_ref"], None,
                request["boundary"], request["risk"],
                base_commit=request["base_commit"],
                head_commit=request["head_commit"],
                include_worktree=request.get("include_worktree", False),
                environment=environment, _allow_declared_mutation=True,
            )
            current_by_id = {
                lane["id"]: lane for lane in refreshed["lanes"]
            }
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
        results.append(_static_result({
            "lane_id": stale_id,
            "tier": profile_by_id[stale_id]["tier"],
            "owner": profile_by_id[stale_id]["owner"],
            "required": True,
            "command_digest": current_by_id[stale_id]["command_digest"],
            "input_digest": current_by_id[stale_id]["input_digest"],
        }, status="failed", reason="undeclared_repository_mutation"))
    outcome = "failed" if failed else "pending" if pending else "complete"
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "artifact_role": "repository_verification_result",
        "plan_digest": digest(expected),
        "profile_digest": profile_digest,
        "execution_closure_digest": expected["execution_closure_digest"],
        "repository_scope_digest": expected["repository_scope_digest"],
        "request": expected["request"],
        "head_commit": request["head_commit"],
        "status": outcome,
        "lanes": results,
    }
