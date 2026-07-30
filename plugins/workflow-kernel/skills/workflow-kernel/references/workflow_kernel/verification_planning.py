"""Lane selection, cache policy, and immutable plan identity."""

from __future__ import annotations

import os
from pathlib import Path

from .verification_authority import (
    checkout_changed_paths, validate_profile_approval,
)
from .verification_contract import BOUNDARIES
from .verification_errors import VerificationPlannerError
from .verification_repository import (
    PLAN_SCHEMA_VERSION, RISKS, authority_digest, authority_patterns,
    environment_digest, expanded_argv, input_digests, matches,
    normalize_changed_paths, repository_file, resolve_commit,
    tree_input_digests, validate_profile,
)
from .verification_receipts import digest, receipt_index


def _select_lane(lane, changed_paths, boundary, risk):
    if boundary not in lane["cadences"] or risk not in lane["risks"]:
        return "not_scheduled", "cadence_mismatch", [], []
    terminal_required = (
        lane["required"] and boundary in {"merge_candidate", "post_merge"}
    )
    if (
        lane["changed_paths"] and not terminal_required
        and not any(
            matches(path, lane["changed_paths"]) for path in changed_paths
        )
    ):
        return "not_triggered", "changed_paths_do_not_match", [], []
    argv, packages = expanded_argv(lane, changed_paths)
    if lane["package_selector"] == "go_changed" and not packages:
        return "not_triggered", "no_changed_go_packages", [], []
    return "selected", "lane_selected", argv, packages


def _receipt_reusable(
    receipt, lane, profile_digest, command_digest, input_digest, head_commit,
):
    return (
        receipt["profile_digest"] == profile_digest
        and receipt["lane_id"] == lane["id"]
        and receipt["tier"] == lane["tier"]
        and receipt["owner"] == lane["owner"]
        and receipt["command_digest"] == command_digest
        and receipt["input_digest"] == input_digest
        and receipt["exit_code"] == 0
        and (
            lane["owner"] == "local"
            or receipt["head_commit"] == head_commit
        )
    )


def _plan_selected_lane(
    lane, argv, packages, input_digest, profile_digest, environment, prior,
    head_commit,
):
    command_digest = digest(argv)
    environment_digest_value = environment_digest(
        lane["cache_environment"], environment,
    )
    cache_identity = {
        "profile_digest": profile_digest,
        "lane_id": lane["id"],
        "argv": argv,
        "input_digest": input_digest,
        "environment_digest": environment_digest_value,
    }
    if lane["owner"] != "local":
        cache_identity["head_commit"] = head_commit
    cache_key = digest(cache_identity)
    missing = [
        name for name in lane["required_environment"]
        if not environment.get(name)
    ]
    if missing:
        disposition = "blocked" if lane["required"] else "unavailable"
        reason = "required_environment_missing"
    else:
        source = prior.get(cache_key)
        if (
            lane["cache"] == "content" and source is not None
            and _receipt_reusable(
                source, lane, profile_digest, command_digest, input_digest,
                head_commit,
            )
        ):
            disposition = "reuse"
            reason = "matching_authenticated_receipt"
        elif lane["owner"] == "local":
            disposition = "run"
            reason = "scheduled_local_lane"
        elif lane["owner"] == "unresolved":
            disposition = "blocked" if lane["required"] else "unavailable"
            reason = "lane_owner_unresolved"
        else:
            disposition = "remote"
            reason = f"owned_by_{lane['owner']}"
    return {
        "id": lane["id"],
        "tier": lane["tier"],
        "owner": lane["owner"],
        "required": lane["required"],
        "cache": lane["cache"],
        "after": lane["after"],
        "disposition": disposition,
        "reason": reason,
        "argv": argv,
        "packages": packages,
        "input_digest": input_digest,
        "command_digest": command_digest,
        "cache_key": cache_key,
    }


