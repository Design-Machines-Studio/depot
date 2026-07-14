import unittest

from workflow_kernel.adapters.git import GitAdapter, GitInventory
from workflow_kernel.resources import CleanupDisposition, CommandResult


class FakeRunner:
    def __init__(self, results=()):
        self.results = {result.argv: result for result in results}
        self.calls = []

    def run(self, argv):
        argv = tuple(argv)
        self.calls.append(argv)
        return self.results.get(argv, CommandResult(argv, 0, "", ""))


class GitCleanupTests(unittest.TestCase):
    def test_merged_owned_branch_uses_safe_delete_and_removes_clean_worktree(self):
        runner = FakeRunner()
        adapter = GitAdapter(runner)
        inventory = GitInventory(
            worktree_path="/tmp/wt", branch="codex/chunk", readable=True, dirty=False,
            branch_is_feature=False, ancestor_of_base=True, unique_commit_count=0,
        )
        receipt = adapter.cleanup_owned(inventory)
        self.assertEqual(("git", "worktree", "remove", "/tmp/wt"), runner.calls[0])
        self.assertEqual(("git", "branch", "-d", "codex/chunk"), runner.calls[1])
        self.assertTrue(all(item.disposition is CleanupDisposition.REMOVED for item in receipt.dispositions))

    def test_unmerged_zero_unique_branch_may_use_force_delete(self):
        runner = FakeRunner()
        inventory = GitInventory("/tmp/wt", "codex/chunk", True, False, False, False, 0)
        GitAdapter(runner).cleanup_owned(inventory)
        self.assertIn(("git", "branch", "-D", "codex/chunk"), runner.calls)

    def test_dirty_or_unreadable_worktree_is_blocked_without_mutation(self):
        for readable, dirty, reason in ((True, True, "worktree_dirty"), (False, False, "worktree_unreadable")):
            runner = FakeRunner()
            receipt = GitAdapter(runner).cleanup_owned(
                GitInventory("/tmp/wt", "codex/chunk", readable, dirty, False, True, 0)
            )
            self.assertEqual([], runner.calls)
            self.assertEqual(CleanupDisposition.BLOCKED, receipt.dispositions[0].disposition)
            self.assertEqual(reason, receipt.dispositions[0].reason)

    def test_feature_branch_is_never_deleted_by_adapter(self):
        runner = FakeRunner()
        receipt = GitAdapter(runner).cleanup_owned(
            GitInventory("/tmp/wt", "codex/feature", True, False, True, True, 0)
        )
        self.assertNotIn(("git", "branch", "-d", "codex/feature"), runner.calls)
        self.assertEqual(CleanupDisposition.RETAINED_FOR_DEPENDENCY, receipt.dispositions[-1].disposition)

    def test_command_failure_is_recorded_as_blocked(self):
        result = CommandResult(("git", "worktree", "remove", "/tmp/wt"), 1, "", "busy")
        receipt = GitAdapter(FakeRunner((result,))).cleanup_owned(
            GitInventory("/tmp/wt", "codex/chunk", True, False, False, True, 0)
        )
        self.assertEqual(CleanupDisposition.BLOCKED, receipt.dispositions[0].disposition)
        self.assertEqual("worktree_remove_failed", receipt.dispositions[0].reason)


if __name__ == "__main__":
    unittest.main()
