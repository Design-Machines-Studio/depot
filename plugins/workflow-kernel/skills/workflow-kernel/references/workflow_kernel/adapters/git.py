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
        records = registry.resources_for(scope)
        worktree = next((item for item in records if item.kind is ResourceKind.WORKTREE), None)
        branch = next((item for item in records if item.kind is ResourceKind.BRANCH), None)
        before = tuple(
            item.kind.value + ":" + item.resource_id for item in records
            if item.kind in (ResourceKind.WORKTREE, ResourceKind.BRANCH)
        )
        candidates = tuple(item for item in (worktree, branch) if item is not None)
        if worktree is None or branch is None or not self._proof_matches_scope(proof, worktree, branch):
            dispositions = tuple(
                disposition_for(item, CleanupDisposition.FOREIGN, "none", "git_ownership_proof_mismatch")
                for item in candidates
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
            ))
        elif proof.unique_commit_count == 0:
            actions.append(CleanupAction(
                branch.resource_id, ResourceKind.BRANCH, "remove",
                ("git", "branch", "-D", branch.resource_id), 0,
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
