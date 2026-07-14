"""Positive-ownership Git cleanup adapter with the existing safety table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Tuple

from workflow_kernel.resources import (
    CleanupDisposition, CleanupReceipt, CommandResult, ResourceDisposition, ResourceKind,
)


class CommandRunner(Protocol):
    def run(self, argv: Tuple[str, ...]) -> CommandResult: ...


@dataclass(frozen=True)
class GitInventory:
    worktree_path: str
    branch: str
    readable: bool
    dirty: bool
    branch_is_feature: bool
    ancestor_of_base: bool
    unique_commit_count: int


class GitAdapter:
    def __init__(self, runner: CommandRunner):
        self.runner = runner

    def inventory(self, worktree_path: str, branch: str, *, branch_is_feature: bool) -> GitInventory:
        status = self.runner.run(("git", "-C", worktree_path, "status", "--porcelain=v1", "-z"))
        if status.exit_code != 0:
            return GitInventory(worktree_path, branch, False, False, branch_is_feature, False, -1)
        ancestor = self.runner.run(("git", "merge-base", "--is-ancestor", branch, "origin/main"))
        count = self.runner.run(("git", "rev-list", "--count", "origin/main.." + branch))
        try:
            unique = int(count.stdout.strip()) if count.exit_code == 0 else -1
        except (TypeError, ValueError):
            unique = -1
        return GitInventory(
            worktree_path, branch, True, bool(status.stdout), branch_is_feature,
            ancestor.exit_code == 0, unique,
        )

    def cleanup_owned(self, inventory: GitInventory) -> CleanupReceipt:
        before = (inventory.worktree_path, inventory.branch)
        dispositions = []
        if not inventory.readable:
            dispositions.append(self._item(ResourceKind.WORKTREE, inventory, CleanupDisposition.BLOCKED, "none", "worktree_unreadable"))
            return CleanupReceipt(before, before, tuple(dispositions))
        if inventory.dirty:
            dispositions.append(self._item(ResourceKind.WORKTREE, inventory, CleanupDisposition.BLOCKED, "none", "worktree_dirty"))
            return CleanupReceipt(before, before, tuple(dispositions))

        remove = self.runner.run(("git", "worktree", "remove", inventory.worktree_path))
        if remove.exit_code != 0:
            dispositions.append(self._item(ResourceKind.WORKTREE, inventory, CleanupDisposition.BLOCKED, "git worktree remove", "worktree_remove_failed", ("exit=" + str(remove.exit_code),)))
            return CleanupReceipt(before, before, tuple(dispositions))
        dispositions.append(self._item(ResourceKind.WORKTREE, inventory, CleanupDisposition.REMOVED, "git worktree remove", "clean_owned_worktree"))

        if inventory.branch_is_feature:
            dispositions.append(self._item(ResourceKind.BRANCH, inventory, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "feature_branch_requires_merge_proof_and_orchestrator_disposition"))
            return CleanupReceipt(before, (inventory.branch,), tuple(dispositions))
        if inventory.ancestor_of_base:
            flag, reason = "-d", "branch_merged_into_base"
        elif inventory.unique_commit_count == 0:
            flag, reason = "-D", "branch_has_zero_unique_commits"
        else:
            dispositions.append(self._item(ResourceKind.BRANCH, inventory, CleanupDisposition.BLOCKED, "none", "branch_has_unique_unmerged_commits"))
            return CleanupReceipt(before, (inventory.branch,), tuple(dispositions))
        deleted = self.runner.run(("git", "branch", flag, inventory.branch))
        if deleted.exit_code != 0:
            dispositions.append(self._item(ResourceKind.BRANCH, inventory, CleanupDisposition.BLOCKED, "git branch " + flag, "branch_delete_failed", ("exit=" + str(deleted.exit_code),)))
            return CleanupReceipt(before, (inventory.branch,), tuple(dispositions))
        dispositions.append(self._item(ResourceKind.BRANCH, inventory, CleanupDisposition.REMOVED, "git branch " + flag, reason))
        return CleanupReceipt(before, (), tuple(dispositions))

    @staticmethod
    def _item(kind, inventory, disposition, action, reason, evidence=()):
        identity = inventory.worktree_path if kind is ResourceKind.WORKTREE else inventory.branch
        return ResourceDisposition(
            identity, kind, "git", "git", "run", disposition, action, reason, tuple(evidence)
        )
