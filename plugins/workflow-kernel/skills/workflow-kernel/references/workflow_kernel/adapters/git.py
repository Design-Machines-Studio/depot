"""Pure, registry-scoped Git cleanup planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Callable, Tuple

from workflow_kernel.adapters.base import invalid_policy
from workflow_kernel.resources import (
    CleanupAction, CleanupDisposition, CleanupPlan, CleanupScope,
    ResourceDisposition, ResourceKind, ResourceRecord, ResourceRegistry, disposition_for,
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
            ("git", "-C", worktree_path, "status", "--porcelain=v1", "-z"),
            ("git", "merge-base", "--is-ancestor", branch, merge_target),
            ("git", "rev-list", "--count", base_ref + ".." + branch),
        )

    def cleanup_owned(
        self, registry: ResourceRegistry, scope: CleanupScope, proof: GitProof,
    ) -> CleanupPlan:
        if type(proof) is not GitProof or not _valid_git_proof(proof):
            raise invalid_policy("invalid_git_proof")
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
        if proof.dirty:
            return CleanupPlan(scope, before, (), (
                disposition_for(worktree, CleanupDisposition.BLOCKED, "none", "worktree_dirty"),
                disposition_for(branch, CleanupDisposition.BLOCKED, "none", "worktree_must_be_removed_first"),
            ))

        actions = [CleanupAction(
            worktree.resource_id, ResourceKind.WORKTREE, "remove",
            ("git", "worktree", "remove", worktree.resource_id),
            run_id=worktree.run_id, node_id=worktree.node_id, lifecycle=worktree.lifecycle,
        )]
        dispositions = []
        if branch.labels["ref-role"] == "feature-branch":
            dispositions.append(disposition_for(
                branch, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none",
                "feature_branch_orchestrator_disposition_only",
            ))
        elif proof.ancestor_of_merge_target:
            actions.append(CleanupAction(
                branch.resource_id, ResourceKind.BRANCH, "remove",
                ("git", "branch", "-d", branch.resource_id), 0,
                branch.run_id, branch.node_id, branch.lifecycle,
            ))
        elif proof.unique_commit_count == 0:
            actions.append(CleanupAction(
                branch.resource_id, ResourceKind.BRANCH, "remove",
                ("git", "branch", "-D", branch.resource_id), 0,
                branch.run_id, branch.node_id, branch.lifecycle,
            ))
        else:
            dispositions.append(disposition_for(
                branch, CleanupDisposition.BLOCKED, "none", "branch_has_unique_unmerged_commits",
                follow_up="inspect exact registered branch before retry",
            ))
        return CleanupPlan(scope, before, tuple(actions), tuple(dispositions))

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
        not value.startswith(("/", ".")) and not value.endswith(("/", ".", ".lock"))
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
            proof.ancestor_of_merge_target,
        ))
        and type(proof.unique_commit_count) is int and proof.unique_commit_count >= 0
        and type(proof.captured_at) is datetime
        and proof.captured_at.tzinfo is not None and proof.captured_at.utcoffset() is not None
    )
