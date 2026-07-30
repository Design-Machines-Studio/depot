"""Trusted-base approval issuance and validation for repository verification."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import verification_repository as repository_api
from .verification_contract import byte_digest
from .verification_errors import VerificationPlannerError
from .verification_receipts import (
    digest, receipt_key as validate_receipt_key, seal_approval,
    validate_approval_document,
)


APPROVAL_KEYS = frozenset({
    "schema_version", "artifact_role", "repository_scope_digest",
    "profile_id", "profile_ref", "profile_digest", "authority_digest",
    "trusted_base_commit", "candidate_commit", "include_worktree",
    "changed_paths", "changed_paths_digest", "candidate_snapshot_digest",
    "run_id", "authorization_event_id", "approved_at", "authority_key_id",
    "approval_auth",
})


def _trusted_profile(repository, commit, profile_ref):
    try:
        return repository_api.validate_profile(json.loads(
            repository_api.git_file(
                repository, commit, profile_ref, "profile_ref",
            ).decode("utf-8"),
        ))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise VerificationPlannerError(
            "trusted base verification profile is invalid",
        ) from None


def checkout_changed_paths(
    repository, trusted_base_commit, candidate_commit, include_worktree,
):
    if repository_api.resolve_commit(repository, "HEAD", "HEAD") != candidate_commit:
        raise VerificationPlannerError(
            "current HEAD differs from the approved candidate commit",
        )
    committed = repository_api.git_changed_paths(
        repository, trusted_base_commit, head_ref=candidate_commit,
    )
    complete = repository_api.git_changed_paths(
        repository, trusted_base_commit, head_ref=candidate_commit,
        include_worktree=True,
    )
    status = subprocess.run(
        [
            "git", "-C", str(repository), "status", "--porcelain=v1", "-z",
            "--untracked-files=all",
        ],
        capture_output=True, check=False,
    )
    if status.returncode != 0:
        raise VerificationPlannerError("unable to inspect candidate checkout")
    if not include_worktree and status.stdout:
        raise VerificationPlannerError(
            "approved committed candidate requires a clean index and worktree",
        )
    return complete if include_worktree else committed


def _candidate_snapshot_digest(repository, changed_paths):
    records = []
    repository_fd = os.open(
        repository, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        for relative in changed_paths:
            try:
                os.lstat(repository / relative)
            except FileNotFoundError:
                records.append([relative, "missing"])
                continue
            mode, content_digest = repository_api.hash_repository_file(
                repository_fd, relative,
            )
            records.append([relative, mode, content_digest])
    finally:
        os.close(repository_fd)
    return digest(records)


def issue_profile_approval(
    profile_document, repository_root, profile_ref, *,
    trusted_base_commit, run_id, authorization_event_id, approved_at,
    receipt_key: bytes, candidate_commit=None, include_worktree=False,
    environment=None,
):
    """Seal immutable host authority for one trusted profile and candidate."""
    key = validate_receipt_key(receipt_key)
    profile = repository_api.validate_profile(profile_document)
    repository = Path(repository_root).resolve(strict=True)
    profile_ref = repository_api.repository_file(
        repository, profile_ref, "profile_ref",
    )
    trusted_base_commit = repository_api.resolve_commit(
        repository, trusted_base_commit, "trusted_base_commit",
    )
    candidate_commit = repository_api.resolve_commit(
        repository, candidate_commit or trusted_base_commit, "candidate_commit",
    )
    if type(include_worktree) is not bool:
        raise VerificationPlannerError("include_worktree must be boolean")
    run_id = repository_api.bounded_string(run_id, "run_id")
    authorization_event_id = repository_api.bounded_string(
        authorization_event_id, "authorization_event_id",
    )
    environment = dict(os.environ if environment is None else environment)
    trusted_profile = _trusted_profile(
        repository, trusted_base_commit, profile_ref,
    )
    if trusted_profile != profile:
        raise VerificationPlannerError(
            "current verification profile differs from the trusted base",
        )
    trusted_authority_digest = repository_api.authority_digest_at_commit(
        profile, repository, trusted_base_commit, environment,
    )
    if (
        repository_api.authority_digest(profile, repository, environment)
        != trusted_authority_digest
    ):
        raise VerificationPlannerError(
            "current verification authority differs from the trusted base",
        )
    changed_paths = checkout_changed_paths(
        repository, trusted_base_commit, candidate_commit, include_worktree,
    )
    return seal_approval({
        "schema_version": 1,
        "artifact_role": "repository_verification_profile_approval",
        "repository_scope_digest": repository_api.repository_scope_digest(repository),
        "profile_id": profile["profile_id"],
        "profile_ref": profile_ref,
        "profile_digest": digest(profile),
        "authority_digest": trusted_authority_digest,
        "trusted_base_commit": trusted_base_commit,
        "candidate_commit": candidate_commit,
        "include_worktree": include_worktree,
        "changed_paths": changed_paths,
        "changed_paths_digest": digest(changed_paths),
        "candidate_snapshot_digest": _candidate_snapshot_digest(
            repository, changed_paths,
        ),
        "run_id": run_id,
        "authorization_event_id": authorization_event_id,
        "approved_at": repository_api.timestamp(approved_at, "approved_at"),
        "authority_key_id": byte_digest(key),
    }, key)


def validate_profile_approval(
    approval, profile_document, repository_root, profile_ref, receipt_key,
    *, environment=None, authority_digest=None,
    allow_declared_mutation=False,
):
    """Validate the sealed approval and current trusted execution closure."""
    key = validate_receipt_key(receipt_key)
    repository_api.closed_document(
        approval, APPROVAL_KEYS, "verification profile approval",
    )
    if set(approval) != set(APPROVAL_KEYS):
        raise VerificationPlannerError("invalid verification profile approval")
    profile = repository_api.validate_profile(profile_document)
    repository = Path(repository_root).resolve(strict=True)
    profile_ref = repository_api.repository_file(
        repository, profile_ref, "profile_ref",
    )
    environment = dict(os.environ if environment is None else environment)
    trusted_base_commit = repository_api.resolve_commit(
        repository, approval.get("trusted_base_commit"), "trusted_base_commit",
    )
    candidate_commit = repository_api.resolve_commit(
        repository, approval.get("candidate_commit"), "candidate_commit",
    )
    include_worktree = approval.get("include_worktree")
    if type(include_worktree) is not bool:
        raise VerificationPlannerError("invalid verification profile approval")
    if type(allow_declared_mutation) is not bool:
        raise VerificationPlannerError("invalid verification profile approval")
    try:
        trusted_profile = _trusted_profile(
            repository, trusted_base_commit, profile_ref,
        )
    except VerificationPlannerError:
        raise VerificationPlannerError(
            "invalid verification profile approval",
        ) from None
    trusted_authority_digest = repository_api.authority_digest_at_commit(
        trusted_profile, repository, trusted_base_commit, environment,
    )
    current_authority_digest = (
        authority_digest
        if authority_digest is not None
        else repository_api.authority_digest(profile, repository, environment)
    )
    changed_paths = repository_api.normalize_changed_paths(
        approval.get("changed_paths"),
    )
    current_changed_paths = checkout_changed_paths(
        repository, trusted_base_commit, candidate_commit,
        include_worktree or allow_declared_mutation,
    )
    if not allow_declared_mutation and current_changed_paths != changed_paths:
        raise VerificationPlannerError(
            "current checkout differs from the approved candidate",
        )
    if (
        not allow_declared_mutation
        and _candidate_snapshot_digest(repository, changed_paths)
        != approval.get("candidate_snapshot_digest")
    ):
        raise VerificationPlannerError(
            "current checkout content differs from the approved candidate",
        )
    expected = {
        "schema_version": 1,
        "artifact_role": "repository_verification_profile_approval",
        "repository_scope_digest": repository_api.repository_scope_digest(repository),
        "profile_id": trusted_profile["profile_id"],
        "profile_ref": profile_ref,
        "profile_digest": digest(trusted_profile),
        "authority_digest": trusted_authority_digest,
        "trusted_base_commit": trusted_base_commit,
        "candidate_commit": candidate_commit,
        "include_worktree": include_worktree,
        "changed_paths": changed_paths,
        "changed_paths_digest": digest(changed_paths),
        "candidate_snapshot_digest": approval.get(
            "candidate_snapshot_digest",
        ),
        "run_id": approval.get("run_id"),
        "authorization_event_id": approval.get("authorization_event_id"),
        "approved_at": approval.get("approved_at"),
        "authority_key_id": byte_digest(key),
        "approval_auth": approval.get("approval_auth"),
    }
    if (
        profile != trusted_profile
        or current_authority_digest != trusted_authority_digest
    ):
        raise VerificationPlannerError(
            "verification profile is not approved by the host",
        )
    try:
        repository_api.bounded_string(expected["run_id"], "run_id")
        repository_api.bounded_string(
            expected["authorization_event_id"], "authorization_event_id",
        )
        expected["approved_at"] = repository_api.timestamp(
            expected["approved_at"], "approved_at",
        )
    except VerificationPlannerError:
        raise VerificationPlannerError(
            "invalid verification profile approval",
        ) from None
    return validate_approval_document(approval, expected, key)
