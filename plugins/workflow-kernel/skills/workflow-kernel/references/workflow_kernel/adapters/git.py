"""Pure, registry-scoped Git cleanup planning."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
import re
from typing import Callable, Tuple

from workflow_kernel.adapters.base import invalid_policy
from workflow_kernel.resources import (
    CleanupAction, CleanupDisposition, CleanupPlan, CleanupScope, CommandResult,
    ResourceDisposition, ResourceKind, ResourceRecord, ResourceRegistry,
    build_cleanup_action, cleanup_result_id, disposition_for,
)


@dataclass(frozen=True)
class GitProof:
    worktree_path: str
    branch: str
    readable: bool
    dirty: bool
    branch_is_feature: bool
    ancestor_of_merge_target: bool
    unique_commit_count: int
    base_ref: str
    merge_target: str
    ownership_namespace: str
    captured_at: datetime
    worktree_head_oid: str
    branch_oid: str
    base_oid: str
    merge_target_oid: str
    worktree_prunable: bool
    worktree_present: bool = True

    def __post_init__(self) -> None:
        if not _valid_git_proof(self):
            raise invalid_policy("invalid_git_proof")


class GitAdapter:
    def __init__(
        self, ownership_namespace: str, worktree_root: str, *,
        now: Callable[[], datetime] | None = None,
        max_proof_age: timedelta = timedelta(seconds=5),
    ):
        if not ownership_namespace or not worktree_root or max_proof_age.total_seconds() < 0:
            raise invalid_policy("invalid_git_ownership_scope")
        self.ownership_namespace = ownership_namespace.rstrip("/")
        self.worktree_root = worktree_root.rstrip("/")
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.max_proof_age = max_proof_age

    @staticmethod
    def proof_argv(
        worktree_path: str, branch: str, base_ref: str, merge_target: str,
    ) -> Tuple[Tuple[str, ...], ...]:
        return (
            ("git", "worktree", "list", "--porcelain", "-z"),
            ("git", "-C", worktree_path, "status", "--porcelain=v1", "-z"),
            ("git", "merge-base", "--is-ancestor", "--", branch, merge_target),
            ("git", "rev-list", "--count", "--", base_ref + ".." + branch),
            ("git", "rev-parse", "--verify", "--end-of-options", branch + "^{commit}"),
            ("git", "rev-parse", "--verify", "--end-of-options", base_ref + "^{commit}"),
            ("git", "rev-parse", "--verify", "--end-of-options", merge_target + "^{commit}"),
        )

    def cleanup_owned(
        self, registry: ResourceRegistry, scope: CleanupScope, proof: GitProof,
    ) -> CleanupPlan:
        if type(proof) is not GitProof or not _valid_git_proof(proof):
            raise invalid_policy("invalid_git_proof")
        if not proof.worktree_present:
            raise invalid_policy("git_worktree_absent_before_cleanup")
        records = registry.resources_for(scope)
        worktrees = tuple(item for item in records if item.kind is ResourceKind.WORKTREE)
        branches = tuple(item for item in records if item.kind is ResourceKind.BRANCH)
        git_records = worktrees + branches
        before = tuple(
            item.kind.value + ":" + item.resource_id for item in records
            if item.kind in (ResourceKind.WORKTREE, ResourceKind.BRANCH)
        )
        if len(worktrees) != 1 or len(branches) != 1:
            dispositions = tuple(
                disposition_for(item, CleanupDisposition.BLOCKED, "none", "ambiguous_registered_git_resources")
                for item in git_records
            )
            if not dispositions:
                dispositions = (
                    ResourceDisposition(
                        proof.worktree_path, ResourceKind.WORKTREE, scope.run_id,
                        scope.node_id or "unknown", "chunk", CleanupDisposition.FOREIGN,
                        "none", "git_resource_not_registered",
                    ),
                )
            return CleanupPlan(scope, before, (), dispositions)
        worktree, branch = worktrees[0], branches[0]
        if not self._proof_matches_scope(proof, worktree, branch):
            dispositions = tuple(
                disposition_for(item, CleanupDisposition.FOREIGN, "none", "git_ownership_proof_mismatch")
                for item in git_records
            )
            return CleanupPlan(scope, before, (), dispositions)
        if not self._proof_is_fresh(proof):
            return CleanupPlan(scope, before, (), (
                disposition_for(worktree, CleanupDisposition.BLOCKED, "none", "git_proof_stale_or_unreadable"),
                disposition_for(branch, CleanupDisposition.BLOCKED, "none", "git_proof_stale_or_unreadable"),
            ))
        if not proof.readable:
            return CleanupPlan(scope, before, (), (
                disposition_for(worktree, CleanupDisposition.BLOCKED, "none", "worktree_unreadable"),
                disposition_for(branch, CleanupDisposition.BLOCKED, "none", "worktree_proof_unavailable"),
            ))
        if proof.worktree_prunable:
            return CleanupPlan(scope, before, (), (
                disposition_for(
                    worktree, CleanupDisposition.BLOCKED, "none",
                    "registered_worktree_prunable", evidence=("head=" + proof.worktree_head_oid,),
                ),
                disposition_for(branch, CleanupDisposition.BLOCKED, "none", "worktree_must_be_removed_first"),
            ))
        if proof.dirty:
            return CleanupPlan(scope, before, (), (
                disposition_for(worktree, CleanupDisposition.BLOCKED, "none", "worktree_dirty"),
                disposition_for(branch, CleanupDisposition.BLOCKED, "none", "worktree_must_be_removed_first"),
            ))

        preconditions = (
            "registered_kind_and_exact_id", "proof_fresh", "worktree_clean",
            "authoritative_worktree_inventory_unchanged",
        )
        worktree_argv = ("git", "worktree", "remove", "--", worktree.resource_id)
        actions = [_git_action(
            worktree, "remove", worktree_argv, None, preconditions, proof,
        )]
        dispositions = []
        if branch.labels["ref-role"] == "feature-branch":
            dispositions.append(disposition_for(
                branch, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none",
                "feature_branch_orchestrator_disposition_only",
            ))
        elif proof.ancestor_of_merge_target:
            actions.append(_git_action(
                branch, "remove", ("git", "branch", "-d", "--", branch.resource_id),
                0, preconditions + (
                    "worktree_absent_after_predecessor", "branch_ancestor_of_merge_target",
                ), replace(proof, worktree_present=False),
                cleanup_result_id(worktree_argv, 0),
            ))
        elif proof.unique_commit_count == 0:
            actions.append(_git_action(
                branch, "remove", ("git", "branch", "-D", "--", branch.resource_id),
                0, preconditions + (
                    "worktree_absent_after_predecessor", "branch_unique_commit_count_zero",
                ), replace(proof, worktree_present=False),
                cleanup_result_id(worktree_argv, 0),
            ))
        else:
            dispositions.append(disposition_for(
                branch, CleanupDisposition.BLOCKED, "none", "branch_has_unique_unmerged_commits",
                follow_up="inspect exact registered branch before retry",
            ))
        return CleanupPlan(scope, before, tuple(actions), tuple(dispositions))

    def revalidate_action(
        self, action: CleanupAction, proof: GitProof,
        predecessor_result: CommandResult | None = None,
    ) -> None:
        """Fail closed unless execution-time Git proof is byte-for-byte equivalent."""
        if type(action) is not CleanupAction or type(proof) is not GitProof or not _valid_git_proof(proof):
            raise invalid_policy("invalid_git_cleanup_revalidation")
        try:
            action = CleanupAction(
                action.resource_id, action.kind, action.action, tuple(action.argv),
                action.requires_success_of, action.run_id, action.node_id,
                action.lifecycle, action.proof_digest, tuple(action.preconditions),
                dict(action.environment), action.predecessor_result_id,
                action.evidence_digest,
            )
        except Exception:
            raise invalid_policy("invalid_git_cleanup_revalidation") from None
        if not self._proof_is_fresh(proof):
            raise invalid_policy("git_cleanup_precondition_changed")
        preconditions = (
            "registered_kind_and_exact_id", "proof_fresh", "worktree_clean",
            "authoritative_worktree_inventory_unchanged",
        )
        expected = None
        if action.kind is ResourceKind.WORKTREE and proof.worktree_present and not proof.dirty and proof.readable:
            expected = _git_action(
                ResourceRecord(
                    proof.worktree_path, ResourceKind.WORKTREE, action.run_id,
                    action.node_id, action.lifecycle, "retain", proof.captured_at,
                    labels={},
                ),
                "remove", ("git", "worktree", "remove", "--", proof.worktree_path),
                None, preconditions, proof,
            )
        elif action.kind is ResourceKind.BRANCH and not proof.worktree_present:
            if (
                type(predecessor_result) is not CommandResult
                or predecessor_result.exit_code != 0
                or predecessor_result.argv != ("git", "worktree", "remove", "--", proof.worktree_path)
                or cleanup_result_id(predecessor_result.argv, 0) != action.predecessor_result_id
            ):
                raise invalid_policy("git_cleanup_precondition_changed")
            if proof.ancestor_of_merge_target:
                argv = ("git", "branch", "-d", "--", proof.branch)
                branch_condition = "branch_ancestor_of_merge_target"
            elif proof.unique_commit_count == 0:
                argv = ("git", "branch", "-D", "--", proof.branch)
                branch_condition = "branch_unique_commit_count_zero"
            else:
                raise invalid_policy("git_cleanup_precondition_changed")
            expected = _git_action(
                ResourceRecord(
                    proof.branch, ResourceKind.BRANCH, action.run_id, action.node_id,
                    action.lifecycle, "retain", proof.captured_at, labels={},
                ),
                "remove", argv, action.requires_success_of,
                preconditions + ("worktree_absent_after_predecessor", branch_condition),
                proof, action.predecessor_result_id,
            )
        if expected is None or action != expected:
            raise invalid_policy("git_cleanup_precondition_changed")

    @staticmethod
    def _proof_evidence(proof: GitProof) -> dict[str, object]:
        return {
            "worktree_path": proof.worktree_path, "branch": proof.branch,
            "readable": proof.readable, "dirty": proof.dirty,
            "branch_is_feature": proof.branch_is_feature,
            "ancestor_of_merge_target": proof.ancestor_of_merge_target,
            "unique_commit_count": proof.unique_commit_count,
            "base_ref": proof.base_ref, "merge_target": proof.merge_target,
            "ownership_namespace": proof.ownership_namespace,
            "worktree_head_oid": proof.worktree_head_oid, "branch_oid": proof.branch_oid,
            "base_oid": proof.base_oid, "merge_target_oid": proof.merge_target_oid,
            "worktree_prunable": proof.worktree_prunable,
            "worktree_present": proof.worktree_present,
        }

    def _proof_matches_scope(
        self, proof: GitProof, worktree: ResourceRecord, branch: ResourceRecord,
    ) -> bool:
        path_parts = PurePosixPath(proof.worktree_path).parts
        return (
            ".." not in path_parts
            and proof.ownership_namespace == self.ownership_namespace
            and proof.worktree_path.startswith(self.worktree_root + "/")
            and proof.branch.startswith(self.ownership_namespace + "/")
            and proof.worktree_path == worktree.resource_id
            and proof.branch == branch.resource_id
            and self._labels_match(worktree, proof)
            and self._labels_match(branch, proof)
        )

    def _labels_match(self, record: ResourceRecord, proof: GitProof) -> bool:
        role = record.labels.get("ref-role")
        valid_role = (
            role == "chunk-worktree" if record.kind is ResourceKind.WORKTREE
            else role in {"chunk-branch", "feature-branch"}
        )
        return valid_role and record.labels == {
            "ownership-namespace": self.ownership_namespace,
            "base-ref": proof.base_ref,
            "merge-target": proof.merge_target,
            "ref-role": role,
        }

    def _proof_is_fresh(self, proof: GitProof) -> bool:
        if not isinstance(proof.captured_at, datetime) or proof.captured_at.tzinfo is None:
            return False
        age = self.now() - proof.captured_at
        return timedelta(0) <= age <= self.max_proof_age


def _git_action(
    record: ResourceRecord, action: str, argv: Tuple[str, ...],
    requires_success_of: int | None, preconditions: Tuple[str, ...],
    proof: GitProof, predecessor_result_id: str | None = None,
) -> CleanupAction:
    return build_cleanup_action(
        evidence=GitAdapter._proof_evidence(proof),
        resource_id=record.resource_id, kind=record.kind, action=action,
        argv=argv, requires_success_of=requires_success_of,
        run_id=record.run_id, node_id=record.node_id, lifecycle=record.lifecycle,
        preconditions=preconditions, predecessor_result_id=predecessor_result_id,
    )


def _normalized_absolute_path(value: object) -> bool:
    if (
        type(value) is not str or not value or len(value) > 4096
        or value != value.strip() or "\x00" in value
    ):
        return False
    path = PurePosixPath(value)
    return path.is_absolute() and ".." not in path.parts and str(path) == value


def _normalized_git_ref(value: object) -> bool:
    if type(value) is not str or not value or len(value) > 256 or value != value.strip():
        return False
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    return (
        not value.startswith(("/", ".", "-")) and not value.endswith(("/", ".", ".lock"))
        and "//" not in value and ".." not in value and "@{" not in value and "\\" not in value
    )


def _valid_git_proof(proof: object) -> bool:
    return (
        type(proof) is GitProof
        and _normalized_absolute_path(proof.worktree_path)
        and all(_normalized_git_ref(value) for value in (
            proof.branch, proof.base_ref, proof.merge_target, proof.ownership_namespace,
        ))
        and all(type(value) is bool for value in (
            proof.readable, proof.dirty, proof.branch_is_feature,
            proof.ancestor_of_merge_target, proof.worktree_prunable,
            proof.worktree_present,
        ))
        and type(proof.unique_commit_count) is int and proof.unique_commit_count >= 0
        and type(proof.captured_at) is datetime
        and proof.captured_at.tzinfo is not None and proof.captured_at.utcoffset() is not None
        and all(type(value) is str and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value)
                for value in (proof.worktree_head_oid, proof.branch_oid, proof.base_oid, proof.merge_target_oid))
        and proof.worktree_head_oid == proof.branch_oid
    )