def build_plan(profile_document, repository_root, profile_ref, changed_paths,
               boundary, risk, *, receipt_ledger=None, receipt_key=None,
               approval=None, head_commit="unresolved", environment=None,
               _allow_declared_mutation=False):
    """Build the exact tiered verification plan for one workflow boundary."""
    profile = validate_profile(profile_document)
    repository = Path(repository_root).resolve(strict=True)
    if not repository.is_dir():
        raise VerificationPlannerError("repository root must be a directory")
    profile_ref = repository_file(
        repository, profile_ref, "profile_ref",
    )
    if head_commit == "unresolved":
        raise VerificationPlannerError(
            "repository verification requires an exact candidate commit",
        )
    head_commit = resolve_commit(repository, head_commit, "head_commit")
    if boundary not in BOUNDARIES or risk not in RISKS:
        raise VerificationPlannerError("invalid verification boundary or risk")
    changed_paths = normalize_changed_paths(changed_paths)
    if approval is None:
        raise VerificationPlannerError("verification profile approval is required")
    if (
        boundary in {"merge_candidate", "post_merge"}
        and approval.get("include_worktree") is not False
    ):
        raise VerificationPlannerError(
            "exact-SHA terminal verification requires a clean committed candidate",
        )
    authoritative_changed_paths = (
        checkout_changed_paths(
            repository, approval.get("trusted_base_commit", ""),
            approval.get("candidate_commit", ""),
            True,
        )
        if _allow_declared_mutation
        else normalize_changed_paths(approval.get("changed_paths"))
    )
    if head_commit != approval.get("candidate_commit"):
        raise VerificationPlannerError(
            "verification request differs from the host-approved candidate",
        )
    if _allow_declared_mutation:
        changed_paths = authoritative_changed_paths
    elif changed_paths != authoritative_changed_paths:
        raise VerificationPlannerError(
            "verification request differs from the host-approved candidate",
        )
    environment = dict(os.environ if environment is None else environment)
    profile_digest = digest(profile)
    selections = [
        (lane, *_select_lane(lane, changed_paths, boundary, risk))
        for lane in profile["lanes"]
    ]
    pattern_sets = {
        tuple(lane["input_paths"])
        for lane, disposition, _reason, _argv, _packages in selections
        if disposition == "selected" and lane["input_paths"]
    }
    authority_path_patterns = authority_patterns(profile)
    pattern_sets.add(authority_path_patterns)
    input_digest_map = input_digests(repository, pattern_sets)
    if boundary in {"merge_candidate", "post_merge"}:
        committed_input_digests = tree_input_digests(
            repository, head_commit, pattern_sets,
        )
        if committed_input_digests != input_digest_map:
            raise VerificationPlannerError(
                "terminal verification inputs differ from the candidate commit",
            )
        input_digest_map = committed_input_digests
    approval = validate_profile_approval(
        approval, profile_document, repository, profile_ref, receipt_key,
        environment=environment,
        authority_digest=authority_digest(
            profile, repository, environment,
            path_digest=input_digest_map[authority_path_patterns],
        ),
        allow_declared_mutation=_allow_declared_mutation,
    )
    if (
        not _allow_declared_mutation
        and approval["changed_paths_digest"] != digest(changed_paths)
    ):
        raise VerificationPlannerError(
            "verification changed paths differ from the sealed approval",
        )
    prior = receipt_index(receipt_ledger, receipt_key)
    lanes = []
    blocked = False
    for lane, disposition, reason, argv, packages in selections:
        if disposition == "selected":
            input_key = tuple(lane["input_paths"])
            input_digest = (
                input_digest_map[input_key] if input_key else digest([])
            )
            planned = _plan_selected_lane(
                lane, argv, packages, input_digest, profile_digest,
                environment, prior, head_commit,
            )
            blocked = blocked or (
                planned["disposition"] == "blocked" and lane["required"]
            )
        else:
            planned = {
                "id": lane["id"],
                "tier": lane["tier"],
                "owner": lane["owner"],
                "required": lane["required"],
                "cache": lane["cache"],
                "after": lane["after"],
                "disposition": disposition,
                "reason": reason,
                "argv": argv,
                "packages": packages,
                "input_digest": None,
                "command_digest": None,
                "cache_key": None,
            }
        lanes.append(planned)
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "artifact_role": "repository_verification_plan",
        "profile_id": profile["profile_id"],
        "profile_ref": profile_ref,
        "profile_digest": profile_digest,
        "approval_digest": digest(approval),
        "repository_scope_digest": approval["repository_scope_digest"],
        "run_id": approval["run_id"],
        "trusted_base_commit": approval["trusted_base_commit"],
        "request": {
            "boundary": boundary,
            "risk": risk,
            "base_commit": approval["trusted_base_commit"],
            "head_commit": head_commit,
            "changed_paths": changed_paths,
        },
        "status": "blocked" if blocked else "ready",
        "lanes": lanes,
    }


def validate_plan_identity(plan, expected):
    if type(plan) is not dict:
        raise VerificationPlannerError("verification plan must be an object")
    for field in (
        "schema_version", "artifact_role", "profile_id", "profile_ref",
        "profile_digest", "approval_digest", "repository_scope_digest",
        "run_id", "trusted_base_commit", "request",
    ):
        if plan.get(field) != expected.get(field):
            raise VerificationPlannerError("verification plan authority is stale")
    actual_lanes = plan.get("lanes")
    if type(actual_lanes) is not list or len(actual_lanes) != len(expected["lanes"]):
        raise VerificationPlannerError("verification plan lane set is stale")
    immutable = {
        "id", "tier", "owner", "required", "cache", "argv", "packages",
        "input_digest", "command_digest", "cache_key", "after",
    }
    for actual, current in zip(actual_lanes, expected["lanes"]):
        if type(actual) is not dict or any(
            actual.get(field) != current.get(field) for field in immutable
        ):
            raise VerificationPlannerError("verification plan lane authority is stale")
        dispositions = {actual.get("disposition"), current.get("disposition")}
        if len(dispositions) > 1 and dispositions != {"run", "reuse"}:
            raise VerificationPlannerError("verification plan disposition is stale")
